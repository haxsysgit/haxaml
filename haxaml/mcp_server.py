"""Haxaml MCP Server — exposes FRAME governance as MCP tools and resources.

Tools let AI agents manage FRAME governance natively during conversations.
Resources provide read-only access to current FRAME state.

Usage:
    haxaml-mcp                          # stdio transport (default)
    haxaml mcp                          # same, via CLI
    HAXAML_PROJECT_DIR=/path haxaml-mcp # explicit project directory
"""

import os
import json
import difflib
import shutil
import subprocess
from pathlib import Path
from typing import Any, Optional

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
    export_to_file, list_agents, AGENT_CONFIGS, export_frame_to_markdown,
)
from haxaml.auto_export import export_if_stale
from haxaml.init_templates import write_init_templates
from haxaml.versioning import MCP_LAUNCHER_PACKAGE, PACKAGE_NAME, version_spec


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


def _ok(tool: str, data: Optional[dict] = None, warnings: Optional[list[str]] = None) -> dict:
    payload = data or {}
    return {
        "ok": True,
        "tool": tool,
        "data": payload,
        "warnings": warnings or [],
        "error": None,
    }


def _err(
    tool: str,
    code: str,
    message: str,
    details: Optional[dict] = None,
    warnings: Optional[list[str]] = None,
) -> dict:
    return {
        "ok": False,
        "tool": tool,
        "data": {},
        "warnings": warnings or [],
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
        },
    }


def _resolve_export_target(
    project_dir: str,
    agent: str,
    target: Optional[str] = None,
    override_native: bool = False,
) -> Path:
    config = AGENT_CONFIGS[agent]
    if target:
        return Path(target).expanduser().resolve()
    filename = config.get("native_filename") if override_native else config["filename"]
    return (Path(project_dir).resolve() / filename).resolve()


def _build_unified_diff(before: str, after: str, target_path: Path) -> str:
    before_lines = before.splitlines(keepends=True)
    after_lines = after.splitlines(keepends=True)
    diff_lines = difflib.unified_diff(
        before_lines,
        after_lines,
        fromfile=str(target_path),
        tofile=str(target_path),
        lineterm="\n",
    )
    return "".join(diff_lines)


def _diff_summary(diff_text: str) -> dict:
    added = 0
    removed = 0
    for line in diff_text.splitlines():
        if line.startswith(("---", "+++", "@@")):
            continue
        if line.startswith("+"):
            added += 1
        elif line.startswith("-"):
            removed += 1
    return {
        "changed": bool(diff_text),
        "added_lines": added,
        "removed_lines": removed,
    }


def _mcp_server_config(project_dir: str, uvx: bool = True) -> dict:
    if uvx:
        return {
            "type": "stdio",
            "command": "uvx",
            "args": ["haxaml-mcp"],
            "env": {"HAXAML_PROJECT_DIR": str(Path(project_dir).resolve())},
        }
    return {
        "type": "stdio",
        "command": "haxaml-mcp",
        "args": [],
        "env": {"HAXAML_PROJECT_DIR": str(Path(project_dir).resolve())},
    }


def _editor_targets(project_dir: Path) -> dict[str, Optional[Path]]:
    return {
        "generic": (project_dir / ".mcp.json"),
        "claude_code": (project_dir / ".mcp.json"),
        "cursor": (project_dir / ".cursor" / "mcp.json"),
        "copilot": None,
    }


def _bootstrap_snippet(project_dir: str, uvx: bool = True) -> dict:
    base = _mcp_server_config(project_dir, uvx=uvx)
    return {"mcpServers": {"haxaml": base}}


def _write_bootstrap_config(
    path: Path,
    server_block: dict,
    overwrite: bool = False,
) -> tuple[str, str]:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = {}
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return "error", f"Existing config is invalid JSON: {path}"
    if not isinstance(existing, dict):
        return "error", f"Existing config must be a JSON object: {path}"

    mcp_servers = existing.setdefault("mcpServers", {})
    if not isinstance(mcp_servers, dict):
        return "error", f"`mcpServers` must be an object in {path}"

    if "haxaml" in mcp_servers and not overwrite:
        return "skipped_exists", f"Existing haxaml server preserved in {path}"

    mcp_servers["haxaml"] = server_block
    path.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")
    return "written", f"Wrote MCP config at {path}"


