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
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from mcp.server.fastmcp import FastMCP

from haxaml.paths import frame_dir, frame_path, resolve_frame_file
from haxaml.validator import (
    validate_facts, validate_rules, validate_acts, validate_expect,
    validate_map, detect_missing_facts_fields,
)
from haxaml.context import (
    build_context,
    build_context_pack,
    count_tokens,
    format_context_pack,
    load_frame_data,
)
from haxaml.map_policy import (
    evaluate_map_complexity,
    map_complexity_issues,
    format_map_complexity_summary,
)
from haxaml.reconcile import reconcile_derivation
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


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _rules_policy(rules: dict[str, Any], key: str, default: dict[str, Any]) -> dict[str, Any]:
    value = rules.get(key, {})
    if isinstance(value, dict):
        merged = dict(default)
        merged.update(value)
        return merged
    return dict(default)


def _classify_task_type(task: str, rules: dict[str, Any]) -> str:
    task_l = task.lower()
    guidance_policy = _rules_policy(rules, "guidance_policy", {})
    hints = guidance_policy.get("task_type_hints", {})
    if isinstance(hints, dict):
        for task_type, words in hints.items():
            if not isinstance(words, list):
                continue
            for word in words:
                if isinstance(word, str) and word.lower() in task_l:
                    return task_type

    if any(k in task_l for k in ("debug", "bug", "fix", "error", "trace")):
        return "debug"
    if any(k in task_l for k in ("design", "architecture", "approach", "tradeoff")):
        return "design"
    if any(k in task_l for k in ("strategy", "roadmap", "position", "plan")):
        return "strategy"
    if any(k in task_l for k in ("build", "implement", "add", "create", "refactor", "update")):
        return "implementation"
    return "outcome"


def _guidance_eval(task: str, frame: dict[str, Any]) -> dict[str, Any]:
    facts = frame.get("facts") or {}
    rules = frame.get("rules") or {}
    acts = frame.get("acts") or {}
    expect = frame.get("expect") or {}

    clarification = _rules_policy(
        rules,
        "clarification_policy",
        {
            "mode": "risk_gated_soft_block",
            "min_task_chars": 16,
            "high_risk_keywords": [
                "delete",
                "drop",
                "migrate",
                "auth",
                "security",
                "payment",
                "billing",
                "database",
                "schema",
                "production",
                "infra",
            ],
        },
    )
    mode = str(clarification.get("mode", "risk_gated_soft_block"))
    min_task_chars = clarification.get("min_task_chars", 16)
    if not isinstance(min_task_chars, int) or min_task_chars < 1:
        min_task_chars = 16
    high_risk_words = clarification.get("high_risk_keywords", [])
    if not isinstance(high_risk_words, list):
        high_risk_words = []

    task_l = task.lower().strip()
    missing_context: list[str] = []
    assumptions: list[str] = []
    required_questions: list[str] = []
    suggested_questions: list[str] = []

    unresolved_facts = [
        item for item in (facts.get("unresolved", []) or [])
        if isinstance(item, dict) and item.get("blocking")
    ]
    unresolved_acts = [
        item for item in (acts.get("unresolved_dependencies", []) or [])
        if isinstance(item, dict) and item.get("blocking")
    ]
    unresolved_expect = [
        item for item in (expect.get("open_questions", []) or [])
        if isinstance(item, dict) and item.get("blocking")
    ]
    if unresolved_facts:
        missing_context.append("Blocking unresolved items exist in facts.yaml")
    if unresolved_acts:
        missing_context.append("Blocking unresolved dependencies exist in acts.yaml")
    if unresolved_expect:
        missing_context.append("Blocking open questions exist in expect.yaml")

    risky_keyword_hits = sorted(
        {w for w in high_risk_words if isinstance(w, str) and w.lower() in task_l}
    )
    very_short = len(task.strip()) < min_task_chars
    if very_short:
        assumptions.append("Task statement is short; intent may be underspecified.")
    if risky_keyword_hits:
        assumptions.append(f"Task includes high-impact domain keywords: {', '.join(risky_keyword_hits)}.")

    task_type = _classify_task_type(task, rules)
    if very_short:
        required_questions.append("What exact outcome should be delivered for this task?")
        suggested_questions.append("Which files/modules are expected to be touched?")
    if risky_keyword_hits:
        required_questions.append("Should this proceed now, or wait for explicit approval due to risk?")
        suggested_questions.append("What rollback path or safety checks are required?")
    if missing_context:
        required_questions.append("Which unresolved/blocking items should be resolved first?")

    if risky_keyword_hits or missing_context:
        risk_level = "high"
    elif very_short:
        risk_level = "medium"
    else:
        risk_level = "low"

    status = "proceed"
    if mode == "hard_block" and (required_questions or missing_context):
        status = "action_required"
    elif mode == "risk_gated_soft_block" and risk_level == "high" and required_questions:
        status = "action_required"

    safer_path = []
    if status == "action_required":
        safer_path.append("Resolve required clarification questions before code changes.")
        safer_path.append("Use `haxaml_context_pack` to gather only task-relevant context.")
    else:
        safer_path.append("Proceed with a minimal plan and verify against FRAME before record.")

    return {
        "status": status,
        "task_type": task_type,
        "risk_level": risk_level,
        "missing_context": missing_context,
        "assumptions": assumptions,
        "required_questions": required_questions,
        "suggested_questions": suggested_questions,
        "safer_path": safer_path,
        "recommended_packs": ["balanced", "minimal"] if risk_level == "low" else ["balanced", "full"],
    }


