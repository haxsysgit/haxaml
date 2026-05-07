"""haxaml_prebuild MCP tool — prebuild phase for v0.6.

Lifecycle position:
    about -> guidance -> prebuild -> context_pack -> build -> verify -> record -> expect_sync

haxaml_prebuild is the public governed entrypoint. It classifies the task, runs
semantic validation, produces a structured readiness report, starts a governed
session internally, and advances the lifecycle contract to allow
haxaml_context_pack.
"""

from __future__ import annotations

import uuid

from haxaml.frame_model import FrameModel
from haxaml.prebuild_templates import (
    HIGH_RISK_TASK_TYPES,
    classify_task,
    context_policy_for,
    get_template,
)
from haxaml.validator import semantic_validate
from haxaml.validator import frame_consistency_report

from haxaml.mcp.base import (
    _contract_allows,
    _contract_touch,
    _err,
    _get_state_manager,
    _guidance_eval,
    _lifecycle_hint,
    _lifecycle_contract_state,
    _normalize_detail,
    _now_iso,
    _ok,
    _persist_state,
    _require_about,
    _set_lifecycle_contract_state,
    _utility_mode_eval,
    _utility_mode_error,
    _utility_mode_policy,
    mcp_app,
    DETAIL_SHORT,
    ExecutionRunner,
)


# Utility tasks that should not trigger governed session start
_UTILITY_KEYWORDS = {
    "list", "show", "search", "grep", "find", "what is", "explain",
    "read", "display", "summarize recent", "check status",
}


def _is_utility(task: str, description: str = "") -> bool:
    text = f"{task} {description}".lower().strip()
    return any(kw in text for kw in _UTILITY_KEYWORDS)


def _readiness_from_health(
    health_blocking: list[str],
    health_warnings: list[str],
    task_type: str,
    risk: str,
    required_questions: list[str],
) -> tuple[str, str]:
    """Determine (readiness_status, next_step) from frame health + task context."""

    if health_blocking:
        is_policy_issue = any(
            "policy" in b or "lifecycle" in b or "stale" in b
            for b in health_blocking
        )
        if is_policy_issue:
            return "blocked_by_policy", "fix_frame_health"
        return "blocked_by_missing_context", "fix_frame_health"

    if required_questions and risk == "high":
        return "needs_user_input", "ask_user"

    if risk == "high" and health_warnings:
        return "ready_to_build_with_warnings", "haxaml_context_pack"

    if health_warnings:
        return "ready_to_build_with_warnings", "haxaml_context_pack"

    return "ready_to_build", "haxaml_context_pack"


