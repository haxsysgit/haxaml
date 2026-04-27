"""Haxaml MCP Server — exposes FRAME governance as MCP tools and resources.

Tools let AI agents manage FRAME governance natively during conversations.
Resources provide read-only access to current FRAME state.

Usage:
    haxaml-mcp                          # stdio transport (default)
    haxaml mcp                          # same, via CLI
    HAXAML_PROJECT_DIR=/path haxaml-mcp # explicit project directory
"""

import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from haxaml.paths import frame_dir, frame_path, resolve_frame_file
from haxaml.validator import (
    validate_facts, validate_rules, validate_acts, validate_expect,
    validate_map, detect_missing_facts_fields,
)
from haxaml.context import build_context, count_tokens
from haxaml.map_policy import (
    evaluate_map_complexity,
    map_complexity_issues,
    format_map_complexity_summary,
)
from haxaml.runner import ExecutionRunner
from haxaml.state_manager import StateManager, StateError
from haxaml.supervision import render_impact, render_needs
from haxaml.adoption import (
    scan_native_sources, render_adoption_report, write_adoption_scaffold,
)
from haxaml.export_engine import (
    export_to_file, list_agents,
)
from haxaml.auto_export import export_if_stale
from haxaml.init_templates import write_init_templates


mcp_app = FastMCP(
    "haxaml",
    instructions=(
        "Deterministic FRAME governance for AI-assisted development. "
        "Plan first, then build. Use FRAME as your project journal."
    ),
)


def _project() -> Path:
    """Resolve the project directory from HAXAML_PROJECT_DIR env or CWD."""
    return Path(os.environ.get("HAXAML_PROJECT_DIR", ".")).resolve()


# ─── Tools ───────────────────────────────────────────────────────────────────


@mcp_app.tool()
def haxaml_init(directory: str = ".") -> str:
    """Initialize FRAME governance files in a project directory.

    Creates .haxaml/ with template facts.yaml, rules.yaml, acts.yaml,
    and expect.yaml. The AI agent should fill these in before building.
    """
    project_dir = Path(directory).resolve()
    project_dir.mkdir(parents=True, exist_ok=True)
    haxaml_root = frame_dir(project_dir)
    haxaml_root.mkdir(parents=True, exist_ok=True)

    facts_p = frame_path(project_dir, "facts.yaml")
    if facts_p.exists():
        return f"⚠ facts.yaml already exists at {facts_p}. Use haxaml_validate to check it."

    write_init_templates(project_dir)

    stale = export_if_stale(str(project_dir))
    re_export_msg = ""
    if stale:
        re_export_msg = f"\n  ↻ Auto-exported {len(stale)} agent file(s)"

    return (
        f"✓ Initialized FRAME at {haxaml_root}\n"
        f"  → .haxaml/facts.yaml — fill in project truth\n"
        f"  → .haxaml/rules.yaml — define agent rules\n"
        f"  → .haxaml/acts.yaml — diary starts here\n"
        f"  → .haxaml/expect.yaml — plan your runs\n"
        f"  → Call haxaml_validate when ready{re_export_msg}"
    )


@mcp_app.tool()
def haxaml_validate(project_dir: str = ".") -> str:
    """Validate all FRAME files against schemas.

    Checks facts.yaml, rules.yaml, acts.yaml, expect.yaml, and map.yaml.
    Returns validation results for each file.
    """
    p = Path(project_dir).resolve()
    lines = []
    all_valid = True

    checks = [
        ("facts.yaml", "brain.yaml", validate_facts),
        ("rules.yaml", "mind.yaml", validate_rules),
        ("acts.yaml", "state.yaml", validate_acts),
    ]

    for new_name, old_name, validator_fn in checks:
        path = resolve_frame_file(p, new_name, old_name)
        if path:
            errors = validator_fn(str(path))
            if errors:
                lines.append(f"✗ {new_name}: {len(errors)} error(s)")
                for e in errors:
                    lines.append(f"  → {e}")
                all_valid = False
            else:
                lines.append(f"✓ {new_name} is valid")
        else:
            if new_name == "facts.yaml":
                lines.append(f"✗ {new_name} not found")
                all_valid = False
            else:
                lines.append(f"⚠ {new_name} not found (optional)")

    expect_path = resolve_frame_file(p, "expect.yaml")
    if expect_path:
        errors = validate_expect(str(expect_path))
        if errors:
            lines.append(f"✗ expect.yaml: {len(errors)} error(s)")
            for e in errors:
                lines.append(f"  → {e}")
            all_valid = False
        else:
            lines.append("✓ expect.yaml is valid")

    map_path = resolve_frame_file(p, "map.yaml")
    if map_path:
        errors = validate_map(str(map_path))
        if errors:
            lines.append(f"✗ map.yaml: {len(errors)} error(s)")
            for e in errors:
                lines.append(f"  → {e}")
            all_valid = False
        else:
            lines.append("✓ map.yaml is valid")

    assessment = evaluate_map_complexity(p)
    map_errors, map_warnings = map_complexity_issues(assessment)
    lines.append(f"• Map complexity: {format_map_complexity_summary(assessment)}")
    if map_errors:
        for err in map_errors:
            lines.append(f"✗ map policy: {err}")
        if assessment.reasons:
            for reason in assessment.reasons:
                lines.append(f"  → complexity signal: {reason}")
        all_valid = False
    if map_warnings:
        for warning in map_warnings:
            lines.append(f"⚠ map policy: {warning}")

    if all_valid:
        lines.append("\n✓ All FRAME files valid")
    else:
        lines.append("\n✗ Validation failed — fix errors above")

    return "\n".join(lines)