def _session_read_policy(frame: dict[str, Any]) -> dict[str, Any]:
    rules = frame.get("rules") or {}
    acts = frame.get("acts") or {}
    lifecycle = _rules_policy(
        rules,
        "lifecycle",
        {
            "onboarding_full_reads": 5,
            "enforce_verify_before_record": True,
        },
    )
    onboarding = lifecycle.get("onboarding_full_reads", 5)
    if not isinstance(onboarding, int) or onboarding < 1:
        onboarding = 5

    context_compaction = acts.get("context_compaction", {}) if isinstance(acts, dict) else {}
    sessions_started = context_compaction.get("sessions_started", 0)
    if not isinstance(sessions_started, int) or sessions_started < 0:
        sessions_started = 0

    canonical = [".haxaml/facts.yaml", ".haxaml/rules.yaml", ".haxaml/acts.yaml", ".haxaml/expect.yaml"]
    if frame.get("map"):
        canonical.append(".haxaml/map.yaml")

    needs_full_reads = sessions_started < onboarding
    required_reads = canonical if needs_full_reads else [".haxaml/facts.yaml", ".haxaml/rules.yaml"]
    return {
        "needs_full_reads": needs_full_reads,
        "required_reads": required_reads,
        "sessions_started": sessions_started,
        "onboarding_full_reads": onboarding,
        "enforce_verify_before_record": bool(lifecycle.get("enforce_verify_before_record", True)),
    }


def _get_state_manager(project_dir: str) -> tuple[Optional[StateManager], Optional[Path]]:
    p = Path(project_dir).resolve()
    acts_path = resolve_frame_file(p, "acts.yaml", "state.yaml")
    if not acts_path:
        return None, None
    try:
        return StateManager(str(acts_path)), acts_path
    except StateError:
        return None, acts_path


def _persist_state(sm: Optional[StateManager], state: dict[str, Any]) -> Optional[str]:
    if not sm:
        return "acts.yaml not available"
    try:
        sm.write(state)
    except StateError as exc:
        return str(exc)
    return None


def _find_session(state: dict[str, Any], session_id: str) -> Optional[dict[str, Any]]:
    sessions = state.get("sessions", [])
    if not isinstance(sessions, list):
        return None
    for session in sessions:
        if isinstance(session, dict) and session.get("id") == session_id:
            return session
    return None


def _wrapper_deprecation(tool: str, replacement: list[str]) -> dict[str, Any]:
    return {
        "tool": tool,
        "status": "deprecated",
        "replacement": replacement,
        "removal_target": "0.5.0",
        "message": f"{tool} is a compatibility wrapper and will be removed in 0.5.0.",
    }


