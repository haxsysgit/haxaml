"""MCP lifecycle/session helper functions."""

from datetime import datetime, timezone
from pathlib import Path
import subprocess
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

    # Guidance treats any blocking unresolved item anywhere in FRAME as missing context
    # for the current task. This keeps the tool focused on project readiness, not just task text.
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
            safer_path.append("Use utility mode: run the task directly and keep FRAME untouched.")
            safer_path.append("When you return to project work, call guidance, then prebuild.")
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

    # Early governed sessions pay the full read cost so the agent learns the project.
    # Later sessions can usually rely on the stable high-signal subset.
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
        "removal_target": "0.7.0",
        "message": f"{tool} is a compatibility wrapper and is planned for removal in 0.7.0.",
    }


def _lifecycle_hint(
    *,
    tool: str,
    phase: str,
    depends_on: list[str],
    preferred_next: str,
    allowed_next: list[str] | None = None,
    contract_enforced: bool = True,
) -> dict[str, Any]:
    """Return compact machine-readable lifecycle dependency metadata."""
    next_tools = list(allowed_next or ([preferred_next] if preferred_next else []))
    hint = {
        "tool": tool,
        "phase": phase,
        "depends_on": list(depends_on),
        "preferred_next": preferred_next,
        "contract_enforced": contract_enforced,
    }
    if next_tools and next_tools != [preferred_next]:
        hint["allowed_next"] = next_tools
    return hint


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


def _expect_sync_state(state: dict[str, Any]) -> dict[str, Any]:
    """Return normalized expect-sync lifecycle state from acts.yaml payload."""
    raw = state.get("expect_sync", {}) if isinstance(state, dict) else {}
    if not isinstance(raw, dict):
        raw = {}
    return {
        "required": bool(raw.get("required", False)),
        "pending_run_id": str(raw.get("pending_run_id", "") or ""),
        "pending_task": str(raw.get("pending_task", "") or ""),
        "pending_result": str(raw.get("pending_result", "") or ""),
        "pending_recorded_at": str(raw.get("pending_recorded_at", "") or ""),
        "last_synced_run_id": str(raw.get("last_synced_run_id", "") or ""),
        "last_synced_at": str(raw.get("last_synced_at", "") or ""),
        "last_sync_status": str(raw.get("last_sync_status", "") or ""),
    }


def _lifecycle_contract_state(state: dict[str, Any]) -> dict[str, Any]:
    """Return normalized lifecycle contract state from acts.yaml payload."""
    raw = state.get("lifecycle_contract", {}) if isinstance(state, dict) else {}
    if not isinstance(raw, dict):
        raw = {}
    # Normalize required_next aggressively so tool gates can reason against one shape only.
    required_next = raw.get("required_next", [])
    if isinstance(required_next, str):
        required_next = [required_next]
    if not isinstance(required_next, list):
        required_next = []
    normalized_required = []
    for item in required_next:
        if isinstance(item, str) and item.strip():
            normalized_required.append(item.strip())
    # Treat missing/empty contract state as "about has not happened yet".
    if not normalized_required:
        normalized_required = ["haxaml_about"]
    return {
        "phase": str(raw.get("phase", "idle") or "idle"),
        "required_next": normalized_required,
        "active_session_id": str(raw.get("active_session_id", "") or ""),
        "active_task": str(raw.get("active_task", "") or ""),
        "last_tool": str(raw.get("last_tool", "") or ""),
        "last_verification_id": str(raw.get("last_verification_id", "") or ""),
        "last_verification_verdict": str(raw.get("last_verification_verdict", "") or ""),
        "last_record_run_id": str(raw.get("last_record_run_id", "") or ""),
        "last_record_result": str(raw.get("last_record_result", "") or ""),
        "updated_at": str(raw.get("updated_at", "") or ""),
    }


def _set_lifecycle_contract_state(state: dict[str, Any], contract: dict[str, Any]) -> None:
    """Persist normalized lifecycle contract state in acts payload."""
    clean = _lifecycle_contract_state({"lifecycle_contract": contract})
    state["lifecycle_contract"] = clean


def _contract_allows(contract: dict[str, Any], tool_name: str) -> bool:
    required_next = contract.get("required_next", [])
    if not isinstance(required_next, list):
        return False
    return tool_name in required_next