@mcp_app.tool()
def haxaml_prebuild(
    task: str,
    description: str = "",
    project_dir: str = ".",
    detail: str = DETAIL_SHORT,
) -> dict:
    """Prebuild phase: classify task, validate FRAME, produce readiness report, start session.

    Must be called after haxaml_about and haxaml_guidance.

    Returns a structured readiness report including:
    - readiness_status: ready_to_build | ready_to_build_with_warnings |
                        needs_user_input | needs_project_inspection |
                        blocked_by_missing_context | blocked_by_conflict |
                        blocked_by_policy | utility_mode
    - task_type: one of 12 domain types
    - guidance_type: one of 5 abstract guidance types
    - classification_reason
    - required_questions, materials_needed, done_criteria, likely_impact, risks
    - context_policy
    - frame_health (blocking + warnings from semantic validation)
    - plan, verification_expectations
    - session_id
    - next_step
    """
    detail_mode, detail_err = _normalize_detail("haxaml_prebuild", detail)
    if detail_err:
        return detail_err

    # --- gate: about required ---
    about_required = _require_about("haxaml_prebuild", project_dir)
    if about_required:
        details = ((about_required.get("error") or {}).get("details") or {})
        details["hint"] = "Call haxaml_about once per MCP session, then haxaml_guidance, then haxaml_prebuild."
        return _err(
            "haxaml_prebuild",
            "about_required",
            "haxaml_about must be called before haxaml_prebuild.",
            details,
        )

    # --- utility mode check ---
    mode_eval = _utility_mode_eval(task, description)
    if mode_eval["mode"] == "utility":
        return _ok(
            "haxaml_prebuild",
            {
                "message": "Utility task detected. No governed session required.",
                "readiness_status": "utility_mode",
                "task": task,
                "next_step": "run_outside_governed_flow",
                "policy": _utility_mode_policy(),
            },
            detail=detail_mode,
        )

    # --- load FrameModel ---
    frame = FrameModel.load(project_dir)
    if not frame.has_facts():
        return _err(
            "haxaml_prebuild",
            "missing_facts",
            "facts.yaml not found — cannot run prebuild without FRAME. "
            "Run haxaml_init to create FRAME files.",
        )

    # --- semantic validation ---
    sem = semantic_validate(frame)
    consistency = frame_consistency_report(frame)
    progress_summary = {
        "status": consistency["status"],
        "reason": consistency["reason"],
    }
    frame_health = {
        "blocking": list(sem.blocking),
        "warnings": list(sem.warnings),
    }

    # --- classify task ---
    task_type, guidance_type, classification_reason = classify_task(task, description)
    tmpl = get_template(task_type) or {}
    risk = tmpl.get("risk", "medium")

    # --- build readiness status ---
    required_questions = list(tmpl.get("required_questions") or [])
    readiness_status, next_step = _readiness_from_health(
        sem.blocking,
        sem.warnings,
        task_type,
        risk,
        required_questions,
    )
    if readiness_status == "ready_to_build" and consistency["status"] != "on_track":
        readiness_status = "ready_to_build_with_warnings"

    # --- context policy ---
    ctx_policy = context_policy_for(task_type, risk)

    # --- verify expectations from rules ---
    rules = frame.rules or {}
    verify_expect_raw = ((rules.get("after_task") or {}).get("verify", []) or [])
    verification_expectations = [
        item.strip() for item in verify_expect_raw
        if isinstance(item, str) and item.strip()
    ]
    if not verification_expectations:
        verification_expectations = [
            "Confirm changes satisfy the done criteria.",
            "Run relevant tests or validation.",
            "Record unresolved risks and follow-ups.",
        ]

    # --- default plan ---
    plan = [
        "Review the readiness report and clarify any required questions.",
        "Call haxaml_context_pack to load task-scoped context.",
        "Apply the smallest logical change set within the scoped files.",
        "Run validations or tests for touched behavior.",
        "Call haxaml_session_verify before haxaml_session_record.",
    ]

    # --- start governed session (only if readiness allows) ---
    session_id = f"session-{uuid.uuid4().hex[:10]}"
    warnings: list[str] = []

    if readiness_status in ("ready_to_build", "ready_to_build_with_warnings", "needs_project_inspection"):
        sm, _ = _get_state_manager(project_dir)
        if sm:
            state = sm.read()
            contract = _lifecycle_contract_state(state)

            if not _contract_allows(contract, "haxaml_prebuild"):
                # Check if guidance has been called
                phase = contract.get("phase", "")
                if phase not in ("guidance", "about"):
                    return _err(
                        "haxaml_prebuild",
                        "lifecycle_contract_violation",
                        "haxaml_prebuild must be called after haxaml_guidance.",
                        {
                            "current_phase": phase,
                            "required_next": contract.get("required_next", []),
                            "hint": "Call haxaml_guidance(task=...) before haxaml_prebuild.",
                        },
                    )

            try:
                runner = ExecutionRunner(project_dir)
                pre = runner.start_run(task=task, description=description)
                if pre.result == "failed":
                    warnings.append(
                        f"Session preflight raised issues: {'; '.join(pre.errors or [])}"
                    )
            except Exception as exc:
                warnings.append(f"Runner start skipped: {exc}")

            now = _now_iso()
            frame_dict = {
                "facts": frame.facts,
                "rules": frame.rules,
                "acts": frame.acts,
                "map": frame.map,
                "expect": frame.expect,
            }
            guidance = _guidance_eval(task, frame_dict)

            sessions = state.get("sessions", [])
            if not isinstance(sessions, list):
                sessions = []
            sessions.append(
                {
                    "id": session_id,
                    "task": task,
                    "description": description,
                    "execution_mode": "governed",
                    "status": "planned",
                    "phase": "prebuild",
                    "risk_level": risk,
                    "task_type": task_type,
                    "guidance_type": guidance_type,
                    "readiness_status": readiness_status,
                    "started": now,
                    "updated": now,
                    "plan": plan,
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

            contract = _contract_touch(
                contract,
                phase="prebuild",
                required_next=["haxaml_context_pack"],
                tool_name="haxaml_prebuild",
                active_session_id=session_id,
                active_task=task,
            )
            _set_lifecycle_contract_state(state, contract)
            err = _persist_state(sm, state)
            if err:
                warnings.append(f"Could not persist prebuild session state: {err}")
        else:
            warnings.append("acts.yaml not found — session was not persisted.")
    else:
        # Blocked or needs input — don't start a session yet, but still return a session_id
        # so the caller knows what to reference if they resolve and retry
        session_id = ""

    payload: dict = {
        "message": (
            f"Prebuild complete: {readiness_status}\n"
            f"Progress: {progress_summary['status']} — {progress_summary['reason']}\n"
            f"Next step: {next_step}"
        ),
        "session_id": session_id,
        "readiness_status": readiness_status,
        "task_type": task_type,
        "guidance_type": guidance_type,
        "classification_reason": classification_reason,
        "required_questions": required_questions,
        "materials_needed": list(tmpl.get("materials_needed") or []),
        "done_criteria": list(tmpl.get("done_criteria") or []),
        "likely_impact": list(tmpl.get("likely_impact") or []),
        "risks": list(tmpl.get("risks") or []),
        "context_policy": ctx_policy,
        "frame_health": frame_health,
        "progress_summary": progress_summary,
        "plan": plan,
        "verification_expectations": verification_expectations,
        "next_step": next_step,
        "lifecycle": _lifecycle_hint(
            tool="haxaml_prebuild",
            phase="prebuild",
            depends_on=["haxaml_about", "haxaml_guidance"],
            preferred_next=next_step,
            allowed_next=[next_step] if next_step.startswith("haxaml_") else [],
            contract_enforced=next_step.startswith("haxaml_"),
        ),
    }

    return _ok("haxaml_prebuild", payload, warnings=warnings, detail=detail_mode)
