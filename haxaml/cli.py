"""Haxaml CLI — deterministic agent-management tooling for FRAME."""

import os
import sys
from pathlib import Path

import click

from haxaml.state_manager import StateManager
from haxaml.brain_builder import interactive_build
from haxaml.benchmarks import format_benchmark_report
from haxaml.paths import frame_path, resolve_frame_file


@click.group()
@click.version_option(version="0.1.0")
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


def _is_failure(result: str) -> bool:
    text = (result or "").strip()
    if not text:
        return False
    if text.startswith("✗"):
        return True
    return "Validation failed" in text


@cli.command()
@click.argument("directory", default=".")
def init(directory):
    """Initialize FRAME governance files in DIRECTORY."""
    result = _mcp_tools().haxaml_init(directory)
    click.echo(result)


@cli.command()
@click.option("--dir", "project_dir", default=".", help="Project directory")
def validate(project_dir):
    """Validate FRAME files against schemas."""
    result = _mcp_tools().haxaml_validate(project_dir)
    click.echo(result)
    if _is_failure(result):
        sys.exit(1)


def _resolve(project: Path, new_name: str, old_name: str) -> Path | None:
    """Resolve FRAME filename with backward compat fallback."""
    return resolve_frame_file(project, new_name, old_name)


@cli.command()
@click.option("--dir", "project_dir", default=".", help="Project directory")
def doctor(project_dir):
    """Check facts completeness beyond schema validation."""
    result = _mcp_tools().haxaml_doctor(project_dir)
    click.echo(result)
    if _is_failure(result):
        sys.exit(1)


@cli.command()
@click.option("--dir", "project_dir", default=".", help="Project directory")
@click.option("--no-state", is_flag=True, help="Exclude state from context")
@click.option("--tokens", is_flag=True, help="Show token count")
def context(project_dir, no_state, tokens):
    """Output minimal context for an AI agent."""
    result = _mcp_tools().haxaml_context(project_dir, include_state=not no_state)
    if tokens:
        click.echo(result)
        return
    marker = "\n\n--- Token count:"
    base = result.split(marker, 1)[0]
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
    result = _mcp_tools().haxaml_adopt(project_dir=project_dir, write=write_files, force=force)
    click.echo(result)
    if _is_failure(result):
        sys.exit(1)


@cli.command()
@click.option("--dir", "project_dir", default=".", help="Project directory")
def needs(project_dir):
    """List what still needs user/agent input before safe building."""
    click.echo(_mcp_tools().haxaml_needs(project_dir))


@cli.command()
@click.argument("module")
@click.option("--dir", "project_dir", default=".", help="Project directory")
def impact(module, project_dir):
    """Show what is affected when changing a module."""
    click.echo(_mcp_tools().haxaml_impact(module, project_dir))


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
    click.echo(result)
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
    click.echo(result)
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
    result = _mcp_tools().haxaml_health(project_dir)
    click.echo(result)
    if _is_failure(result):
        sys.exit(1)


@cli.command()
@click.option("--facts", "facts_path", default=None, help="Path to facts.yaml")
@click.option("--dir", "project_dir", default=".", help="Project directory for full report")
def benchmark(facts_path, project_dir):
    """Run token efficiency benchmarks."""
    if facts_path is not None:
        if not os.path.exists(facts_path):
            click.echo(f"✗ facts file not found at {facts_path}")
            sys.exit(1)
        report = format_benchmark_report(facts_path, project_dir)
        click.echo(report)
        return

    result = _mcp_tools().haxaml_benchmark(project_dir)
    click.echo(result)
    if _is_failure(result):
        sys.exit(1)


@cli.command()
@click.option("--dir", "project_dir", default=".", help="Project directory")
@click.option("--task", required=True, help="Task to execute")
@click.option("--description", default="", help="Task description")
def run(project_dir, task, description):
    """Start an execution run (sets active task, validates preflight)."""
    result = _mcp_tools().haxaml_run(task=task, description=description, project_dir=project_dir)
    click.echo(result)
    if _is_failure(result):
        sys.exit(1)


@cli.command()
@click.option("--dir", "project_dir", default=".", help="Project directory")
@click.option("--task", required=True, help="Task that was completed")
@click.option("--result", "run_result", default="success",
              type=click.Choice(["success", "partial", "failed"]))
@click.option("--changes", default="", help="Summary of changes")
@click.option("--decisions", default="", help="Key decisions made")
@click.option("--risks", default="", help="Identified risks")
def done(project_dir, task, run_result, changes, decisions, risks):
    """Complete an execution run and record results."""
    result = _mcp_tools().haxaml_done(
        task=task,
        result=run_result,
        changes=changes,
        decisions=decisions,
        risks=risks,
        project_dir=project_dir,
    )
    click.echo(result)


@cli.command()
@click.option("--dir", "project_dir", default=".", help="Project directory")
@click.option("--agent", default="generic",
              type=click.Choice(["claude", "windsurf", "copilot", "codex", "cursor", "gemini", "generic"]),
              help="Target AI agent")
@click.option("--output", default=None, help="Override output file path")
@click.option("--all", "export_all", is_flag=True, help="Export for all supported agents")
@click.option("--print", "print_only", is_flag=True, help="Print to stdout instead of writing file")
@click.option("--quiet", is_flag=True, help="Suppress success output")
def export(project_dir, agent, output, export_all, print_only, quiet):
    """Export FRAME files to agent-specific markdown (CLAUDE.md, AGENTS.md, etc.)."""
    from haxaml.export_engine import export_frame_to_markdown, export_to_file, list_agents

    if export_all and output is None and not print_only:
        result = _mcp_tools().haxaml_export(agent="all", project_dir=project_dir)
        if not quiet:
            click.echo(result)
        return

    if export_all:
        for a in list_agents():
            path = export_to_file(project_dir, a["name"])
            if not quiet:
                click.echo(f"✓ {a['name']:10s} → {path}")
        return

    if print_only:
        content = export_frame_to_markdown(project_dir, agent)
        click.echo(content)
        return

    if output is None:
        result = _mcp_tools().haxaml_export(agent=agent, project_dir=project_dir)
        if not quiet:
            click.echo(result)
    else:
        path = export_to_file(project_dir, agent, output)
        if not quiet:
            click.echo(f"✓ Exported to {path}")


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
