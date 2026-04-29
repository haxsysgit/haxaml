"""MCP lifecycle/session helper functions."""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from haxaml.paths import resolve_frame_file
from haxaml.state_manager import StateError, StateManager

from haxaml.mcp.policy_helpers import _utility_mode_eval


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
    mode_eval = _utility_mode_eval(task)
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
    if mode_eval["mode"] == "utility":
        status = "action_required"
        required_questions.append("This looks like a utility/off-topic task. Keep FRAME untouched and run it outside governed lifecycle.")
    if mode == "hard_block" and (required_questions or missing_context):
        status = "action_required"
    elif mode == "risk_gated_soft_block" and risk_level == "high" and required_questions:
        status = "action_required"

    safer_path = []
    if status == "action_required":
        if mode_eval["mode"] == "utility":
            safer_path.append("Use utility mode: do not call lifecycle tools and do not edit .haxaml/*.")
            safer_path.append("When you return to project work, resume with guidance -> session_start.")
        else:
            safer_path.append("Resolve required clarification questions before code changes.")
            safer_path.append("Use `haxaml_context_pack` to gather only task-relevant context.")
    else:
        safer_path.append("Proceed with a minimal plan and verify against FRAME before record.")

    return {
        "execution_mode": mode_eval["mode"],
        "mode_reason": mode_eval["reason"],
        "mode_hints": mode_eval["matched_hints"],
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