@mcp_app.tool()
def haxaml_context(project_dir: str = ".", include_state: bool = True) -> str:
    """Get the current project context for the AI agent.

    Returns a compact summary of facts, rules, acts, and expect.
    This is what the agent reads to understand the project.
    """
    ctx = build_context(project_dir, include_state=include_state)
    tokens = count_tokens(ctx)
    return f"{ctx}\n\n--- Token count: {tokens} ---"


@mcp_app.tool()
def haxaml_health(project_dir: str = ".") -> str:
    """Get project health report.

    Shows validation status, state summary, token count, errors and warnings.
    """
    try:
        runner = ExecutionRunner(project_dir)
    except FileNotFoundError as e:
        return f"✗ {e}"

    report = runner.get_project_health()
    lines = [
        f"Project:    {report['project']}",
        f"Ready:      {'✓' if report['ready'] else '✗'}",
        f"Facts:      {'✓ valid' if report['facts_valid'] else '✗ invalid'}",
        f"Acts:       {'✓ valid' if report['acts_valid'] else '✗ invalid'}",
        f"Complete:   {'✓' if report['facts_complete'] else '✗ incomplete'}",
        f"Context:    {report['context_tokens']} tokens",
    ]

    p = Path(project_dir).resolve()
    rules_path = resolve_frame_file(p, "rules.yaml", "mind.yaml")
    if rules_path:
        errors = validate_rules(str(rules_path))
        lines.append(f"Rules:      {'✓ valid' if not errors else '✗ invalid'}")

    expect_path = resolve_frame_file(p, "expect.yaml")
    if expect_path:
        errors = validate_expect(str(expect_path))
        lines.append(f"Expect:     {'✓ valid' if not errors else '✗ invalid'}")

    map_path = resolve_frame_file(p, "map.yaml")
    if map_path:
        errors = validate_map(str(map_path))
        lines.append(f"Map:        {'✓ valid' if not errors else '✗ invalid'}")

    map_assessment = evaluate_map_complexity(p)
    map_errors, map_warnings = map_complexity_issues(map_assessment)
    lines.append(f"Map policy: {format_map_complexity_summary(map_assessment)}")
    if map_assessment.reasons:
        lines.append("Map signals:")
        for reason in map_assessment.reasons:
            lines.append(f"  → {reason}")
    for err in map_errors:
        lines.append(f"  ✗ {err}")
    for warning in map_warnings:
        lines.append(f"  ⚠ {warning}")

    if report.get("phase"):
        lines.extend([
            f"Phase:      {report['phase']}",
            f"Active:     {report['active_task']}",
            f"Completed:  {report['completed_tasks']}",
            f"Blocked:    {report['blocked_tasks']}",
            f"Total runs: {report['total_runs']}",
        ])

    if report["errors"]:
        lines.append(f"\n✗ {len(report['errors'])} error(s):")
        for e in report["errors"]:
            lines.append(f"  → {e}")

    if report["warnings"]:
        lines.append(f"\n⚠ {len(report['warnings'])} warning(s):")
        for w in report["warnings"]:
            lines.append(f"  → {w}")

    return "\n".join(lines)


@mcp_app.tool()
def haxaml_doctor(project_dir: str = ".") -> str:
    """Check facts completeness beyond schema validation.

    Finds missing recommended fields and blocking unresolved items.
    """
    p = Path(project_dir).resolve()
    facts_path = resolve_frame_file(p, "facts.yaml", "brain.yaml")
    if not facts_path:
        return "✗ facts.yaml not found"

    errors = validate_facts(str(facts_path))
    if errors:
        lines = ["✗ facts.yaml fails schema validation — fix these first:"]
        for e in errors:
            lines.append(f"  → {e}")
        return "\n".join(lines)

    missing = detect_missing_facts_fields(str(facts_path))
    if missing:
        lines = [f"⚠ {len(missing)} recommendation(s):"]
        for m in missing:
            lines.append(f"  → {m}")
        return "\n".join(lines)

    return "✓ facts.yaml is complete — no recommendations"


