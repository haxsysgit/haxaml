"""Deterministic map.yaml requirement checks for module and cross-impact complexity."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from haxaml.paths import resolve_frame_file
from haxaml.validator import load_yaml


DEFAULT_SMALL_MAX_RUNS = 5
DEFAULT_MEDIUM_MAX_RUNS = 12
DEFAULT_MODULE_THRESHOLD = 10
DEFAULT_CROSS_IMPACT_TOUCH_THRESHOLD = 3
DEFAULT_CROSS_IMPACT_RUN_THRESHOLD = 2
DEFAULT_DEPENDENCY_FANOUT_THRESHOLD = 3
DEFAULT_IMPACT_CHECK_THRESHOLD = 3
DEFAULT_SHARED_INTEGRATION_MODULE_THRESHOLD = 2


@dataclass
class MapComplexityAssessment:
    """Computed map requirement and the measurable signals behind it."""

    required: bool
    has_map: bool
    declared_map_required: bool | None
    project_size: str
    estimated_runs: int
    module_count: int
    cross_impact_runs: int
    dependency_edges: int
    max_dependency_fanout: int
    max_dependency_fanin: int
    broad_impact_rules: int
    shared_integrations: int
    shared_database_signal: bool
    reasons: list[str] = field(default_factory=list)

    @property
    def declared_state(self) -> str:
        if self.declared_map_required is None:
            return "unset"
        return "true" if self.declared_map_required else "false"

    @property
    def required_state(self) -> str:
        return "true" if self.required else "false"


def _int_or_default(value: Any, default: int) -> int:
    try:
        ivalue = int(value)
        if ivalue < 1:
            return default
        return ivalue
    except (TypeError, ValueError):
        return default


def _module_names_from_rules(rules: dict[str, Any]) -> set[str]:
    modules = rules.get("boundaries", {}).get("modules", {})
    names: set[str] = set()

    if isinstance(modules, dict):
        for name in modules.keys():
            if isinstance(name, str) and name.strip():
                names.add(name.strip().lower())
    elif isinstance(modules, list):
        for item in modules:
            if isinstance(item, dict):
                name = item.get("name")
                if isinstance(name, str) and name.strip():
                    names.add(name.strip().lower())
    return names


def _module_names_from_facts(facts: dict[str, Any]) -> set[str]:
    boundaries = facts.get("architecture", {}).get("boundaries", [])
    names: set[str] = set()

    if not isinstance(boundaries, list):
        return names

    for item in boundaries:
        if isinstance(item, str):
            candidate = item.split(":", 1)[0].strip()
            if candidate:
                names.add(candidate.lower())
        elif isinstance(item, dict):
            name = item.get("name")
            if isinstance(name, str) and name.strip():
                names.add(name.strip().lower())
    return names


def _module_names_from_map(map_data: dict[str, Any]) -> set[str]:
    modules = map_data.get("modules", [])
    names: set[str] = set()
    if not isinstance(modules, list):
        return names

    for mod in modules:
        if isinstance(mod, dict):
            name = mod.get("name")
            if isinstance(name, str) and name.strip():
                names.add(name.strip().lower())
    return names


def _dependency_edges_from_rules(rules: dict[str, Any]) -> list[tuple[str, str]]:
    modules = rules.get("boundaries", {}).get("modules", {})
    edges: list[tuple[str, str]] = []

    if not isinstance(modules, dict):
        return edges

    for source, data in modules.items():
        if not isinstance(source, str) or not source.strip():
            continue
        if not isinstance(data, dict):
            continue
        touches = data.get("touches", [])
        if not isinstance(touches, list):
            continue
        for target in touches:
            if isinstance(target, str) and target.strip():
                edges.append((source.strip().lower(), target.strip().lower()))
    return edges


def _dependency_edges_from_map(map_data: dict[str, Any]) -> list[tuple[str, str]]:
    deps = map_data.get("dependencies", [])
    edges: list[tuple[str, str]] = []

    if not isinstance(deps, list):
        return edges

    for dep in deps:
        if not isinstance(dep, dict):
            continue
        source = dep.get("from")
        target = dep.get("to")
        if isinstance(source, str) and source.strip() and isinstance(target, str) and target.strip():
            edges.append((source.strip().lower(), target.strip().lower()))
    return edges


def _dependency_stats(edges: list[tuple[str, str]]) -> tuple[int, int, int]:
    if not edges:
        return 0, 0, 0

    fanout: dict[str, int] = {}
    fanin: dict[str, int] = {}
    for source, target in edges:
        fanout[source] = fanout.get(source, 0) + 1
        fanin[target] = fanin.get(target, 0) + 1

    return len(edges), max(fanout.values(), default=0), max(fanin.values(), default=0)


def _cross_impact_run_count(expect: dict[str, Any], touch_threshold: int) -> int:
    runbook = expect.get("runbook", [])
    if not isinstance(runbook, list):
        return 0

    count = 0
    for run in runbook:
        if not isinstance(run, dict):
            continue
        touches = run.get("touches", [])
        if not isinstance(touches, list):
            continue
        breadth = {
            str(item).strip().lower()
            for item in touches
            if str(item).strip()
        }
        if len(breadth) >= touch_threshold:
            count += 1
    return count


def _broad_impact_rule_count(map_data: dict[str, Any], check_threshold: int) -> int:
    impact_rules = map_data.get("impact", [])
    if not isinstance(impact_rules, list):
        return 0

    broad = 0
    for rule in impact_rules:
        if not isinstance(rule, dict):
            continue
        checks = rule.get("check", [])
        if not isinstance(checks, list):
            continue
        normalized = {
            str(check).strip().lower()
            for check in checks
            if str(check).strip()
        }
        if len(normalized) >= check_threshold:
            broad += 1
    return broad


def _shared_integrations_count(map_data: dict[str, Any], used_by_threshold: int) -> int:
    external = map_data.get("external", [])
    if not isinstance(external, list):
        return 0

    shared = 0
    for item in external:
        if not isinstance(item, dict):
            continue
        used_by = item.get("used_by", [])
        if not isinstance(used_by, list):
            continue
        users = {
            str(module).strip().lower()
            for module in used_by
            if str(module).strip()
        }
        if len(users) >= used_by_threshold:
            shared += 1
    return shared


def evaluate_map_complexity(project_dir: str | Path) -> MapComplexityAssessment:
    """Evaluate whether map.yaml is required by project complexity signals."""
    project = Path(project_dir).resolve()

    expect_path = resolve_frame_file(project, "expect.yaml")
    rules_path = resolve_frame_file(project, "rules.yaml", "mind.yaml")
    facts_path = resolve_frame_file(project, "facts.yaml", "brain.yaml")
    map_path = resolve_frame_file(project, "map.yaml")

    expect = load_yaml(str(expect_path)) if expect_path else {}
    rules = load_yaml(str(rules_path)) if rules_path else {}
    facts = load_yaml(str(facts_path)) if facts_path else {}
    map_data = load_yaml(str(map_path)) if map_path else {}

    planning = expect.get("planning", {}) if isinstance(expect, dict) else {}
    map_policy = expect.get("map_policy", {}) if isinstance(expect, dict) else {}

    project_size = str(planning.get("project_size", "small")).lower()
    estimated_runs = _int_or_default(planning.get("estimated_runs"), 1)
    declared_map_required = planning.get("map_required")
    if not isinstance(declared_map_required, bool):
        declared_map_required = None

    small_max_runs = _int_or_default(
        map_policy.get("small_project_max_runs"),
        DEFAULT_SMALL_MAX_RUNS,
    )
    medium_max_runs = _int_or_default(
        map_policy.get("medium_project_max_runs"),
        DEFAULT_MEDIUM_MAX_RUNS,
    )
    module_threshold = _int_or_default(
        map_policy.get("module_threshold"),
        DEFAULT_MODULE_THRESHOLD,
    )
    cross_touch_threshold = _int_or_default(
        map_policy.get("cross_impact_touch_threshold"),
        DEFAULT_CROSS_IMPACT_TOUCH_THRESHOLD,
    )
    cross_run_threshold = _int_or_default(
        map_policy.get("cross_impact_run_threshold"),
        DEFAULT_CROSS_IMPACT_RUN_THRESHOLD,
    )
    dependency_fanout_threshold = _int_or_default(
        map_policy.get("dependency_fanout_threshold"),
        DEFAULT_DEPENDENCY_FANOUT_THRESHOLD,
    )
    impact_check_threshold = _int_or_default(
        map_policy.get("impact_check_threshold"),
        DEFAULT_IMPACT_CHECK_THRESHOLD,
    )
    shared_integration_threshold = _int_or_default(
        map_policy.get("shared_integration_module_threshold"),
        DEFAULT_SHARED_INTEGRATION_MODULE_THRESHOLD,
    )

    module_names = set()
    module_names.update(_module_names_from_facts(facts))
    module_names.update(_module_names_from_rules(rules))
    module_names.update(_module_names_from_map(map_data))
    module_count = len(module_names)

    cross_impact_runs = _cross_impact_run_count(expect, cross_touch_threshold)

    map_edges = _dependency_edges_from_map(map_data)
    rule_edges = _dependency_edges_from_rules(rules)
    edges = map_edges if map_edges else rule_edges
    dependency_edges, max_fanout, max_fanin = _dependency_stats(edges)

    broad_impact_rules = _broad_impact_rule_count(map_data, impact_check_threshold)
    shared_integrations = _shared_integrations_count(map_data, shared_integration_threshold)

    db_type = str(facts.get("database", {}).get("type", "")).strip().lower()
    shared_database_signal = (
        db_type not in ("", "none")
        and module_count >= shared_integration_threshold
        and dependency_edges > 0
    )

    run_complexity = False
    if project_size == "small":
        run_complexity = estimated_runs > small_max_runs
    elif project_size == "medium":
        run_complexity = estimated_runs > medium_max_runs
    elif project_size == "large":
        run_complexity = estimated_runs > 0
    else:
        run_complexity = estimated_runs > medium_max_runs

    module_complexity = module_count >= module_threshold
    cross_run_complexity = cross_impact_runs >= cross_run_threshold
    dependency_complexity = max(max_fanout, max_fanin) >= dependency_fanout_threshold
    impact_complexity = broad_impact_rules >= cross_run_threshold
    integration_complexity = shared_integrations > 0 or shared_database_signal

    required = any(
        (
            run_complexity,
            module_complexity,
            cross_run_complexity,
            dependency_complexity,
            impact_complexity,
            integration_complexity,
        )
    )

    reasons: list[str] = []
    if run_complexity:
        reasons.append(
            f"estimated_runs={estimated_runs} exceeds {project_size} threshold"
        )
    if module_complexity:
        reasons.append(
            f"module_count={module_count} meets/exceeds threshold {module_threshold}"
        )
    if cross_run_complexity:
        reasons.append(
            f"cross-impact runs={cross_impact_runs} (touching >= {cross_touch_threshold} areas)"
        )
    if dependency_complexity:
        reasons.append(
            f"dependency fanout/fanin is high (fanout={max_fanout}, fanin={max_fanin})"
        )
    if impact_complexity:
        reasons.append(f"broad impact rules={broad_impact_rules}")
    if integration_complexity:
        if shared_integrations > 0:
            reasons.append(
                f"shared integrations detected={shared_integrations}"
            )
        if shared_database_signal:
            reasons.append("database is shared across multiple dependent modules")

    return MapComplexityAssessment(
        required=required,
        has_map=bool(map_path),
        declared_map_required=declared_map_required,
        project_size=project_size,
        estimated_runs=estimated_runs,
        module_count=module_count,
        cross_impact_runs=cross_impact_runs,
        dependency_edges=dependency_edges,
        max_dependency_fanout=max_fanout,
        max_dependency_fanin=max_fanin,
        broad_impact_rules=broad_impact_rules,
        shared_integrations=shared_integrations,
        shared_database_signal=shared_database_signal,
        reasons=reasons,
    )


def map_complexity_issues(
    assessment: MapComplexityAssessment,
) -> tuple[list[str], list[str]]:
    """Return (errors, warnings) based on map complexity policy compliance."""
    errors: list[str] = []
    warnings: list[str] = []

    if assessment.required and not assessment.has_map:
        errors.append("map.yaml is required by module/cross-impact complexity but is missing")

    if assessment.declared_map_required is None:
        warnings.append("expect.planning.map_required is unset; set it explicitly")
    elif not assessment.declared_map_required and assessment.required:
        errors.append(
            "expect.planning.map_required=false but complexity check requires map.yaml"
        )
    elif assessment.declared_map_required and not assessment.required:
        warnings.append(
            "expect.planning.map_required=true but complexity check says map is optional"
        )

    return errors, warnings


def format_map_complexity_summary(assessment: MapComplexityAssessment) -> str:
    """Format a single-line map complexity snapshot."""
    return (
        f"map_required(computed)={assessment.required_state}; "
        f"declared={assessment.declared_state}; "
        f"modules={assessment.module_count}; "
        f"cross_impact_runs={assessment.cross_impact_runs}; "
        f"dependency_edges={assessment.dependency_edges}; "
        f"shared_integrations={assessment.shared_integrations}"
    )