# ─── Tools ───────────────────────────────────────────────────────────────────


@mcp_app.tool()
def haxaml_init(directory: str = ".") -> dict:
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
        return _ok(
            "haxaml_init",
            {
                "message": f"⚠ facts.yaml already exists at {facts_p}. Use haxaml_validate to check it.",
                "project_dir": str(project_dir),
                "created": False,
            },
        )

    write_init_templates(project_dir)

    stale = export_if_stale(str(project_dir), agents=["generic"])
    re_export_msg = ""
    if stale:
        re_export_msg = f"\n  ↻ Auto-exported {len(stale)} agent file(s)"

    message = (
        f"✓ Initialized FRAME at {haxaml_root}\n"
        f"  → .haxaml/facts.yaml — fill in project truth\n"
        f"  → .haxaml/rules.yaml — define agent rules\n"
        f"  → .haxaml/acts.yaml — diary starts here\n"
        f"  → .haxaml/expect.yaml — plan your runs\n"
        f"  → Call haxaml_validate when ready{re_export_msg}"
    )
    return _ok(
        "haxaml_init",
        {
            "message": message,
            "project_dir": str(project_dir),
            "created": True,
            "auto_exported": stale,
        },
    )


@mcp_app.tool()
def haxaml_validate(project_dir: str = ".") -> dict:
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
    message = "\n".join(lines)
    if all_valid:
        return _ok("haxaml_validate", {"message": message, "valid": True})
    return _err(
        "haxaml_validate",
        "validation_failed",
        "FRAME validation failed.",
        {"message": message},
    )


@mcp_app.tool()
def haxaml_context(project_dir: str = ".", include_state: bool = True) -> dict:
    """Get the current project context for the AI agent.

    Returns a compact summary of facts, rules, acts, and expect.
    This is what the agent reads to understand the project.
    """
    ctx = build_context(project_dir, include_state=include_state)
    tokens = count_tokens(ctx)
    message = f"{ctx}\n\n--- Token count: {tokens} ---"
    return _ok(
        "haxaml_context",
        {
            "message": message,
            "context": ctx,
            "tokens": tokens,
            "include_state": include_state,
        },
    )


@mcp_app.tool()
def haxaml_health(project_dir: str = ".") -> dict:
    """Get project health report.

    Shows validation status, state summary, token count, errors and warnings.
    """
    try:
        runner = ExecutionRunner(project_dir)
    except FileNotFoundError as e:
        return _err("haxaml_health", "missing_frame", str(e))

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

    message = "\n".join(lines)
    if report["ready"]:
        return _ok("haxaml_health", {"message": message, "report": report})
    return _err("haxaml_health", "not_ready", "Project health has errors.", {"message": message, "report": report})


@mcp_app.tool()
def haxaml_doctor(project_dir: str = ".") -> dict:
    """Check facts completeness beyond schema validation.

    Finds missing recommended fields and blocking unresolved items.
    """
    p = Path(project_dir).resolve()
    facts_path = resolve_frame_file(p, "facts.yaml", "brain.yaml")
    if not facts_path:
        return _err("haxaml_doctor", "missing_facts", "facts.yaml not found")

    errors = validate_facts(str(facts_path))
    if errors:
        lines = ["✗ facts.yaml fails schema validation — fix these first:"]
        for e in errors:
            lines.append(f"  → {e}")
        return _err(
            "haxaml_doctor",
            "invalid_facts_schema",
            "facts.yaml fails schema validation.",
            {"message": "\n".join(lines), "errors": errors},
        )

    missing = detect_missing_facts_fields(str(facts_path))
    if missing:
        lines = [f"⚠ {len(missing)} recommendation(s):"]
        for m in missing:
            lines.append(f"  → {m}")
        return _ok(
            "haxaml_doctor",
            {"message": "\n".join(lines), "recommendations": missing, "has_recommendations": True},
        )

    return _ok(
        "haxaml_doctor",
        {"message": "✓ facts.yaml is complete — no recommendations", "has_recommendations": False},
    )