def _adoption_plan_payload(project_dir: str, plan: Any = None) -> dict[str, Any]:
    plan = plan or scan_native_sources(project_dir)
    native_files = [{"kind": f.kind, "label": f.label, "path": f.path} for f in plan.native_files]
    context_files = [{"kind": f.kind, "label": f.label, "path": f.path} for f in plan.context_files]
    risks = []
    if len(native_files) >= 3:
        risks.append("Multiple native instruction sources detected; precedence conflicts are likely.")
    if plan.existing_frame_files:
        risks.append("Existing FRAME files detected; preserve unless explicit overwrite is requested.")
    if not native_files and not context_files:
        risks.append("No known native/context files were discovered; adoption may require manual context capture.")

    migration_steps = [
        "Run haxaml_reconcile to detect derivation boundary conflicts.",
        "Decide precedence for conflicting native instructions before editing FRAME.",
        "Fill/update FRAME files from evidence, then run haxaml_validate.",
        "Export native files from FRAME only after validate passes.",
    ]
    next_actions = [
        "Call haxaml_reconcile(project_dir='.')",
        "Resolve blocking conflicts from reconcile report.",
        "Call haxaml_validate(project_dir='.')",
    ]
    human_summary = (
        f"Inventory complete: {len(native_files)} native file(s), "
        f"{len(context_files)} context file(s), {len(plan.existing_frame_files)} existing FRAME file(s)."
    )
    return {
        "project_dir": str(plan.project_dir),
        "native_files": native_files,
        "context_files": context_files,
        "existing_frame_files": list(plan.existing_frame_files),
        "counts": {
            "native_files": len(native_files),
            "context_files": len(context_files),
            "existing_frame_files": len(plan.existing_frame_files),
        },
        "migration_plan": migration_steps,
        "risk_notes": risks,
        "next_actions": next_actions,
        "non_destructive": True,
        "human_summary": human_summary,
    }


def _has_conflict_stop_reason(changes: str, decisions: str, risks: str) -> bool:
    text = f"{changes}\n{decisions}\n{risks}".lower()
    keywords = (
        "conflict",
        "reconcile",
        "derivation",
        "map mismatch",
        "boundary mismatch",
        "gate reason",
    )
    return any(k in text for k in keywords)


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

    reconcile = reconcile_derivation(p)
    lines.append(f"• Reconcile: {reconcile['human_summary']}")
    for conflict in reconcile["conflicts"]:
        marker = "✗" if conflict["severity"] == "blocking" else "⚠"
        lines.append(f"{marker} reconcile[{conflict['id']}]: {conflict['message']}")
        lines.append(f"  → fix: {conflict['suggested_fix_action']}")
    if reconcile["severity_totals"]["blocking"] > 0:
        all_valid = False

    if all_valid:
        lines.append("\n✓ All FRAME files valid")
    else:
        lines.append("\n✗ Validation failed — fix errors above")
    message = "\n".join(lines)
    if all_valid:
        return _ok(
            "haxaml_validate",
            {
                "message": message,
                "valid": True,
                "reconcile": reconcile,
            },
        )
    error_code = "derivation_conflicts" if reconcile["severity_totals"]["blocking"] > 0 else "validation_failed"
    return _err(
        "haxaml_validate",
        error_code,
        "FRAME validation failed.",
        {
            "message": message,
            "reconcile": reconcile,
        },
    )