@mcp_app.tool()
def haxaml_run(task: str, description: str = "", project_dir: str = ".") -> str:
    """Start a governed execution run.

    Sets the active task in acts.yaml and runs preflight validation.
    Call this before starting work on a task.
    """
    try:
        runner = ExecutionRunner(project_dir)
    except FileNotFoundError as e:
        return f"✗ {e}"

    result = runner.start_run(task=task, description=description)
    if result.result == "failed":
        lines = ["✗ Run failed preflight:"]
        for e in result.errors:
            lines.append(f"  → {e}")
        return "\n".join(lines)

    lines = [f"✓ Run started: {task}"]
    if result.warnings:
        for w in result.warnings:
            lines.append(f"  ⚠ {w}")
    lines.append("  → Work on the task, then call haxaml_done to record results")
    return "\n".join(lines)


@mcp_app.tool()
def haxaml_done(
    task: str,
    result: str = "success",
    changes: str = "",
    decisions: str = "",
    risks: str = "",
    project_dir: str = ".",
) -> str:
    """Record task completion in the project diary (acts.yaml).

    Call this after finishing work on a task.

    Args:
        task: The task that was completed
        result: success, partial, or failed
        changes: Summary of what changed
        decisions: Key decisions made during this task
        risks: Any risks or concerns identified
    """
    try:
        runner = ExecutionRunner(project_dir)
    except FileNotFoundError as e:
        return f"✗ {e}"

    run_result = runner.finish_run(
        task=task, result=result, changes=changes,
        decisions=decisions, risks=risks,
    )

    if run_result.errors:
        lines = ["⚠ Run completed with errors:"]
        for e in run_result.errors:
            lines.append(f"  → {e}")
        return "\n".join(lines)

    lines = [f"✓ Run {run_result.run_id} recorded ({result})"]
    lines.append(f"  Context: {run_result.token_count} tokens")
    if run_result.warnings:
        for w in run_result.warnings:
            lines.append(f"  ⚠ {w}")

    stale = export_if_stale(project_dir)
    if stale:
        lines.append(f"  ↻ Auto re-exported {len(stale)} agent file(s)")

    return "\n".join(lines)


@mcp_app.tool()
def haxaml_export(agent: str = "generic", project_dir: str = ".") -> str:
    """Export FRAME to an agent-native markdown file.

    Generates CLAUDE.md, AGENTS.md, .cursor/rules/haxaml.mdc, etc.
    Use agent='all' to export for all supported agents.

    Supported agents: claude, codex, cursor, windsurf, copilot, gemini, generic
    """
    if agent == "all":
        lines = []
        for a in list_agents():
            path = export_to_file(project_dir, a["name"])
            lines.append(f"✓ {a['name']:10s} → {path}")
        return "\n".join(lines)

    try:
        path = export_to_file(project_dir, agent)
        return f"✓ Exported to {path}"
    except (ValueError, KeyError):
        available = ", ".join(a["name"] for a in list_agents())
        return f"✗ Unknown agent '{agent}'. Available: {available}"


@mcp_app.tool()
def haxaml_adopt(
    project_dir: str = ".",
    write: bool = False,
    force: bool = False,
) -> str:
    """Adopt an existing project into FRAME governance.

    Scans for native agent files (CLAUDE.md, AGENTS.md, .cursor/rules/, etc.)
    and repository context (README, package.json, etc.).

    With write=False (default): shows the adoption report (dry run).
    With write=True: creates .haxaml/ADOPTION.md and scaffold FRAME files.
    """
    plan = scan_native_sources(project_dir)

    if not write:
        report = render_adoption_report(plan)
        return f"{report}\n---\nDry run. Call with write=True to create files."

    written = write_adoption_scaffold(plan, force=force)
    if written:
        lines = []
        for path in written:
            lines.append(f"✓ wrote {path.relative_to(plan.project_dir)}")
        if plan.existing_frame_files and not force:
            lines.append(f"Preserved existing: {', '.join(plan.existing_frame_files)}")
        lines.append(
            "Next: fill in scaffold unknowns with real project facts, "
            "then call haxaml_validate"
        )
        return "\n".join(lines)

    return "No files written. Existing files preserved. Use force=True to overwrite."