@mcp_app.tool()
def haxaml_run(task: str, description: str = "", project_dir: str = ".") -> dict:
    """Start a governed execution run.

    Sets the active task in acts.yaml and runs preflight validation.
    Call this before starting work on a task.
    """
    try:
        runner = ExecutionRunner(project_dir)
    except FileNotFoundError as e:
        return _err("haxaml_run", "missing_frame", str(e))

    result = runner.start_run(task=task, description=description)
    if result.result == "failed":
        lines = ["✗ Run failed preflight:"]
        for e in result.errors:
            lines.append(f"  → {e}")
        return _err(
            "haxaml_run",
            "preflight_failed",
            "Run failed preflight.",
            {"message": "\n".join(lines), "errors": result.errors},
        )

    lines = [f"✓ Run started: {task}"]
    if result.warnings:
        for w in result.warnings:
            lines.append(f"  ⚠ {w}")
    lines.append("  → Work on the task, then call haxaml_done to record results")
    return _ok(
        "haxaml_run",
        {
            "message": "\n".join(lines),
            "task": task,
            "warnings": result.warnings,
        },
    )


@mcp_app.tool()
def haxaml_done(
    task: str,
    result: str = "success",
    changes: str = "",
    decisions: str = "",
    risks: str = "",
    project_dir: str = ".",
) -> dict:
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
        return _err("haxaml_done", "missing_frame", str(e))

    run_result = runner.finish_run(
        task=task, result=result, changes=changes,
        decisions=decisions, risks=risks,
    )

    if run_result.errors:
        lines = ["⚠ Run completed with errors:"]
        for e in run_result.errors:
            lines.append(f"  → {e}")
        return _err(
            "haxaml_done",
            "run_record_error",
            "Run completed with errors.",
            {"message": "\n".join(lines), "errors": run_result.errors},
        )

    lines = [f"✓ Run {run_result.run_id} recorded ({result})"]
    lines.append(f"  Context: {run_result.token_count} tokens")
    if run_result.warnings:
        for w in run_result.warnings:
            lines.append(f"  ⚠ {w}")

    stale = export_if_stale(project_dir, agents=["generic"])
    if stale:
        lines.append(f"  ↻ Auto re-exported {len(stale)} agent file(s)")

    return _ok(
        "haxaml_done",
        {
            "message": "\n".join(lines),
            "run_id": run_result.run_id,
            "token_count": run_result.token_count,
            "warnings": run_result.warnings,
            "auto_exported": stale,
        },
    )


