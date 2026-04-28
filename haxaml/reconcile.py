"""Deterministic derivation-boundary reconciliation for FRAME files."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from haxaml.map_policy import evaluate_map_complexity
from haxaml.paths import resolve_frame_file
from haxaml.validator import load_yaml


_CATEGORY_FIX_CONFIDENCE = {
    "map_required": "high",
    "module_sync": "medium",
    "facts_boundary_sync": "low",
    "runbook_module_sync": "medium",
    "map_dependency_integrity": "high",
    "dependency_sync": "medium",
    "impact_integrity": "medium",
}

_CATEGORY_WHY_IT_MATTERS = {
    "map_required": "Map-canonical checks are blocked without map.yaml, so validation and session gates cannot reliably enforce module boundaries.",
    "module_sync": "When map modules and rules modules diverge, boundary ownership and downstream verification gates become inconsistent.",
    "facts_boundary_sync": "Facts boundaries that drift from map modules reduce operator visibility and can mislead planning context.",
    "runbook_module_sync": "Runbook touches must reference mapped modules so planned work aligns with enforced map boundaries.",
    "map_dependency_integrity": "Dependencies that reference undeclared modules make impact analysis and gate decisions unreliable.",
    "dependency_sync": "Dependency drift between map and rules causes inconsistent boundary enforcement across tools.",
    "impact_integrity": "Impact triggers must point to declared modules so verification can enforce the correct checks.",
}


def _normalize_name(value: Any) -> str:
    return str(value).strip().lower()


def _sorted_unique(values: set[str]) -> list[str]:
    return sorted(v for v in values if v)


def _map_modules(map_data: dict[str, Any]) -> set[str]:
    modules = map_data.get("modules", [])
    names: set[str] = set()
    if not isinstance(modules, list):
        return names
    for mod in modules:
        if isinstance(mod, dict):
            name = _normalize_name(mod.get("name", ""))
            if name:
                names.add(name)
    return names


def _rules_modules(rules: dict[str, Any]) -> set[str]:
    modules = (rules.get("boundaries", {}) or {}).get("modules", {})
    names: set[str] = set()
    if not isinstance(modules, dict):
        return names
    for key in modules.keys():
        name = _normalize_name(key)
        if name:
            names.add(name)
    return names


def _facts_boundaries(facts: dict[str, Any]) -> set[str]:
    boundaries = (facts.get("architecture", {}) or {}).get("boundaries", [])
    names: set[str] = set()
    if not isinstance(boundaries, list):
        return names
    for item in boundaries:
        if isinstance(item, str):
            chunk = item.split(":", 1)[0].strip()
            if chunk:
                names.add(chunk.lower())
        elif isinstance(item, dict):
            name = _normalize_name(item.get("name", ""))
            if name:
                names.add(name)
    return names


def _map_dependencies(map_data: dict[str, Any]) -> set[tuple[str, str]]:
    deps = map_data.get("dependencies", [])
    out: set[tuple[str, str]] = set()
    if not isinstance(deps, list):
        return out
    for dep in deps:
        if not isinstance(dep, dict):
            continue
        source = _normalize_name(dep.get("from", ""))
        target = _normalize_name(dep.get("to", ""))
        if source and target:
            out.add((source, target))
    return out


def _rules_dependencies(rules: dict[str, Any]) -> set[tuple[str, str]]:
    modules = (rules.get("boundaries", {}) or {}).get("modules", {})
    out: set[tuple[str, str]] = set()
    if not isinstance(modules, dict):
        return out
    for source, config in modules.items():
        src = _normalize_name(source)
        if not src or not isinstance(config, dict):
            continue
        touches = config.get("touches", [])
        if not isinstance(touches, list):
            continue
        for target in touches:
            dst = _normalize_name(target)
            if dst:
                out.add((src, dst))
    return out


def _expect_runbook_modules(expect: dict[str, Any]) -> set[str]:
    runbook = expect.get("runbook", [])
    names: set[str] = set()
    if not isinstance(runbook, list):
        return names
    for run in runbook:
        if not isinstance(run, dict):
            continue
        if not bool(run.get("uses_map", False)):
            continue
        touches = run.get("touches", [])
        if not isinstance(touches, list):
            continue
        for item in touches:
            token = _normalize_name(item)
            if token:
                names.add(token)
    return names


def _looks_like_module_reference(value: str) -> bool:
    if not value:
        return False
    return all(sep not in value for sep in ("/", "\\", "*", ".", ":", " "))


def _edge_records(edges: set[tuple[str, str]], source: str | None = None) -> list[dict[str, str]]:
    records = []
    for from_mod, to_mod in sorted(edges):
        if source and from_mod != source:
            continue
        records.append({"from": from_mod, "to": to_mod})
    return records


def _path_file(path: str) -> str:
    return str(path).split(":", 1)[0].strip()


def _related_files(canonical_path: str, derived_path: str) -> list[str]:
    files = {_path_file(canonical_path), _path_file(derived_path)}
    return sorted(f for f in files if f)


def _fix_confidence(category: str, severity: str) -> str:
    if category in _CATEGORY_FIX_CONFIDENCE:
        return _CATEGORY_FIX_CONFIDENCE[category]
    return "medium" if severity == "blocking" else "low"


def _why_it_matters(category: str, message: str) -> str:
    return _CATEGORY_WHY_IT_MATTERS.get(category, f"This conflict matters because {message.lower()}")


@dataclass
class _ConflictBuilder:
    items: list[dict[str, Any]]
    counter: int = 0

    def add(
        self,
        *,
        category: str,
        severity: str,
        canonical_path: str,
        derived_path: str,
        canonical_value: Any,
        derived_value: Any,
        message: str,
        suggested_fix_action: str,
    ) -> None:
        self.counter += 1
        related_files = _related_files(canonical_path, derived_path)
        fix_confidence = _fix_confidence(category, severity)
        self.items.append(
            {
                "id": f"conflict-{self.counter:03d}",
                "category": category,
                "severity": severity,
                "canonical_path": canonical_path,
                "derived_path": derived_path,
                "canonical_value": canonical_value,
                "derived_value": derived_value,
                "message": message,
                "suggested_fix_action": suggested_fix_action,
                "fix_confidence": fix_confidence,
                "safe_to_auto_apply": False,
                "related_files": related_files,
                "why_it_matters": _why_it_matters(category, message),
                "suggested_next_tool": "manual_edit",
            }
        )


def reconcile_derivation(project_dir: str | Path) -> dict[str, Any]:
    """Return deterministic derivation-boundary conflict report."""
    project = Path(project_dir).resolve()
    assessment = evaluate_map_complexity(project)
    map_path = resolve_frame_file(project, "map.yaml")
    rules_path = resolve_frame_file(project, "rules.yaml", "mind.yaml")
    facts_path = resolve_frame_file(project, "facts.yaml", "brain.yaml")
    expect_path = resolve_frame_file(project, "expect.yaml")

    rules = load_yaml(str(rules_path)) if rules_path else {}
    facts = load_yaml(str(facts_path)) if facts_path else {}
    expect = load_yaml(str(expect_path)) if expect_path else {}

    conflicts: list[dict[str, Any]] = []
    add = _ConflictBuilder(conflicts)

    if not map_path:
        if assessment.required:
            add.add(
                category="map_required",
                severity="blocking",
                canonical_path=".haxaml/expect.yaml:planning.map_required",
                derived_path=".haxaml/map.yaml",
                canonical_value=True,
                derived_value=None,
                message="Map complexity policy requires map.yaml but file is missing.",
                suggested_fix_action="Create .haxaml/map.yaml and align module/dependency/impact definitions.",
            )
            human_summary = "Blocking conflict: map.yaml is required by complexity policy but missing."
        else:
            human_summary = "No map.yaml found; map-canonical derivation checks were deferred by policy."
        severity_totals = {
            "blocking": sum(1 for c in conflicts if c["severity"] == "blocking"),
            "warning": sum(1 for c in conflicts if c["severity"] == "warning"),
        }
        gate_reasons = [c["message"] for c in conflicts if c["severity"] == "blocking"]
        return {
            "project_dir": str(project),
            "has_map": False,
            "map_required": assessment.required,
            "deferred_map_canonical_checks": not assessment.required,
            "conflicts": conflicts,
            "conflict_counts": {
                "total": len(conflicts),
                "blocking": severity_totals["blocking"],
            },
            "warning_counts": {"total": severity_totals["warning"]},
            "severity_totals": severity_totals,
            "gate_reasons": gate_reasons,
            "human_summary": human_summary,
        }

    map_data = load_yaml(str(map_path))
    map_modules = _map_modules(map_data)
    rules_modules = _rules_modules(rules)
    facts_modules = _facts_boundaries(facts)
    runbook_modules = _expect_runbook_modules(expect)
    map_edges = _map_dependencies(map_data)
    rule_edges = _rules_dependencies(rules)

    for name in _sorted_unique(map_modules - rules_modules):
        add.add(
            category="module_sync",
            severity="blocking",
            canonical_path=f".haxaml/map.yaml:modules[name={name}]",
            derived_path=f".haxaml/rules.yaml:boundaries.modules.{name}",
            canonical_value=name,
            derived_value=None,
            message=f"Map module '{name}' is missing in rules.boundaries.modules.",
            suggested_fix_action=f"Add rules.boundaries.modules.{name} and align ownership/purpose to map module '{name}'.",
        )

    for name in _sorted_unique(rules_modules - map_modules):
        add.add(
            category="module_sync",
            severity="blocking",
            canonical_path=".haxaml/map.yaml:modules",
            derived_path=f".haxaml/rules.yaml:boundaries.modules.{name}",
            canonical_value=_sorted_unique(map_modules),
            derived_value=name,
            message=f"Rules module '{name}' is not declared in map.modules.",
            suggested_fix_action=f"Add module '{name}' to map.modules or remove it from rules.boundaries.modules.",
        )

    for name in _sorted_unique(map_modules - facts_modules):
        add.add(
            category="facts_boundary_sync",
            severity="warning",
            canonical_path=f".haxaml/map.yaml:modules[name={name}]",
            derived_path=".haxaml/facts.yaml:architecture.boundaries",
            canonical_value=name,
            derived_value=_sorted_unique(facts_modules),
            message=f"Map module '{name}' is missing from facts architecture boundaries.",
            suggested_fix_action=f"Add '{name}' to facts.architecture.boundaries or document why boundaries stay more abstract.",
        )

    for module in _sorted_unique(runbook_modules - map_modules):
        add.add(
            category="runbook_module_sync",
            severity="blocking",
            canonical_path=".haxaml/map.yaml:modules",
            derived_path=f".haxaml/expect.yaml:runbook[].touches[{module}]",
            canonical_value=_sorted_unique(map_modules),
            derived_value=module,
            message=f"Runbook touches unknown module '{module}' not present in map.modules.",
            suggested_fix_action=f"Add module '{module}' to map.modules or update expect.runbook touches to mapped modules.",
        )

    for source, target in sorted(map_edges):
        if source not in map_modules or target not in map_modules:
            add.add(
                category="map_dependency_integrity",
                severity="blocking",
                canonical_path=f".haxaml/map.yaml:dependencies[{source}->{target}]",
                derived_path=".haxaml/map.yaml:modules",
                canonical_value={"from": source, "to": target},
                derived_value=_sorted_unique(map_modules),
                message=f"Dependency '{source}->{target}' references module(s) not declared in map.modules.",
                suggested_fix_action="Fix dependency endpoints or add the missing module declarations in map.modules.",
            )

    for edge in sorted(map_edges - rule_edges):
        source, target = edge
        add.add(
            category="dependency_sync",
            severity="blocking",
            canonical_path=f".haxaml/map.yaml:dependencies[{source}->{target}]",
            derived_path=f".haxaml/rules.yaml:boundaries.modules.{source}.touches",
            canonical_value={"from": source, "to": target},
            derived_value=_edge_records(rule_edges, source=source),
            message=f"Map dependency '{source}->{target}' is missing in rules boundaries touches.",
            suggested_fix_action=f"Add '{target}' to rules.boundaries.modules.{source}.touches.",
        )

    for edge in sorted(rule_edges - map_edges):
        source, target = edge
        add.add(
            category="dependency_sync",
            severity="blocking",
            canonical_path=".haxaml/map.yaml:dependencies",
            derived_path=f".haxaml/rules.yaml:boundaries.modules.{source}.touches[{target}]",
            canonical_value=_edge_records(map_edges),
            derived_value={"from": source, "to": target},
            message=f"Rules dependency '{source}->{target}' is not declared in map.dependencies.",
            suggested_fix_action=f"Add dependency '{source}->{target}' to map.dependencies or remove the touch relation from rules.",
        )

    impact_rules = map_data.get("impact", [])
    if isinstance(impact_rules, list):
        for idx, rule in enumerate(impact_rules):
            if not isinstance(rule, dict):
                continue
            when = _normalize_name(rule.get("when", ""))
            if not _looks_like_module_reference(when):
                continue
            if when and when not in map_modules:
                add.add(
                    category="impact_integrity",
                    severity="blocking",
                    canonical_path=f".haxaml/map.yaml:impact[{idx}].when",
                    derived_path=".haxaml/map.yaml:modules",
                    canonical_value=when,
                    derived_value=_sorted_unique(map_modules),
                    message=f"Impact rule trigger '{when}' is not a declared map module.",
                    suggested_fix_action=f"Change impact.when to a declared module or add module '{when}' to map.modules.",
                )

    severity_totals = {
        "blocking": sum(1 for c in conflicts if c["severity"] == "blocking"),
        "warning": sum(1 for c in conflicts if c["severity"] == "warning"),
    }
    gate_reasons = [c["message"] for c in conflicts if c["severity"] == "blocking"]
    if severity_totals["blocking"]:
        human_summary = (
            f"Found {severity_totals['blocking']} blocking and "
            f"{severity_totals['warning']} warning derivation conflict(s)."
        )
    elif severity_totals["warning"]:
        human_summary = f"No blocking conflicts; found {severity_totals['warning']} warning(s)."
    else:
        human_summary = "No derivation conflicts detected. Map-canonical boundaries are consistent."

    return {
        "project_dir": str(project),
        "has_map": True,
        "map_required": assessment.required,
        "deferred_map_canonical_checks": False,
        "conflicts": conflicts,
        "conflict_counts": {
            "total": len(conflicts),
            "blocking": severity_totals["blocking"],
        },
        "warning_counts": {"total": severity_totals["warning"]},
        "severity_totals": severity_totals,
        "gate_reasons": gate_reasons,
        "human_summary": human_summary,
    }
