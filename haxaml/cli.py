"""Haxaml CLI — deterministic agent-management tooling for FRAME."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import click

from haxaml.state_manager import StateManager
from haxaml.brain_builder import interactive_build
from haxaml.benchmarks import format_benchmark_report
from haxaml.paths import frame_path, resolve_frame_file
from haxaml.versioning import MCP_LAUNCHER_PACKAGE, PACKAGE_NAME, get_version, version_spec


@click.group()
@click.version_option(version=get_version())
def cli():
    """Haxaml — deterministic FRAME tooling for AI-assisted development."""
    pass


def _mcp_tools():
    """Load MCP tool implementations used as thin CLI backends."""
    try:
        from haxaml import mcp_server
    except ImportError:
        click.echo("✗ MCP support requires the 'mcp' package.")
        click.echo("  Install with: pip install haxaml")
        sys.exit(1)
    return mcp_server


def _result_dict(result):
    """Return a MCP-style result dict when one is available."""
    return result if isinstance(result, dict) else None


def _is_failure(result: str) -> bool:
    result_dict = _result_dict(result)
    if result_dict is not None:
        return result_dict.get("ok") is False
    text = (result or "").strip()
    if not text:
        return False
    if text.startswith("✗"):
        return True
    return "Validation failed" in text


def _result_text(result) -> str:
    result_dict = _result_dict(result)
    if result_dict is not None:
        data = result_dict.get("data") if isinstance(result_dict.get("data"), dict) else {}
        if data.get("message"):
            return str(data["message"])
        error = result_dict.get("error") if isinstance(result_dict.get("error"), dict) else {}
        details = error.get("details") if isinstance(error.get("details"), dict) else {}
        if details.get("message"):
            return str(details["message"])
        if error.get("message"):
            return str(error["message"])
        return json.dumps(result_dict, indent=2, sort_keys=True)
    return str(result or "")


def _echo_tool_result(result, *, exit_on_failure: bool = True) -> None:
    """Print a MCP/CLI result consistently and optionally fail fast."""
    click.echo(_result_text(result))
    if exit_on_failure and _is_failure(result):
        sys.exit(1)


@cli.command()
@click.argument("directory", default=".")
def init(directory):
    """Initialize FRAME governance files in DIRECTORY."""
    _echo_tool_result(_mcp_tools().haxaml_init(directory), exit_on_failure=False)


@cli.command()
@click.option("--dir", "project_dir", default=".", help="Project directory")
def validate(project_dir):
    """Validate FRAME files against schemas."""
    _echo_tool_result(_mcp_tools().haxaml_validate(project_dir))


def _resolve(project: Path, new_name: str, old_name: str) -> Path | None:
    """Resolve FRAME filename with backward compat fallback."""
    return resolve_frame_file(project, new_name, old_name)


@cli.command()
@click.option("--dir", "project_dir", default=".", help="Project directory")
def doctor(project_dir):
    """Check facts completeness beyond schema validation."""
    _echo_tool_result(_mcp_tools().haxaml_doctor(project_dir))


@cli.command()
@click.option("--to", "target_version", default=None, help="Target version (default: latest).")
@click.option("--include-mcp/--no-include-mcp", default=True, help="Upgrade haxaml-mcp too.")
@click.option("--dry-run", is_flag=True, help="Print the upgrade command without executing it.")
def upgrade(target_version, include_mcp, dry_run):
    """Upgrade Haxaml with uv tool management."""
    if not shutil.which("uv"):
        click.echo("✗ `uv` is required for upgrade. Install uv first: https://docs.astral.sh/uv/")
        sys.exit(1)

    specs = [version_spec(PACKAGE_NAME, target_version)]
    if include_mcp:
        specs.append(version_spec(MCP_LAUNCHER_PACKAGE, target_version))

    upgrade_cmd = ["uv", "tool", "upgrade", *specs]
    if dry_run:
        click.echo(f"Dry run:\n  {' '.join(upgrade_cmd)}")
        return

    first = subprocess.run(upgrade_cmd, capture_output=True, text=True)
    if first.returncode == 0:
        click.echo("✓ Upgrade complete via `uv tool upgrade`.")
        output = (first.stdout or "").strip()
        if output:
            click.echo(output)
        return

    # Fallback: install/upgrade tools when upgrade fails because a tool was not previously installed.
    failures = []
    for spec in specs:
        cmd = ["uv", "tool", "install", "--upgrade", spec]
        step = subprocess.run(cmd, capture_output=True, text=True)
        if step.returncode != 0:
            failures.append((spec, (step.stderr or step.stdout or "").strip()))

    if failures:
        click.echo("✗ Upgrade failed.")
        for spec, error in failures:
            click.echo(f"  - {spec}: {error or 'unknown error'}")
        sys.exit(1)

    click.echo("✓ Upgrade complete via fallback install flow.")


@cli.command()
@click.option("--dir", "project_dir", default=".", help="Project directory")
@click.option("--no-state", is_flag=True, help="Exclude state from context")
@click.option("--tokens", is_flag=True, help="Show token count")
def context(project_dir, no_state, tokens):
    """Output minimal context for an AI agent."""
    result = _mcp_tools().haxaml_context(project_dir, include_state=not no_state)
    rendered = _result_text(result)
    if tokens:
        click.echo(rendered)
        return
    marker = "\n\n--- Token count:"
    base = rendered.split(marker, 1)[0]
    click.echo(base)


@cli.command()
@click.option("--output", default=".haxaml/facts.yaml", help="Output path for facts.yaml")
def build(output):
    """Interactively build a facts.yaml with guided questions."""
    interactive_build(output_path=output)


@cli.command()
@click.argument("intent")
@click.option("--output", default="facts.draft.yaml", help="Output path for draft facts")
def derive(intent, output):
    """Derive a draft facts.yaml from a natural language intent string."""
    from haxaml.brain_builder import derive_facts_from_intent, write_facts
    facts = derive_facts_from_intent(intent)
    write_facts(facts, output)
    click.echo(f"✓ Draft facts written to {output}")

    unresolved = facts.get("unresolved", [])
    blocking = [u for u in unresolved if u.get("blocking", False)]
    if blocking:
        click.echo(f"\n⚠ {len(blocking)} blocking item(s) need resolution:")
        for u in blocking:
            click.echo(f"  → {u['item']}: {u.get('reason', '')}")
    click.echo(f"\nEdit the draft, then run `haxaml validate` to check it.")


@cli.command()
@click.option("--dir", "project_dir", default=".", help="Project directory")
@click.option("--from-native", "from_native", is_flag=True,
              help="Adopt from native AI-agent files and repository context")
@click.option("--write", "write_files", is_flag=True,
              help="Write .haxaml/ADOPTION.md and missing FRAME files")
@click.option("--force", is_flag=True,
              help="Overwrite existing adoption report and FRAME files")
def adopt(project_dir, from_native, write_files, force):
    """Adopt an existing project into FRAME governance."""
    if not from_native:
        click.echo("✗ Only native-file adoption is supported right now. Use `haxaml adopt --from-native`.")
        sys.exit(1)
    _echo_tool_result(_mcp_tools().haxaml_adopt(project_dir=project_dir, write=write_files, force=force))


@cli.command("adopt-plan")
@click.option("--dir", "project_dir", default=".", help="Project directory")
def adopt_plan(project_dir):
    """Inventory native/context files and show non-destructive adoption plan."""
    _echo_tool_result(_mcp_tools().haxaml_adopt_plan(project_dir=project_dir))


@cli.command()
@click.option("--dir", "project_dir", default=".", help="Project directory")
def reconcile(project_dir):
    """Check derivation boundaries and return conflict report."""
    _echo_tool_result(_mcp_tools().haxaml_reconcile(project_dir=project_dir))


@cli.command()
@click.option("--dir", "project_dir", default=".", help="Project directory")
def needs(project_dir):
    """List what still needs user/agent input before safe building."""
    _echo_tool_result(_mcp_tools().haxaml_needs(project_dir), exit_on_failure=False)


@cli.command()
@click.argument("module")
@click.option("--dir", "project_dir", default=".", help="Project directory")
def impact(module, project_dir):
    """Show what is affected when changing a module."""
    click.echo(_result_text(_mcp_tools().haxaml_impact(module, project_dir)))


@cli.group()
def state():
    """State management commands."""
    pass


@state.command("show")
@click.option("--path", default=None, help="Path to acts.yaml")
def state_show(path):
    """Show current acts summary."""
    if path:
        if not os.path.exists(path):
            click.echo(f"✗ acts.yaml not found at {path}")
            sys.exit(1)
        sm = StateManager(path)
        stats = sm.get_stats()
        click.echo(f"Phase:      {stats['current_phase']}")
        click.echo(f"Active:     {stats['active_task']}")
        click.echo(f"Completed:  {stats['completed_count']}")
        click.echo(f"Blocked:    {stats['blocked_count']}")
        click.echo(f"Decisions:  {stats['decision_count']}")
        click.echo(f"Unresolved: {stats['unresolved_count']}")
        click.echo(f"Runs:       {stats['run_count']} (+ {stats['total_runs_compacted']} compacted)")
        click.echo(f"File size:  {stats['file_size_bytes']} bytes")
        return

    result = _mcp_tools().haxaml_state_show(".")
    click.echo(_result_text(result))
    if _is_failure(result):
        sys.exit(1)


@state.command("compact")
@click.option("--path", default=None, help="Path to acts.yaml")
@click.option("--keep", default=5, help="Number of recent runs to keep")
def state_compact(path, keep):
    """Compact old runs into a summary."""
    if path:
        if not os.path.exists(path):
            click.echo(f"✗ acts.yaml not found at {path}")
            sys.exit(1)
        sm = StateManager(path)
        result = sm.compact(keep_recent=keep)
        click.echo(f"✓ Compacted {result['compacted']} runs, kept {result['kept']}")
        return

    result = _mcp_tools().haxaml_state_compact(".", keep_recent=keep)
    click.echo(_result_text(result))
    if _is_failure(result):
        sys.exit(1)


@state.command("record")
@click.option("--path", default=None, help="Path to acts.yaml")
@click.option("--task", required=True, help="Task description")
@click.option("--result", "run_result", required=True,
              type=click.Choice(["success", "partial", "failed"]))
@click.option("--changes", default="", help="Summary of changes")
@click.option("--decisions", default="", help="Key decisions made")
@click.option("--risks", default="", help="Identified risks")
def state_record(path, task, run_result, changes, decisions, risks):
    """Record a completed run."""
    path = path or str(resolve_frame_file(".", "acts.yaml", "state.yaml") or frame_path(".", "acts.yaml"))
    if not os.path.exists(path):
        click.echo(f"✗ acts.yaml not found at {path}")
        sys.exit(1)

    sm = StateManager(path)
    run_id = sm.record_run(task=task, result=run_result, changes=changes,
                           decisions=decisions, risks=risks)
    click.echo(f"✓ Recorded run {run_id}")


@cli.command()
@click.option("--dir", "project_dir", default=".", help="Project directory")
def health(project_dir):
    """Show project health report."""
    _echo_tool_result(_mcp_tools().haxaml_health(project_dir))


@cli.command()
@click.option("--dir", "project_dir", default=".", help="Project directory")
def about(project_dir):
    """Load Haxaml/FRAME onboarding brief (mandatory first call for lifecycle tools)."""
    _echo_tool_result(_mcp_tools().haxaml_about(project_dir=project_dir))


@cli.command()
@click.option("--facts", "facts_path", default=None, help="Path to facts.yaml")
@click.option("--dir", "project_dir", default=".", help="Project directory for full report")
@click.option("--mode", default="frame", type=click.Choice(["frame", "workflow"]), help="Benchmark mode")
def benchmark(facts_path, project_dir, mode):
    """Run token efficiency benchmarks."""
    if facts_path is not None:
        if not os.path.exists(facts_path):
            click.echo(f"✗ facts file not found at {facts_path}")
            sys.exit(1)
        report = format_benchmark_report(facts_path, project_dir)
        click.echo(report)
        return

    _echo_tool_result(_mcp_tools().haxaml_benchmark(project_dir=project_dir, mode=mode))


@cli.command()
@click.option("--dir", "project_dir", default=".", help="Project directory")
@click.option("--task", required=True, help="Task description")
def guidance(project_dir, task):
    """Generate structured task guidance and clarification needs."""
    _echo_tool_result(_mcp_tools().haxaml_guidance(task=task, project_dir=project_dir))


@cli.command("prebuild")
@click.option("--dir", "project_dir", default=".", help="Project directory")
@click.option("--task", required=True, help="Task description")
@click.option("--description", default="", help="Optional task description")
def prebuild(project_dir, task, description):
    """Classify task, run semantic validation, and open a governed prebuild session."""
    _echo_tool_result(_mcp_tools().haxaml_prebuild(task=task, description=description, project_dir=project_dir))


@cli.command("session-start")
@click.option("--dir", "project_dir", default=".", help="Project directory")
@click.option("--task", required=True, help="Task to execute")
@click.option("--description", default="", help="Task description")
def session_start(project_dir, task, description):
    """Start a governed session manually (advanced/manual path)."""
    _echo_tool_result(_mcp_tools().haxaml_session_start(task=task, description=description, project_dir=project_dir))


@cli.command("session-plan")
@click.option("--dir", "project_dir", default=".", help="Project directory")
@click.option("--session-id", required=True, help="Session ID from session-start")
def session_plan(project_dir, session_id):
    """Generate a session plan manually after session-start (advanced/manual path)."""
    _echo_tool_result(_mcp_tools().haxaml_session_plan(session_id=session_id, project_dir=project_dir))


@cli.command("context-pack")
@click.option("--dir", "project_dir", default=".", help="Project directory")
@click.option("--task", required=True, help="Task to build context for")
@click.option("--pack", default="balanced", type=click.Choice(["minimal", "balanced", "standard", "full"]), help="Pack detail level")
@click.option("--no-state", is_flag=True, help="Exclude acts state from the pack")
@click.option("--session-id", default="", help="Session ID for one-pack-per-task enforcement")
@click.option("--refresh-reason", default="", help="Reason for repeated context-pack call")
def context_pack(project_dir, task, pack, no_state, session_id, refresh_reason):
    """Build token-efficient task-specific context pack."""
    _echo_tool_result(_mcp_tools().haxaml_context_pack(
        task=task,
        project_dir=project_dir,
        pack=pack,
        include_state=not no_state,
        session_id=session_id,
        refresh_reason=refresh_reason,
    ))


@cli.command("verify")
@click.option("--dir", "project_dir", default=".", help="Project directory")
@click.option("--task", required=True, help="Task that was worked on")
@click.option("--session-id", default="", help="Session ID (optional)")
@click.option("--summary", default="", help="Change summary for verification evidence")
@click.option("--inspected-context", "inspected_context", multiple=True, help="Context files you inspected")
@click.option("--changed-file", "changed_files", multiple=True, help="Changed file path (repeatable)")
@click.option("--unresolved", "unresolved_questions", multiple=True, help="Unresolved question (repeatable)")
@click.option("--assumption", "assumptions", multiple=True, help="Assumption made (repeatable)")
def verify(project_dir, task, session_id, summary, inspected_context, changed_files, unresolved_questions, assumptions):
    """Run reflective verification before recording completion."""
    _echo_tool_result(_mcp_tools().haxaml_session_verify(
        task=task,
        project_dir=project_dir,
        session_id=session_id,
        inspected_context=list(inspected_context),
        changed_files=list(changed_files),
        unresolved_questions=list(unresolved_questions),
        assumptions=list(assumptions),
        summary=summary,
    ))


@cli.command("session-record")
@click.option("--dir", "project_dir", default=".", help="Project directory")
@click.option("--task", required=True, help="Task that was completed")
@click.option("--result", "run_result", default="success",
              type=click.Choice(["success", "partial", "failed"]))
@click.option("--session-id", default="", help="Session ID (optional)")
@click.option("--changes", default="", help="Summary of changes")
@click.option("--decisions", default="", help="Key decisions made")
@click.option("--risks", default="", help="Identified risks")
def session_record(project_dir, task, run_result, session_id, changes, decisions, risks):
    """Record session completion (verification gate enforced)."""
    _echo_tool_result(_mcp_tools().haxaml_session_record(
        task=task,
        result=run_result,
        project_dir=project_dir,
        session_id=session_id,
        changes=changes,
        decisions=decisions,
        risks=risks,
    ))


@cli.command()
@click.option("--dir", "project_dir", default=".", help="Project directory")
@click.option("--task", required=True, help="Task to execute")
@click.option("--description", default="", help="Task description")
def run(project_dir, task, description):
    """Start an execution run (sets active task, validates preflight)."""
    _echo_tool_result(_mcp_tools().haxaml_run(task=task, description=description, project_dir=project_dir))


@cli.command()
@click.option("--dir", "project_dir", default=".", help="Project directory")
@click.option("--task", required=True, help="Task that was completed")
@click.option("--result", "run_result", default="success",
              type=click.Choice(["success", "partial", "failed"]))
@click.option("--session-id", default="", help="Session ID (optional)")
@click.option("--changes", default="", help="Summary of changes")
@click.option("--decisions", default="", help="Key decisions made")
@click.option("--risks", default="", help="Identified risks")
def done(project_dir, task, run_result, session_id, changes, decisions, risks):
    """Complete an execution run and record results."""
    _echo_tool_result(_mcp_tools().haxaml_done(
        task=task,
        result=run_result,
        session_id=session_id,
        changes=changes,
        decisions=decisions,
        risks=risks,
        project_dir=project_dir,
    ), exit_on_failure=False)


@cli.command()
@click.option("--dir", "project_dir", default=".", help="Project directory")
@click.option("--agent", default="generic",
              type=click.Choice(["claude", "windsurf", "copilot", "codex", "cursor", "gemini", "generic"]),
              help="Target AI agent")
@click.option("--output", default=None, help="Override output file path")
@click.option("--target", default=None, help="Alias of --output (preferred for agent workflows)")
@click.option("--all", "export_all", is_flag=True, help="Export for all supported agents")
@click.option("--print", "print_only", is_flag=True, help="Print to stdout instead of writing file")
@click.option("--dry-run", is_flag=True, help="Preview export target without writing files.")
@click.option("--diff-preview", is_flag=True, help="Include unified diff preview in export result.")
@click.option(
    "--override-native",
    is_flag=True,
    help="For codex export only: write native AGENTS.md instead of haxaml-agents.md.",
)
@click.option(
    "--overwrite-existing",
    is_flag=True,
    help="Allow replacing existing non-Haxaml files at the output path.",
)
@click.option("--quiet", is_flag=True, help="Suppress success output")
def export(
    project_dir,
    agent,
    output,
    target,
    export_all,
    print_only,
    dry_run,
    diff_preview,
    override_native,
    overwrite_existing,
    quiet,
):
    """Export FRAME files (default: HAXAML.md; optional agent-specific targets)."""
    from haxaml.export_engine import export_frame_to_markdown

    if output and target:
        click.echo("✗ Use only one of --output or --target.")
        sys.exit(1)

    output_path = target or output

    if export_all and output_path is None and not print_only:
        if dry_run or diff_preview:
            click.echo("✗ --dry-run/--diff-preview cannot be combined with --all.")
            sys.exit(1)
        result = _mcp_tools().haxaml_export(
            agent="all",
            project_dir=project_dir,
            override_native=override_native,
            overwrite_existing=overwrite_existing,
        )
        if not quiet:
            click.echo(_result_text(result))
        if _is_failure(result):
            sys.exit(1)
        return

    if export_all:
        click.echo("✗ --all cannot be combined with --output/--target or --print.")
        sys.exit(1)
        return

    if print_only:
        if output_path is not None:
            click.echo("✗ --print cannot be combined with --output/--target.")
            sys.exit(1)
        if dry_run or diff_preview:
            click.echo("✗ --print cannot be combined with --dry-run/--diff-preview.")
            sys.exit(1)
        content = export_frame_to_markdown(project_dir, agent)
        click.echo(content)
        return

    result = _mcp_tools().haxaml_export(
        agent=agent,
        project_dir=project_dir,
        target=output_path,
        dry_run=dry_run,
        diff_preview=diff_preview,
        override_native=override_native,
        overwrite_existing=overwrite_existing,
    )
    if not quiet:
        click.echo(_result_text(result))
        if diff_preview and isinstance(result, dict):
            diff = result.get("data", {}).get("diff", "")
            if diff:
                click.echo(diff)
    if _is_failure(result):
        sys.exit(1)


@cli.command("mcp-bootstrap")
@click.option("--dir", "project_dir", default=".", help="Project directory")
@click.option(
    "--editor",
    "editors",
    multiple=True,
    type=click.Choice(["claude_code", "cursor", "copilot", "generic"]),
    help="Target editor(s). Repeatable.",
)
@click.option("--mode", default="both", type=click.Choice(["snippets", "write", "both"]))
@click.option("--uvx/--no-uvx", default=True, help="Prefer uvx launcher in config snippets.")
@click.option("--overwrite", is_flag=True, help="Overwrite existing haxaml MCP server block.")
def mcp_bootstrap(project_dir, editors, mode, uvx, overwrite):
    """Generate/write MCP bootstrap config for common editors."""
    result = _mcp_tools().haxaml_mcp_bootstrap(
        project_dir=project_dir,
        editors=list(editors) if editors else None,
        mode=mode,
        uvx=uvx,
        overwrite=overwrite,
    )
    click.echo(_result_text(result))
    if _is_failure(result):
        sys.exit(1)


@cli.command("install-hook")
@click.option("--dir", "project_dir", default=".", help="Project directory")
@click.option("--force", is_flag=True, help="Overwrite existing pre-commit hook")
def install_hook(project_dir, force):
    """Install a git pre-commit hook that auto-exports FRAME on commit."""
    from haxaml.auto_export import install_git_hook
    click.echo(install_git_hook(project_dir, force=force))


@cli.command("uninstall-hook")
@click.option("--dir", "project_dir", default=".", help="Project directory")
def uninstall_hook(project_dir):
    """Remove the Haxaml pre-commit hook."""
    from haxaml.auto_export import uninstall_git_hook
    click.echo(uninstall_git_hook(project_dir))


@cli.command()
@click.option("--dir", "project_dir", default=".", help="Project directory")
@click.option("--interval", default=2.0, help="Poll interval in seconds")
def watch(project_dir, interval):
    """Watch .haxaml/ for changes and auto re-export agent files."""
    from haxaml.auto_export import watch_and_export
    click.echo(f"Watching {Path(project_dir).resolve() / '.haxaml'}/ for changes (Ctrl+C to stop)...")
    try:
        watch_and_export(
            project_dir,
            interval=interval,
            callback=lambda paths: click.echo(f"Re-exported {len(paths)} file(s)"),
        )
    except KeyboardInterrupt:
        click.echo("\nStopped.")


@cli.command()
def mcp():
    """Start the Haxaml MCP server (stdio transport)."""
    _mcp_tools().main()


if __name__ == "__main__":
    cli()