@mcp_app.tool()
def haxaml_export(
    agent: str = "generic",
    project_dir: str = ".",
    target: Optional[str] = None,
    dry_run: bool = False,
    diff_preview: bool = False,
    override_native: bool = False,
    overwrite_existing: bool = False,
) -> dict:
    """Export FRAME to an agent-native markdown file.

    Default export writes HAXAML.md. Explicit agent exports can generate
    CLAUDE.md, haxaml-agents.md, .cursor/rules/haxaml.mdc, etc.
    Use agent='all' to export for all supported agents.

    Supported agents: claude, codex, cursor, windsurf, copilot, gemini, generic
    """
    target_path = (target or "").strip() or None

    if agent == "all":
        if target_path is not None:
            return _err(
                "haxaml_export",
                "invalid_target_with_all",
                "target cannot be used with agent='all'.",
            )
        if dry_run:
            return _err(
                "haxaml_export",
                "invalid_dry_run_with_all",
                "dry_run is only supported with a single agent.",
            )
        lines = []
        exported = []
        for a in list_agents():
            path = export_to_file(
                project_dir,
                a["name"],
                override_native=override_native,
                overwrite_existing=overwrite_existing,
            )
            lines.append(f"✓ {a['name']:10s} → {path}")
            exported.append({"agent": a["name"], "path": path})
        return _ok(
            "haxaml_export",
            {"message": "\n".join(lines), "exports": exported},
        )

    if agent not in AGENT_CONFIGS:
        available = ", ".join(a["name"] for a in list_agents())
        return _err(
            "haxaml_export",
            "unknown_agent",
            f"Unknown agent '{agent}'. Available: {available}",
        )

    resolved_target = _resolve_export_target(
        project_dir=project_dir,
        agent=agent,
        target=target_path,
        override_native=override_native,
    )
    content = export_frame_to_markdown(project_dir, agent)

    existing = ""
    exists = resolved_target.exists()
    if exists:
        existing = resolved_target.read_text(encoding="utf-8", errors="ignore")

    diff = ""
    summary = {"changed": not exists or existing != content, "added_lines": 0, "removed_lines": 0}
    if diff_preview:
        diff = _build_unified_diff(existing, content, resolved_target)
        summary = _diff_summary(diff)

    if dry_run:
        message = f"✓ Dry run complete for {resolved_target}"
        return _ok(
            "haxaml_export",
            {
                "message": message,
                "agent": agent,
                "would_write": True,
                "target_path": str(resolved_target),
                "exists": exists,
                "generated_marker_present": ("Generated by Haxaml from FRAME" in existing) if exists else False,
                "diff": diff,
                "summary": summary,
            },
        )

    try:
        path = export_to_file(
            project_dir,
            agent,
            output_path=target_path,
            override_native=override_native,
            overwrite_existing=overwrite_existing,
        )
        message = f"✓ Exported to {path}"
        return _ok(
            "haxaml_export",
            {
                "message": message,
                "agent": agent,
                "target_path": path,
                "exists": exists,
                "generated_marker_present": ("Generated by Haxaml from FRAME" in existing) if exists else False,
                "diff": diff if diff_preview else "",
                "summary": summary if diff_preview else {"changed": True, "added_lines": 0, "removed_lines": 0},
            },
        )
    except FileExistsError as e:
        return _err("haxaml_export", "protected_existing_file", str(e))


@mcp_app.tool()
def haxaml_upgrade(
    target_version: Optional[str] = None,
    include_mcp: bool = True,
    dry_run: bool = False,
) -> dict:
    """Upgrade haxaml (and optionally haxaml-mcp) using uv tool management."""
    if not shutil.which("uv"):
        return _err(
            "haxaml_upgrade",
            "uv_not_found",
            "uv is required for upgrade. Install uv first: https://docs.astral.sh/uv/",
        )

    specs = [version_spec(PACKAGE_NAME, target_version)]
    if include_mcp:
        specs.append(version_spec(MCP_LAUNCHER_PACKAGE, target_version))

    upgrade_cmd = ["uv", "tool", "upgrade", *specs]
    if dry_run:
        return _ok(
            "haxaml_upgrade",
            {
                "message": "✓ Dry run upgrade plan prepared.",
                "command": upgrade_cmd,
                "target_version": target_version or "latest",
                "include_mcp": include_mcp,
            },
        )

    primary = subprocess.run(upgrade_cmd, capture_output=True, text=True)
    if primary.returncode == 0:
        return _ok(
            "haxaml_upgrade",
            {
                "message": "✓ Upgrade complete via `uv tool upgrade`.",
                "command": upgrade_cmd,
                "stdout": (primary.stdout or "").strip(),
                "stderr": (primary.stderr or "").strip(),
                "include_mcp": include_mcp,
                "target_version": target_version or "latest",
            },
        )

    failures = []
    executed = []
    for spec in specs:
        cmd = ["uv", "tool", "install", "--upgrade", spec]
        step = subprocess.run(cmd, capture_output=True, text=True)
        executed.append({"command": cmd, "returncode": step.returncode})
        if step.returncode != 0:
            failures.append(
                {
                    "spec": spec,
                    "stderr": (step.stderr or "").strip(),
                    "stdout": (step.stdout or "").strip(),
                }
            )

    if failures:
        return _err(
            "haxaml_upgrade",
            "upgrade_failed",
            "Upgrade failed for one or more packages.",
            {
                "command": upgrade_cmd,
                "primary_stderr": (primary.stderr or "").strip(),
                "primary_stdout": (primary.stdout or "").strip(),
                "failures": failures,
                "executed": executed,
            },
        )

    return _ok(
        "haxaml_upgrade",
        {
            "message": "✓ Upgrade complete via fallback install flow.",
            "command": upgrade_cmd,
            "include_mcp": include_mcp,
            "target_version": target_version or "latest",
            "executed": executed,
        },
    )