@mcp_app.tool()
def haxaml_context(project_dir: str = ".", include_state: bool = True) -> dict:
    """Get the current project context for the AI agent.

    Returns a compact summary of facts, rules, acts, and expect.
    This is what the agent reads to understand the project.
    """
    frame = load_frame_data(project_dir)
    if not frame.get("facts"):
        return _err("haxaml_context", "missing_facts", "facts.yaml not found")
    rules = frame.get("rules") or {}
    context_policy = _rules_policy(rules, "context_policy", {"default_pack": "balanced"})
    default_pack = str(context_policy.get("default_pack", "balanced"))
    pack_data = build_context_pack(
        project_dir,
        task="General project context",
        pack=default_pack,
        include_state=include_state,
    )
    ctx = "## Project Facts\n\n" + format_context_pack(pack_data)
    tokens = pack_data.get("_meta", {}).get("token_count", count_tokens(ctx))
    message = f"{ctx}\n\n--- Token count: {tokens} ---"
    dep = _wrapper_deprecation("haxaml_context", ["haxaml_context_pack"])
    return _ok(
        "haxaml_context",
        {
            "message": message,
            "context": ctx,
            "tokens": tokens,
            "context_pack": pack_data,
            "include_state": include_state,
            "deprecation": dep,
        },
        warnings=[dep["message"]],
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
def haxaml_guidance(task: str, project_dir: str = ".") -> dict:
    """Generate structured task guidance and clarification needs for agent execution."""
    frame = load_frame_data(project_dir)
    if not frame.get("facts"):
        return _err("haxaml_guidance", "missing_facts", "facts.yaml not found")

    guidance = _guidance_eval(task, frame)
    status = guidance["status"]
    msg_lines = [
        f"Task type: {guidance['task_type']}",
        f"Risk: {guidance['risk_level']}",
        f"Status: {status}",
    ]
    if guidance["required_questions"]:
        msg_lines.append("Required clarification:")
        msg_lines.extend([f"  - {q}" for q in guidance["required_questions"]])
    if guidance["missing_context"]:
        msg_lines.append("Missing context:")
        msg_lines.extend([f"  - {m}" for m in guidance["missing_context"]])

    payload = {
        "message": "\n".join(msg_lines),
        "status": status,
        "task_type": guidance["task_type"],
        "risk_level": guidance["risk_level"],
        "missing_context": guidance["missing_context"],
        "assumptions": guidance["assumptions"],
        "required_questions": guidance["required_questions"],
        "suggested_questions": guidance["suggested_questions"],
        "safer_path": guidance["safer_path"],
        "recommended_packs": guidance["recommended_packs"],
    }
    return _ok("haxaml_guidance", payload)


@mcp_app.tool()
def haxaml_session_start(task: str, description: str = "", project_dir: str = ".") -> dict:
    """Start a governed agent session with guidance and read policy checks."""
    frame = load_frame_data(project_dir)
    if not frame.get("facts"):
        return _err("haxaml_session_start", "missing_facts", "facts.yaml not found")

    try:
        runner = ExecutionRunner(project_dir)
        pre = runner.start_run(task=task, description=description)
        if pre.result == "failed":
            return _err(
                "haxaml_session_start",
                "preflight_failed",
                "Session failed preflight.",
                {"errors": pre.errors},
            )
    except FileNotFoundError as e:
        return _err("haxaml_session_start", "missing_frame", str(e))

    guidance = _guidance_eval(task, frame)
    read_policy = _session_read_policy(frame)
    session_id = f"session-{uuid.uuid4().hex[:10]}"
    now = _now_iso()

    sm, _ = _get_state_manager(project_dir)
    warnings = []
    if sm:
        state = sm.read()
        sessions = state.get("sessions", [])
        if not isinstance(sessions, list):
            sessions = []
        sessions.append(
            {
                "id": session_id,
                "task": task,
                "description": description,
                "status": "started",
                "phase": "start",
                "risk_level": guidance["risk_level"],
                "guidance_status": guidance["status"],
                "started": now,
                "updated": now,
            }
        )
        state["sessions"] = sessions
        state["active_task"] = {
            "name": task,
            "description": description,
            "started": now,
            "assignee": "agent",
        }
        compaction = state.get("context_compaction", {})
        if not isinstance(compaction, dict):
            compaction = {}
        started = compaction.get("sessions_started", 0)
        if not isinstance(started, int) or started < 0:
            started = 0
        compaction["sessions_started"] = started + 1
        state["context_compaction"] = compaction
        err = _persist_state(sm, state)
        if err:
            warnings.append(f"Could not persist session state: {err}")
    else:
        warnings.append("acts.yaml not found; session was not persisted.")

    payload = {
        "message": (
            f"Session started: {session_id}\n"
            f"Status: {guidance['status']}\n"
            f"Risk: {guidance['risk_level']}\n"
            f"Required reads: {', '.join(read_policy['required_reads'])}"
        ),
        "session_id": session_id,
        "status": guidance["status"],
        "risk_level": guidance["risk_level"],
        "task_type": guidance["task_type"],
        "required_questions": guidance["required_questions"],
        "required_reads": read_policy["required_reads"],
        "recommended_context_packs": guidance["recommended_packs"],
        "onboarding": {
            "needs_full_reads": read_policy["needs_full_reads"],
            "sessions_started": read_policy["sessions_started"],
            "onboarding_full_reads": read_policy["onboarding_full_reads"],
        },
    }
    return _ok("haxaml_session_start", payload, warnings=warnings)


@mcp_app.tool()
def haxaml_session_plan(
    session_id: str,
    project_dir: str = ".",
) -> dict:
    """Generate a short execution plan and risk check for a started session."""
    sm, _ = _get_state_manager(project_dir)
    if not sm:
        return _err("haxaml_session_plan", "missing_acts", "acts.yaml not found")

    state = sm.read()
    session = _find_session(state, session_id)
    if not session:
        return _err("haxaml_session_plan", "unknown_session", f"Session not found: {session_id}")

    task = str(session.get("task", ""))
    frame = load_frame_data(project_dir)
    guidance = _guidance_eval(task, frame)
    rules = frame.get("rules") or {}
    verify_expect = ((rules.get("after_task") or {}).get("verify", []) or [])
    if not verify_expect:
        verify_expect = [
            "Confirm changes satisfy task scope.",
            "Run relevant validation/tests.",
            "Record unresolved risks and follow-ups.",
        ]

    plan = [
        "Inspect context pack and required rules for this task.",
        "Apply smallest logical change set in scoped files.",
        "Run validations/tests for touched behavior.",
        "Run reflective verification before record.",
    ]
    if guidance["status"] == "action_required":
        plan.insert(0, "Resolve required clarification questions before code changes.")

    session["phase"] = "plan"
    session["status"] = "planned"
    session["updated"] = _now_iso()
    session["plan"] = plan
    err = _persist_state(sm, state)
    warnings = [f"Could not persist session plan: {err}"] if err else []

    return _ok(
        "haxaml_session_plan",
        {
            "message": f"Session plan prepared for {session_id}",
            "session_id": session_id,
            "status": guidance["status"],
            "risk_level": guidance["risk_level"],
            "plan": plan,
            "risk_checks": guidance["assumptions"] + guidance["missing_context"],
            "verification_expectations": verify_expect,
        },
        warnings=warnings,
    )


@mcp_app.tool()
def haxaml_context_pack(
    task: str,
    project_dir: str = ".",
    pack: str = "balanced",
    include_state: bool = True,
) -> dict:
    """Build compact task-specific context packs for token-efficient agent runs."""
    frame = load_frame_data(project_dir)
    if not frame.get("facts"):
        return _err("haxaml_context_pack", "missing_facts", "facts.yaml not found")

    pack_data = build_context_pack(project_dir, task=task, pack=pack, include_state=include_state)
    text = format_context_pack(pack_data)
    tokens = count_tokens(text)

    sm, _ = _get_state_manager(project_dir)
    warnings = []
    if sm:
        state = sm.read()
        compaction = state.get("context_compaction", {})
        if not isinstance(compaction, dict):
            compaction = {}
        compaction["last_pack_tokens"] = tokens
        if pack in ("minimal", "balanced", "full"):
            compaction["default_pack"] = pack
        state["context_compaction"] = compaction
        err = _persist_state(sm, state)
        if err:
            warnings.append(f"Could not persist context compaction stats: {err}")

    return _ok(
        "haxaml_context_pack",
        {
            "message": text,
            "context_pack": pack_data,
            "tokens": tokens,
            "pack": pack,
        },
        warnings=warnings,
    )


@mcp_app.tool()
def haxaml_session_verify(
    task: str,
    project_dir: str = ".",
    session_id: str = "",
    inspected_context: Optional[list[str]] = None,
    changed_files: Optional[list[str]] = None,
    unresolved_questions: Optional[list[str]] = None,
    assumptions: Optional[list[str]] = None,
    summary: str = "",
) -> dict:
    """Run reflective verification checks and store evidence in acts.yaml."""
    frame = load_frame_data(project_dir)
    if not frame.get("facts"):
        return _err("haxaml_session_verify", "missing_facts", "facts.yaml not found")

    rules = frame.get("rules") or {}
    guidance = _guidance_eval(task, frame)
    inspected_context = inspected_context or []
    changed_files = changed_files or []
    unresolved_questions = unresolved_questions or []
    assumptions = assumptions or []

    required_reads = ((rules.get("before_task") or {}).get("read_first", []) or [])
    required_checks = _rules_policy(
        rules,
        "verification_policy",
        {
            "require_checks": [
                "understood_task",
                "inspected_context",
                "changed_right_files",
                "risky_or_unrelated_touch",
                "followed_rules",
                "updated_journal",
                "unresolved_logged",
                "explained_changes",
            ],
            "allow_pass_with_risks": True,
        },
    )["require_checks"]

    risky_paths = [p for p in changed_files if any(x in p for x in (".env", "secrets", ".pem", "credentials"))]
    has_summary = bool(summary.strip())
    inspected_ok = all(path in inspected_context for path in required_reads) if required_reads else bool(inspected_context)
    unresolved_logged = bool(unresolved_questions) or guidance["status"] != "action_required"
    rule_follow_ok = not risky_paths

    checks = {
        "understood_task": (bool(task.strip()), "Task text was provided."),
        "inspected_context": (inspected_ok, "Inspected context includes required reads."),
        "changed_right_files": (bool(changed_files) or has_summary, "Changed files or summary evidence was provided."),
        "risky_or_unrelated_touch": (not risky_paths, "No risky file patterns were reported."),
        "followed_rules": (rule_follow_ok, "No forbidden risky path was reported."),
        "updated_journal": (True, "Journal update is enforced at session_record stage."),
        "unresolved_logged": (unresolved_logged, "Unresolved items were explicitly captured or not required."),
        "explained_changes": (has_summary, "Summary explains what changed and why."),
    }

    failures = [name for name in required_checks if name in checks and not checks[name][0]]
    if guidance["status"] == "action_required" and not unresolved_questions and not inspected_ok:
        verdict = "needs_clarification"
    elif not failures:
        verdict = "pass"
    elif len(failures) <= 2 and _rules_policy(rules, "verification_policy", {"allow_pass_with_risks": True}).get("allow_pass_with_risks", True):
        verdict = "pass_with_risks"
    else:
        verdict = "fail"

    check_rows = [
        {"name": name, "passed": checks[name][0], "details": checks[name][1]}
        for name in required_checks
        if name in checks
    ]

    evidence_refs = [".haxaml/facts.yaml", ".haxaml/rules.yaml", ".haxaml/acts.yaml"] + changed_files
    verification_id = f"verify-{uuid.uuid4().hex[:10]}"
    timestamp = _now_iso()

    sm, _ = _get_state_manager(project_dir)
    warnings = []
    if sm:
        state = sm.read()
        verifications = state.get("verifications", [])
        if not isinstance(verifications, list):
            verifications = []
        verifications.append(
            {
                "id": verification_id,
                "session_id": session_id or "",
                "task": task,
                "verdict": verdict,
                "summary": summary,
                "unresolved_questions": unresolved_questions,
                "assumptions": assumptions,
                "follow_ups": guidance["required_questions"] if verdict in ("fail", "needs_clarification") else [],
                "checks": check_rows,
                "evidence_refs": evidence_refs,
                "timestamp": timestamp,
            }
        )
        state["verifications"] = verifications
        if session_id:
            session = _find_session(state, session_id)
            if session:
                session["phase"] = "verify"
                session["status"] = "verified" if verdict in ("pass", "pass_with_risks") else "failed"
                session["updated"] = timestamp
        err = _persist_state(sm, state)
        if err:
            warnings.append(f"Could not persist verification report: {err}")

    message = f"Verification {verification_id}: {verdict}"
    if failures:
        message += f" ({len(failures)} failed check(s))"
    if guidance["status"] == "action_required":
        message += " — clarification needed before confident execution."

    return _ok(
        "haxaml_session_verify",
        {
            "message": message,
            "verification_id": verification_id,
            "session_id": session_id or "",
            "task": task,
            "verdict": verdict,
            "checks": check_rows,
            "evidence_refs": evidence_refs,
            "risky_paths": risky_paths,
            "unresolved_questions": unresolved_questions,
            "assumptions": assumptions,
            "follow_ups": guidance["required_questions"] if verdict in ("fail", "needs_clarification") else [],
        },
        warnings=warnings,
    )


@mcp_app.tool()
def haxaml_session_record(
    task: str,
    result: str = "success",
    project_dir: str = ".",
    session_id: str = "",
    changes: str = "",
    decisions: str = "",
    risks: str = "",
) -> dict:
    """Record a session result; enforces verification gate before success/partial record."""
    if result not in ("success", "partial", "failed"):
        return _err("haxaml_session_record", "invalid_result", f"Invalid result: {result}")

    try:
        runner = ExecutionRunner(project_dir)
    except FileNotFoundError as e:
        return _err("haxaml_session_record", "missing_frame", str(e))

    frame = load_frame_data(project_dir)
    rules = frame.get("rules") or {}
    lifecycle = _rules_policy(rules, "lifecycle", {"enforce_verify_before_record": True})
    enforce_verify = bool(lifecycle.get("enforce_verify_before_record", True))

    sm, _ = _get_state_manager(project_dir)
    state = sm.read() if sm else {}
    latest_verdict = None
    latest_verification_id = ""
    verifications = state.get("verifications", []) if isinstance(state, dict) else []
    if isinstance(verifications, list):
        for item in reversed(verifications):
            if not isinstance(item, dict):
                continue
            if session_id and item.get("session_id") != session_id:
                continue
            if item.get("task") != task:
                continue
            latest_verdict = item.get("verdict")
            latest_verification_id = str(item.get("id", ""))
            break

    reconcile = reconcile_derivation(project_dir)
    blocking_conflicts = reconcile["severity_totals"]["blocking"]
    if result in ("success", "partial") and blocking_conflicts > 0:
        return _err(
            "haxaml_session_record",
            "derivation_conflicts",
            "Cannot record success/partial while blocking derivation conflicts exist.",
            {
                "task": task,
                "session_id": session_id,
                "gate_reasons": reconcile["gate_reasons"],
                "reconcile": reconcile,
            },
        )
    if result == "failed" and blocking_conflicts > 0 and not _has_conflict_stop_reason(changes, decisions, risks):
        return _err(
            "haxaml_session_record",
            "conflict_reason_required",
            "Recording failed is allowed only when unresolved conflicts are explicitly documented as the stop reason.",
            {
                "task": task,
                "session_id": session_id,
                "required_hint": "Mention conflict/reconcile/derivation mismatch in changes, decisions, or risks.",
                "gate_reasons": reconcile["gate_reasons"],
                "reconcile": reconcile,
            },
        )

    if enforce_verify and result in ("success", "partial"):
        if latest_verdict not in ("pass", "pass_with_risks"):
            return _err(
                "haxaml_session_record",
                "verification_required",
                "Verification is required before recording success/partial results.",
                {
                    "task": task,
                    "session_id": session_id,
                    "latest_verdict": latest_verdict,
                    "allowed_verdicts": ["pass", "pass_with_risks"],
                },
            )

    run_result = runner.finish_run(
        task=task,
        result=result,
        changes=changes,
        decisions=decisions,
        risks=risks,
    )
    if run_result.errors:
        return _err(
            "haxaml_session_record",
            "run_record_error",
            "Run completed with errors.",
            {"errors": run_result.errors, "warnings": run_result.warnings},
        )

    warnings = list(run_result.warnings)
    if sm:
        state = sm.read()
        if session_id:
            session = _find_session(state, session_id)
            if session:
                session["phase"] = "record"
                session["status"] = "recorded"
                session["updated"] = _now_iso()
                session["ended"] = _now_iso()
        err = _persist_state(sm, state)
        if err:
            warnings.append(f"Could not persist session close state: {err}")

    stale = export_if_stale(project_dir, agents=["generic"])
    return _ok(
        "haxaml_session_record",
        {
            "message": f"✓ Session record complete (run {run_result.run_id}, result={result})",
            "session_id": session_id,
            "run_id": run_result.run_id,
            "token_count": run_result.token_count,
            "verification_id": latest_verification_id,
            "verification_verdict": latest_verdict,
            "gate_reasons": reconcile["gate_reasons"],
            "reconcile": reconcile,
            "auto_exported": stale,
        },
        warnings=warnings,
    )


@mcp_app.tool()
def haxaml_run(task: str, description: str = "", project_dir: str = ".") -> dict:
    """Start a governed execution run.

    Sets the active task in acts.yaml and runs preflight validation.
    Call this before starting work on a task.
    """
    started = haxaml_session_start(task=task, description=description, project_dir=project_dir)
    dep = _wrapper_deprecation("haxaml_run", ["haxaml_session_start"])
    if not started.get("ok"):
        return _err(
            "haxaml_run",
            started.get("error", {}).get("code", "session_start_failed"),
            started.get("error", {}).get("message", "Session start failed."),
            started.get("error", {}).get("details", {}),
            warnings=[dep["message"]],
        )

    payload = started.get("data", {})
    lines = [f"✓ Run started: {task}"]
    lines.append(f"  Session: {payload.get('session_id', '')}")
    lines.append(f"  Status: {payload.get('status', 'proceed')}")
    lines.append("  → Work on the task, then call haxaml_done (or haxaml_session_verify + haxaml_session_record)")
    return _ok(
        "haxaml_run",
        {
            "message": "\n".join(lines),
            "task": task,
            "session_id": payload.get("session_id", ""),
            "warnings": started.get("warnings", []),
            "deprecation": dep,
        },
        warnings=[dep["message"]],
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
    verify = haxaml_session_verify(
        task=task,
        project_dir=project_dir,
        summary=changes or decisions or risks or f"Completed task: {task}",
        changed_files=[],
        unresolved_questions=[],
        assumptions=[],
    )
    if not verify.get("ok"):
        dep = _wrapper_deprecation("haxaml_done", ["haxaml_session_verify", "haxaml_session_record"])
        return _err(
            "haxaml_done",
            verify.get("error", {}).get("code", "verify_failed"),
            verify.get("error", {}).get("message", "Verification failed."),
            verify.get("error", {}).get("details", {}),
            warnings=[dep["message"]],
        )

    record = haxaml_session_record(
        task=task,
        result=result,
        project_dir=project_dir,
        changes=changes,
        decisions=decisions,
        risks=risks,
    )
    if not record.get("ok"):
        dep = _wrapper_deprecation("haxaml_done", ["haxaml_session_verify", "haxaml_session_record"])
        return _err(
            "haxaml_done",
            record.get("error", {}).get("code", "record_failed"),
            record.get("error", {}).get("message", "Recording failed."),
            record.get("error", {}).get("details", {}),
            warnings=[dep["message"]],
        )

    payload = record.get("data", {})
    dep = _wrapper_deprecation("haxaml_done", ["haxaml_session_verify", "haxaml_session_record"])
    payload["message"] = f"{payload.get('message', '')}\n(verification: {verify.get('data', {}).get('verification_id', '')})"
    payload["deprecation"] = dep
    return _ok(
        "haxaml_done",
        payload,
        warnings=[dep["message"]],
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
def haxaml_adopt_plan(project_dir: str = ".") -> dict:
    """Inventory native instruction files and return non-destructive adoption plan."""
    payload = _adoption_plan_payload(project_dir)
    return _ok(
        "haxaml_adopt_plan",
        {
            "message": payload["human_summary"],
            **payload,
        },
    )


@mcp_app.tool()
def haxaml_reconcile(project_dir: str = ".") -> dict:
    """Return structured derivation-boundary conflict report."""
    report = reconcile_derivation(project_dir)
    if report["severity_totals"]["blocking"] > 0:
        return _err(
            "haxaml_reconcile",
            "derivation_conflicts",
            report["human_summary"],
            report,
        )
    return _ok(
        "haxaml_reconcile",
        {
            "message": report["human_summary"],
            **report,
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
    plan_payload = _adoption_plan_payload(project_dir, plan=plan)

    if not write:
        report = render_adoption_report(plan)
        return _ok(
            "haxaml_adopt",
            {
                "message": f"{report}\n---\nDry run. Call with write=True to create files.",
                "written": [],
                "dry_run": True,
                "adoption_plan": plan_payload,
            },
            warnings=["Prefer haxaml_adopt_plan for non-destructive inventory and migration planning."],
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
                "adoption_plan": plan_payload,
            },
            warnings=["Use haxaml_reconcile after edits to detect map-canonical derivation conflicts."],
        )

    return _ok(
        "haxaml_adopt",
        {
            "message": "No files written. Existing files preserved. Use force=True to overwrite.",
            "written": [],
            "dry_run": False,
            "adoption_plan": plan_payload,
        },
        warnings=["Use haxaml_adopt_plan for non-destructive planning before forceful writes."],
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