def _contract_touch(
    contract: dict[str, Any],
    *,
    phase: str,
    required_next: list[str],
    tool_name: str,
    active_session_id: str = "",
    active_task: str = "",
    last_verification_id: str = "",
    last_verification_verdict: str = "",
    last_record_run_id: str = "",
    last_record_result: str = "",
) -> dict[str, Any]:
    """Return updated contract state after a successful lifecycle transition."""
    updated = dict(contract)
    updated["phase"] = phase
    updated["required_next"] = list(required_next)
    updated["last_tool"] = tool_name
    # Keep existing session/task context unless the caller explicitly replaces it.
    # That lets small lifecycle transitions advance the contract without blanking history.
    if active_session_id or updated.get("active_session_id"):
        updated["active_session_id"] = active_session_id
    if active_task or updated.get("active_task"):
        updated["active_task"] = active_task
    if last_verification_id:
        updated["last_verification_id"] = last_verification_id
    if last_verification_verdict:
        updated["last_verification_verdict"] = last_verification_verdict
    if last_record_run_id:
        updated["last_record_run_id"] = last_record_run_id
    if last_record_result:
        updated["last_record_result"] = last_record_result
    updated["updated_at"] = _now_iso()
    return _lifecycle_contract_state({"lifecycle_contract": updated})


def _git_changed_files(project_dir: str) -> list[str]:
    """Return changed file paths (git status --porcelain) relative to project root."""
    project = Path(project_dir).resolve()
    try:
        result = subprocess.run(
            ["git", "-C", str(project), "status", "--porcelain"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return []
    if result.returncode != 0:
        return []

    files: list[str] = []
    for line in (result.stdout or "").splitlines():
        if not line.strip():
            continue
        # Porcelain output prefixes each line with XY status codes; the path starts after that.
        path_part = line[3:].strip() if len(line) > 3 else ""
        if " -> " in path_part:
            path_part = path_part.split(" -> ", 1)[1].strip()
        if path_part:
            files.append(path_part)
    return sorted(set(files))


def _is_likely_code_path(path: str) -> bool:
    path_l = path.lower().strip()
    if not path_l or path_l.startswith(".haxaml/"):
        return False
    code_exts = (
        ".py",
        ".ts",
        ".tsx",
        ".js",
        ".jsx",
        ".go",
        ".rs",
        ".java",
        ".kt",
        ".swift",
        ".c",
        ".cc",
        ".cpp",
        ".h",
        ".hpp",
        ".cs",
        ".rb",
        ".php",
        ".sh",
    )
    if path_l.endswith(code_exts):
        return True
    code_names = {
        "pyproject.toml",
        "package.json",
        "pnpm-lock.yaml",
        "uv.lock",
        "tsconfig.json",
        "vite.config.ts",
        "vite.config.js",
        "dockerfile",
        "makefile",
        "requirements.txt",
    }
    return Path(path_l).name in code_names


def _governed_code_changes(project_dir: str) -> list[str]:
    """Return changed paths likely to represent governed code/config changes."""
    return [path for path in _git_changed_files(project_dir) if _is_likely_code_path(path)]


def _has_governed_evidence_for_changes(state: dict[str, Any], changed_files: list[str]) -> bool:
    """Determine whether acts state contains governed evidence for current changed files."""
    if not changed_files:
        return True

    # An active governed session is enough evidence that the repo is in a live governed flow,
    # even before file-level verification evidence has been written.
    sessions = state.get("sessions", []) if isinstance(state, dict) else []
    if isinstance(sessions, list):
        for session in sessions:
            if not isinstance(session, dict):
                continue
            if str(session.get("execution_mode", "")).strip() != "governed":
                continue
            if str(session.get("status", "")).strip() in {"started", "planned", "verified", "recorded"}:
                return True

    # When no active session can justify the changes, fall back to file-level verification evidence.
    verifications = state.get("verifications", []) if isinstance(state, dict) else []
    evidence_files: set[str] = set()
    if isinstance(verifications, list):
        for item in reversed(verifications):
            if not isinstance(item, dict):
                continue
            if str(item.get("verdict", "")).strip() not in {"pass", "pass_with_risks"}:
                continue
            refs = item.get("evidence_refs", [])
            if not isinstance(refs, list):
                continue
            for ref in refs:
                if isinstance(ref, str) and _is_likely_code_path(ref):
                    evidence_files.add(ref.strip())

    if not evidence_files:
        return False
    return all(path in evidence_files for path in changed_files)