@mcp_app.tool()
def haxaml_mcp_bootstrap(
    project_dir: str = ".",
    editors: Optional[list[str]] = None,
    mode: str = "both",
    uvx: bool = True,
    overwrite: bool = False,
) -> dict:
    """Generate and optionally write MCP config snippets for common editors."""
    valid_modes = {"snippets", "write", "both"}
    if mode not in valid_modes:
        return _err(
            "haxaml_mcp_bootstrap",
            "invalid_mode",
            f"mode must be one of: {', '.join(sorted(valid_modes))}",
        )

    requested = editors or ["claude_code", "cursor", "copilot", "generic"]
    supported = {"claude_code", "cursor", "copilot", "generic"}
    unknown = [e for e in requested if e not in supported]
    if unknown:
        return _err(
            "haxaml_mcp_bootstrap",
            "unknown_editor",
            "Unsupported editor requested.",
            {"unknown_editors": unknown, "supported_editors": sorted(supported)},
        )

    project = Path(project_dir).resolve()
    server_block = _mcp_server_config(str(project), uvx=uvx)
    snippet = {"mcpServers": {"haxaml": server_block}}
    snippets = {editor: snippet for editor in requested}
    writes = []

    if mode in {"write", "both"}:
        targets = _editor_targets(project)
        seen_paths = set()
        for editor in requested:
            target_path = targets.get(editor)
            if target_path is None:
                writes.append(
                    {
                        "editor": editor,
                        "path": None,
                        "status": "skipped_unknown_location",
                        "message": "No safe project-local target path is defined for this editor.",
                    }
                )
                continue
            if str(target_path) in seen_paths:
                writes.append(
                    {
                        "editor": editor,
                        "path": str(target_path),
                        "status": "skipped_duplicate_target",
                        "message": "Target already handled for another requested editor.",
                    }
                )
                continue
            seen_paths.add(str(target_path))
            status, message = _write_bootstrap_config(target_path, server_block, overwrite=overwrite)
            writes.append(
                {
                    "editor": editor,
                    "path": str(target_path),
                    "status": status,
                    "message": message,
                }
            )

    message = "✓ MCP bootstrap prepared."
    if mode in {"write", "both"}:
        written_count = sum(1 for item in writes if item["status"] == "written")
        message += f" Wrote {written_count} config file(s)."

    return _ok(
        "haxaml_mcp_bootstrap",
        {
            "message": message,
            "project_dir": str(project),
            "mode": mode,
            "snippets": snippets if mode in {"snippets", "both"} else {},
            "writes": writes,
            "next_steps": [
                "Use `/mcp show` (or equivalent) in your client to verify server visibility.",
                "For Copilot CLI global setup, see ~/.copilot/mcp-config.json docs path.",
            ],
        },
    )


@mcp_app.tool()
def haxaml_adopt(
    project_dir: str = ".",
    write: bool = False,
    force: bool = False,
) -> dict:
    """Adopt an existing project into FRAME governance.

    Scans for native agent files (CLAUDE.md, AGENTS.md, .cursor/rules/, etc.)
    and repository context (README, package.json, etc.).

    With write=False (default): shows the adoption report (dry run).
    With write=True: creates .haxaml/ADOPTION.md and scaffold FRAME files.
    """
    plan = scan_native_sources(project_dir)

    if not write:
        report = render_adoption_report(plan)
        return _ok(
            "haxaml_adopt",
            {
                "message": f"{report}\n---\nDry run. Call with write=True to create files.",
                "written": [],
                "dry_run": True,
            },
        )

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
        return _ok(
            "haxaml_adopt",
            {
                "message": "\n".join(lines),
                "written": [str(path.relative_to(plan.project_dir)) for path in written],
                "dry_run": False,
            },
        )

    return _ok(
        "haxaml_adopt",
        {
            "message": "No files written. Existing files preserved. Use force=True to overwrite.",
            "written": [],
            "dry_run": False,
        },
    )