@mcp_app.tool()
def haxaml_needs(project_dir: str = ".") -> str:
    """List what the user still needs to provide.

    Checks for blocking unresolved items in facts.yaml,
    blocking dependencies in acts.yaml, active run requirements
    in expect.yaml, and blocking open questions.
    """
    return render_needs(project_dir)


@mcp_app.tool()
def haxaml_impact(module: str, project_dir: str = ".") -> str:
    """Check what's affected by changing a module.

    Reads map.yaml to show module ownership, dependencies, and impact rules.
    This prevents the "fix kitchen, break bathroom" problem.
    """
    return render_impact(module, project_dir)


@mcp_app.tool()
def haxaml_state_show(project_dir: str = ".") -> str:
    """Show current project diary (acts.yaml) summary."""
    p = Path(project_dir).resolve()
    acts_path = resolve_frame_file(p, "acts.yaml", "state.yaml")
    if not acts_path:
        return "✗ acts.yaml not found"

    try:
        sm = StateManager(str(acts_path))
    except StateError as e:
        return f"✗ {e}"

    stats = sm.get_stats()
    return (
        f"Phase:      {stats['current_phase']}\n"
        f"Active:     {stats['active_task']}\n"
        f"Completed:  {stats['completed_count']}\n"
        f"Blocked:    {stats['blocked_count']}\n"
        f"Decisions:  {stats['decision_count']}\n"
        f"Unresolved: {stats['unresolved_count']}\n"
        f"Runs:       {stats['run_count']} (+ {stats['total_runs_compacted']} compacted)\n"
        f"File size:  {stats['file_size_bytes']} bytes"
    )


@mcp_app.tool()
def haxaml_state_compact(project_dir: str = ".", keep_recent: int = 5) -> str:
    """Compact old runs in acts.yaml to save context tokens.

    Summarizes old runs and keeps only the most recent ones.
    """
    p = Path(project_dir).resolve()
    acts_path = resolve_frame_file(p, "acts.yaml", "state.yaml")
    if not acts_path:
        return "✗ acts.yaml not found"

    try:
        sm = StateManager(str(acts_path))
        result = sm.compact(keep_recent=keep_recent)
    except StateError as e:
        return f"✗ {e}"

    return f"✓ Compacted {result['compacted']} runs, kept {result['kept']}"


@mcp_app.tool()
def haxaml_benchmark(project_dir: str = ".") -> str:
    """Run token efficiency benchmarks on FRAME files."""
    from haxaml.benchmarks import format_benchmark_report

    p = Path(project_dir).resolve()
    facts_path = resolve_frame_file(p, "facts.yaml", "brain.yaml")
    if not facts_path:
        return "✗ facts.yaml not found"

    return format_benchmark_report(str(facts_path), project_dir)


# ─── Resources ───────────────────────────────────────────────────────────────


@mcp_app.resource("haxaml://frame/facts")
def resource_facts() -> str:
    """Current project facts (FRAME: F)."""
    path = resolve_frame_file(_project(), "facts.yaml", "brain.yaml")
    if not path:
        return "# facts.yaml not found"
    return path.read_text(encoding="utf-8")


@mcp_app.resource("haxaml://frame/rules")
def resource_rules() -> str:
    """Current project rules (FRAME: R)."""
    path = resolve_frame_file(_project(), "rules.yaml", "mind.yaml")
    if not path:
        return "# rules.yaml not found"
    return path.read_text(encoding="utf-8")


@mcp_app.resource("haxaml://frame/acts")
def resource_acts() -> str:
    """Current project diary (FRAME: A)."""
    path = resolve_frame_file(_project(), "acts.yaml", "state.yaml")
    if not path:
        return "# acts.yaml not found"
    return path.read_text(encoding="utf-8")


@mcp_app.resource("haxaml://frame/expect")
def resource_expect() -> str:
    """Current project runbook (FRAME: E)."""
    path = resolve_frame_file(_project(), "expect.yaml")
    if not path:
        return "# expect.yaml not found"
    return path.read_text(encoding="utf-8")


@mcp_app.resource("haxaml://frame/map")
def resource_map() -> str:
    """Current module map (FRAME: M) — required when complexity policy says so."""
    path = resolve_frame_file(_project(), "map.yaml")
    if not path:
        assessment = evaluate_map_complexity(_project())
        state = "required" if assessment.required else "optional"
        return f"# map.yaml not found — {state} by current complexity policy"
    return path.read_text(encoding="utf-8")


@mcp_app.resource("haxaml://context")
def resource_context() -> str:
    """Compact project context for AI agent consumption."""
    return build_context(str(_project()))


# ─── Entry point ─────────────────────────────────────────────────────────────


def main():
    """Run the Haxaml MCP server (stdio transport)."""
    mcp_app.run()


if __name__ == "__main__":
    main()
