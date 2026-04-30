"""Supervisor-level checks used by CLI and MCP surfaces."""

from pathlib import Path

from haxaml.map_policy import (
    evaluate_map_complexity,
    map_complexity_issues,
    format_map_complexity_summary,
)
from haxaml.paths import resolve_frame_file
from haxaml.validator import load_yaml


def render_needs(project_dir: str) -> str:
    """List what the user/agent still needs to provide before safe building."""
    p = Path(project_dir).resolve()
    lines = []

    facts_path = resolve_frame_file(p, "facts.yaml", "brain.yaml")
    if facts_path:
        facts = load_yaml(str(facts_path))
        unresolved = facts.get("unresolved", [])
        blocking = [u for u in unresolved if u.get("blocking")]
        non_blocking = [u for u in unresolved if not u.get("blocking")]

        if blocking:
            lines.append("## Blocking — must resolve before building\n")
            for item in blocking:
                lines.append(f"- {item['item']}: {item.get('reason', '')}")

        if non_blocking:
            lines.append("\n## Non-blocking — can resolve later\n")
            for item in non_blocking:
                lines.append(f"- {item['item']}: {item.get('reason', '')}")
    else:
        lines.append("⚠ facts.yaml not found")

    acts_path = resolve_frame_file(p, "acts.yaml", "state.yaml")
    if acts_path:
        acts = load_yaml(str(acts_path))
        expect_sync = acts.get("expect_sync", {})
        if isinstance(expect_sync, dict) and bool(expect_sync.get("required")):
            lines.append("\n## Blocking lifecycle sync\n")
            lines.append("- expect.yaml is out of date for the latest recorded run.")
            pending_run = str(expect_sync.get("pending_run_id", "") or "")
            pending_task = str(expect_sync.get("pending_task", "") or "")
            pending_result = str(expect_sync.get("pending_result", "") or "")
            if pending_run or pending_task or pending_result:
                lines.append(
                    f"- Pending record: run={pending_run or '?'} task={pending_task or '?'} result={pending_result or '?'}"
                )
            lines.append("- Required action: call haxaml_expect_sync(project_dir='.')")

        deps = acts.get("unresolved_dependencies", [])
        blocking_deps = [d for d in deps if d.get("blocking")]
        if blocking_deps:
            lines.append("\n## Blocked dependencies\n")
            for dep in blocking_deps:
                lines.append(f"- {dep['item']} (owner: {dep.get('owner', '?')})")

    expect_path = resolve_frame_file(p, "expect.yaml")
    if expect_path:
        expect = load_yaml(str(expect_path))
        runbook = expect.get("runbook", [])
        active_runs = [r for r in runbook if r.get("status") == "active"]
        if active_runs:
            lines.append("\n## Active run requirements\n")
            for run in active_runs:
                requires = run.get("requires", [])
                if requires:
                    lines.append(f"Run {run.get('run', '?')} ({run.get('goal', '')}):")
                    for req in requires:
                        lines.append(f"  - {req}")

        questions = expect.get("open_questions", [])
        blocking_q = [q for q in questions if q.get("blocking")]
        if blocking_q:
            lines.append("\n## Blocking questions\n")
            for q in blocking_q:
                lines.append(f"- {q['question']}")

    map_assessment = evaluate_map_complexity(p)
    map_errors, map_warnings = map_complexity_issues(map_assessment)
    if map_errors:
        lines.append("\n## Map policy — blocking\n")
        for err in map_errors:
            lines.append(f"- {err}")
        for reason in map_assessment.reasons:
            lines.append(f"- complexity signal: {reason}")
    elif map_warnings:
        lines.append("\n## Map policy — warnings\n")
        for warning in map_warnings:
            lines.append(f"- {warning}")
    lines.append(f"\n## Map complexity snapshot\n- {format_map_complexity_summary(map_assessment)}")

    if not lines:
        return "✓ No blocking needs — ready to build"
    return "\n".join(lines)


def render_impact(module: str, project_dir: str) -> str:
    """Show what is affected by changing a module, using map.yaml."""
    p = Path(project_dir).resolve()
    map_path = resolve_frame_file(p, "map.yaml")
    map_assessment = evaluate_map_complexity(p)
    if not map_path:
        details = format_map_complexity_summary(map_assessment)
        if map_assessment.required:
            reasons = "\n".join(f"  → {r}" for r in map_assessment.reasons) or "  → no reasons recorded"
            return (
                "✗ map.yaml not found — required by complexity policy.\n"
                f"{details}\n"
                "Create .haxaml/map.yaml and define module ownership/dependencies first.\n"
                "Complexity signals:\n"
                f"{reasons}"
            )
        return (
            "⚠ map.yaml not found — no module map defined.\n"
            f"{details}\n"
            "Create .haxaml/map.yaml to track module boundaries."
        )

    map_data = load_yaml(str(map_path))
    modules = map_data.get("modules", [])
    deps = map_data.get("dependencies", [])
    impact_rules = map_data.get("impact", [])

    target = None
    for mod in modules:
        if mod.get("name", "").lower() == module.lower():
            target = mod
            break

    if not target:
        available = [m.get("name", "?") for m in modules]
        return (
            f"✗ Module '{module}' not found in map.yaml.\n"
            f"Available: {', '.join(available)}"
        )

    lines = [f"## Module: {target['name']}"]

    if target.get("purpose"):
        lines.append(f"Purpose: {target['purpose']}")

    files = target.get("files", [])
    if files:
        lines.append(f"\nOwns: {', '.join(files)}")

    depends_on = [d for d in deps if d.get("from", "").lower() == module.lower()]
    depended_by = [d for d in deps if d.get("to", "").lower() == module.lower()]

    if depends_on:
        lines.append("\nDepends on:")
        for dep in depends_on:
            reason = f" ({dep['reason']})" if dep.get("reason") else ""
            lines.append(f"  → {dep['to']}{reason}")

    if depended_by:
        lines.append("\nDepended on by:")
        for dep in depended_by:
            reason = f" ({dep['reason']})" if dep.get("reason") else ""
            lines.append(f"  ← {dep['from']}{reason}")

    matching_rules = [
        rule for rule in impact_rules
        if rule.get("when", "").lower() == module.lower()
    ]
    if matching_rules:
        lines.append("\nImpact rules — when this module changes, check:")
        for rule in matching_rules:
            for check in rule.get("check", []):
                lines.append(f"  → {check}")

    if not depends_on and not depended_by and not matching_rules:
        lines.append("\nNo dependencies or impact rules defined for this module.")

    return "\n".join(lines)