@mcp_app.tool()
def haxaml_needs(project_dir: str = ".") -> dict:
    """List what the user still needs to provide.

    Checks for blocking unresolved items in facts.yaml,
    blocking dependencies in acts.yaml, active run requirements
    in expect.yaml, and blocking open questions.
    """
    message = render_needs(project_dir)
    if message.startswith("✗"):
        return _err("haxaml_needs", "missing_frame", message)
    return _ok("haxaml_needs", {"message": message})


@mcp_app.tool()
def haxaml_impact(module: str, project_dir: str = ".") -> dict:
    """Check what's affected by changing a module.

    Reads map.yaml to show module ownership, dependencies, and impact rules.
    This prevents the "fix kitchen, break bathroom" problem.
    """
    message = render_impact(module, project_dir)
    if message.startswith("✗"):
        return _err("haxaml_impact", "impact_unavailable", message)
    return _ok("haxaml_impact", {"message": message, "module": module})


@mcp_app.tool()
def haxaml_state_show(project_dir: str = ".") -> dict:
    """Show current project diary (acts.yaml) summary."""
    p = Path(project_dir).resolve()
    acts_path = resolve_frame_file(p, "acts.yaml", "state.yaml")
    if not acts_path:
        return _err("haxaml_state_show", "missing_acts", "acts.yaml not found")

    try:
        sm = StateManager(str(acts_path))
    except StateError as e:
        return _err("haxaml_state_show", "state_error", str(e))

    stats = sm.get_stats()
    message = (
        f"Phase:      {stats['current_phase']}\n"
        f"Active:     {stats['active_task']}\n"
        f"Completed:  {stats['completed_count']}\n"
        f"Blocked:    {stats['blocked_count']}\n"
        f"Decisions:  {stats['decision_count']}\n"
        f"Unresolved: {stats['unresolved_count']}\n"
        f"Runs:       {stats['run_count']} (+ {stats['total_runs_compacted']} compacted)\n"
        f"File size:  {stats['file_size_bytes']} bytes"
    )
    return _ok("haxaml_state_show", {"message": message, "stats": stats})


@mcp_app.tool()
def haxaml_state_compact(project_dir: str = ".", keep_recent: int = 5) -> dict:
    """Compact old runs in acts.yaml to save context tokens.

    Summarizes old runs and keeps only the most recent ones.
    """
    p = Path(project_dir).resolve()
    acts_path = resolve_frame_file(p, "acts.yaml", "state.yaml")
    if not acts_path:
        return _err("haxaml_state_compact", "missing_acts", "acts.yaml not found")

    try:
        sm = StateManager(str(acts_path))
        result = sm.compact(keep_recent=keep_recent)
    except StateError as e:
        return _err("haxaml_state_compact", "state_error", str(e))

    message = f"✓ Compacted {result['compacted']} runs, kept {result['kept']}"
    return _ok("haxaml_state_compact", {"message": message, "result": result})


@mcp_app.tool()
def haxaml_benchmark(project_dir: str = ".") -> dict:
    """Run token efficiency benchmarks on FRAME files."""
    from haxaml.benchmarks import format_benchmark_report

    p = Path(project_dir).resolve()
    facts_path = resolve_frame_file(p, "facts.yaml", "brain.yaml")
    if not facts_path:
        return _err("haxaml_benchmark", "missing_facts", "facts.yaml not found")

    report = format_benchmark_report(str(facts_path), project_dir)
    return _ok("haxaml_benchmark", {"message": report})


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
