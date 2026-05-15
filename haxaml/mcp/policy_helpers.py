"""MCP policy and gating helpers."""

from pathlib import Path
from typing import Any, Optional

from haxaml.mcp.app_core import (
    ABOUT_PROMPT_VERSION,
    UTILITY_TASK_HINTS,
    _ABOUT_ACK_CACHE,
    _RETRY_GUARD_CACHE,
)
from haxaml.mcp.response_helpers import _err
from haxaml.versioning import get_version

CONTEXT_PACK_LIMIT_TEXT = "One context_pack per task by default; repeat only with scope-change or stale-context reason."
VISIBILITY_POLICY_TEXT = "Optional diagnostics only; use on failure, uncertainty, or pre-final check."
RETRY_POLICY_TEXT = "If the same gate error appears twice, stop retrying and fix the root cause."
UTILITY_RESUME_RULE = "When you return to project work, resume with haxaml_guidance then haxaml_prebuild."
CONTEXT_REFRESH_REASON_EXAMPLES = {
    "scope_change": [
        "scope changed to include billing module",
        "need context for the queue worker added to this task",
    ],
    "stale_context": [
        "context stale after major file updates",
        "tests changed after review and the pack is stale",
    ],
    "review_follow_up": [
        "follow-up after review comments changed the task focus",
        "verification found new files to inspect before record",
    ],
    "user_redirect": [
        "user redirected the task to auth cleanup",
        "new requirement added by the user changed the scope",
    ],
}


def _workflow_budget_catalog() -> dict[str, dict[str, Any]]:
    return {
        "debug": {
            "target_calls": 7,
            "max_calls_without_visibility": 8,
            "max_calls_with_visibility": 12,
        },
        "implementation": {
            "target_calls": 7,
            "max_calls_without_visibility": 9,
            "max_calls_with_visibility": 13,
        },
        "design": {
            "target_calls": 6,
            "max_calls_without_visibility": 8,
            "max_calls_with_visibility": 12,
        },
        "strategy": {
            "target_calls": 6,
            "max_calls_without_visibility": 8,
            "max_calls_with_visibility": 12,
        },
        "outcome": {
            "target_calls": 7,
            "max_calls_without_visibility": 9,
            "max_calls_with_visibility": 13,
        },
    }


def _call_budget_for(task_type: str, risk_level: str) -> dict[str, Any]:
    catalog = _workflow_budget_catalog()
    visibility = ["haxaml_health", "haxaml_needs", "haxaml_reconcile", "haxaml_state_show"]
    base = catalog.get(task_type, catalog["implementation"]).copy()
    # High-risk work gets a slightly larger budget before extra calls count as drift/noise.
    if risk_level == "high":
        base["max_calls_without_visibility"] += 1
        base["max_calls_with_visibility"] += 1
    base["recommended_detail"] = "short"
    base["recommended_profile"] = f"lean_{task_type}"
    base["workflow"] = [
        "haxaml_about",
        "haxaml_guidance",
        "haxaml_prebuild",
        "haxaml_context_pack",
        "haxaml_session_verify",
        "haxaml_session_record",
        "haxaml_expect_sync",
    ]
    base["optional_visibility_calls"] = visibility
    return base


def _project_key(project_dir: str) -> str:
    return str(Path(project_dir).resolve())


def _retry_guard_key(
    project_dir: str,
    tool: str,
    error_code: str,
    task: str = "",
    session_id: str = "",
) -> str:
    norm_task = " ".join(task.lower().split()) if task else ""
    return "::".join(
        [
            _project_key(project_dir),
            tool,
            error_code,
            norm_task,
            session_id.strip(),
        ]
    )


def _retry_guard_clear(
    project_dir: str,
    tool: str = "",
    error_code: str = "",
    task: str = "",
    session_id: str = "",
) -> None:
    project_prefix = _project_key(project_dir)
    keys = list(_RETRY_GUARD_CACHE.keys())
    for key in keys:
        if not key.startswith(project_prefix):
            continue
        if tool and f"::{tool}::" not in key:
            continue
        if error_code and f"::{error_code}::" not in key:
            continue
        if task and f"::{' '.join(task.lower().split())}::" not in key:
            continue
        if session_id and not key.endswith(f"::{session_id.strip()}"):
            continue
        # Clearing without filters resets the whole project's retry guard state.
        if not any([tool, error_code, task, session_id]):
            _RETRY_GUARD_CACHE.pop(key, None)
            continue
        if any([tool, error_code, task, session_id]):
            _RETRY_GUARD_CACHE.pop(key, None)


def _context_refresh_policy() -> dict[str, Any]:
    return {
        "summary": CONTEXT_PACK_LIMIT_TEXT,
        "reason_categories": list(CONTEXT_REFRESH_REASON_EXAMPLES.keys()),
        "examples": CONTEXT_REFRESH_REASON_EXAMPLES,
    }


def _compact_context_refresh_policy() -> dict[str, Any]:
    return {
        "summary": CONTEXT_PACK_LIMIT_TEXT,
        "reason_categories": list(CONTEXT_REFRESH_REASON_EXAMPLES.keys()),
    }


def _normalize_context_refresh_reason(refresh_reason: str) -> dict[str, Any]:
    normalized = " ".join(str(refresh_reason or "").strip().split())
    if not normalized:
        return {"reason": "", "category": "", "too_vague": False}

    lower = normalized.lower()
    vague_tokens = {
        "again",
        "retry",
        "refresh",
        "more context",
        "update",
        "updated",
        "stale",
        "scope changed",
    }
    # Repeat context loads are allowed, but only when the caller can explain what changed.
    if len(lower) < 16 or lower in vague_tokens:
        return {"reason": normalized, "category": "", "too_vague": True}

    if any(word in lower for word in ("scope", "include", "expand", "module", "component")):
        category = "scope_change"
    elif any(word in lower for word in ("stale", "updated", "changed", "after edit", "after update", "new file", "tests")):
        category = "stale_context"
    elif any(word in lower for word in ("review", "follow-up", "verify", "verification", "reconcile")):
        category = "review_follow_up"
    elif any(word in lower for word in ("user", "requirement", "redirect", "requested")):
        category = "user_redirect"
    else:
        category = "other_context_shift"
    return {"reason": normalized, "category": category, "too_vague": False}


def _utility_mode_policy() -> dict[str, Any]:
    return {
        "governed_mode": "Use the Haxaml lifecycle only for real project work.",
        "utility_mode": "Run the task directly and keep FRAME unchanged.",
        "resume_rule": UTILITY_RESUME_RULE,
    }


def _gate_error_with_retry_policy(
    tool: str,
    error_code: str,
    message: str,
    *,
    project_dir: str,
    task: str = "",
    session_id: str = "",
    details: Optional[dict] = None,
) -> dict:
    key = _retry_guard_key(project_dir, tool, error_code, task=task, session_id=session_id)
    attempts = _RETRY_GUARD_CACHE.get(key, 0) + 1
    _RETRY_GUARD_CACHE[key] = attempts
    base_details = dict(details or {})
    base_details["retry_policy"] = {
        "attempt": attempts,
        "same_error_block_after": 2,
        "next_step": "Fix the root cause before retrying again.",
    }
    if attempts >= 2:
        return _err(
            tool,
            "retry_policy_blocked",
            "Same gate error appeared twice. Stop retrying, fix root cause, then retry once.",
            {
                **base_details,
                "original_error_code": error_code,
            },
        )
    return _err(tool, error_code, message, base_details)


def _utility_mode_eval(task: str, description: str = "") -> dict[str, Any]:
    text = f"{task}\n{description}".strip().lower()
    if text.startswith("[governed]") or text.startswith("governed:"):
        return {"mode": "governed", "matched_hints": [], "reason": "Explicit governed marker was provided."}
    if text.startswith("[utility]") or text.startswith("utility:"):
        return {"mode": "utility", "matched_hints": ["explicit_utility_marker"], "reason": "Explicit utility marker was provided."}

    hits = [hint for hint in UTILITY_TASK_HINTS if hint in text]
    if hits:
        return {
            "mode": "utility",
            "matched_hints": sorted(set(hits)),
            "reason": "Task text matches utility/off-topic hints. Keep FRAME untouched for this task.",
        }
    return {"mode": "governed", "matched_hints": [], "reason": "No utility hints detected."}


def _utility_mode_error(tool: str, project_dir: str, task: str, description: str = "") -> dict:
    mode = _utility_mode_eval(task, description)
    return _err(
        tool,
        "utility_mode_task",
        "Task is utility-mode. Do not run governed lifecycle tools or modify .haxaml/* for this task.",
        {
            "mode": mode,
            "project_dir": str(Path(project_dir).resolve()),
            "policy": _utility_mode_policy(),
        },
    )


def _about_ack_status(project_dir: str) -> dict[str, Any]:
    key = _project_key(project_dir)
    acknowledged = key in _ABOUT_ACK_CACHE
    return {
        "acknowledged": acknowledged,
        "acknowledged_at": "runtime_cache" if acknowledged else "",
        "prompt_version": ABOUT_PROMPT_VERSION if acknowledged else "",
        "haxaml_version": get_version(),
        "source": "runtime_cache" if acknowledged else "missing_runtime_ack",
    }


def _require_about(tool: str, project_dir: str) -> Optional[dict]:
    status = _about_ack_status(project_dir)
    if status["acknowledged"]:
        return None
    return _err(
        tool,
        "about_required",
        "Call haxaml_about once per active agent/MCP session before governed lifecycle tools.",
        {
            "required_before": "haxaml_prebuild",
            "project_dir": str(Path(project_dir).resolve()),
            "about_status": status,
            "retry_after": [
                "haxaml_about(project_dir='.')",
                f"{tool}(...)",
            ],
        },
    )


def _about_payload(project_dir: str) -> dict[str, Any]:
    project = Path(project_dir).resolve()
    facts_path = project / ".haxaml" / "facts.yaml"
    manifest_path = project / ".haxaml" / "setup" / "manifest.yaml"
    if not facts_path.exists():
        onboarding = {
            "status": "missing_frame",
            "recommended_tool": "haxaml_setup",
            "message": "Project is not initialized. Run `haxaml setup` or call `haxaml_setup` to install FRAME and agent-native onboarding.",
        }
        next_step = "haxaml_setup"
    elif not manifest_path.exists():
        onboarding = {
            "status": "frame_only",
            "recommended_tool": "haxaml_setup",
            "message": "FRAME exists, but setup-managed onboarding is missing. Run `haxaml setup` or call `haxaml_setup` to adopt or install native instructions.",
        }
        next_step = "haxaml_setup"
    else:
        onboarding = {
            "status": "setup_managed",
            "recommended_tool": "haxaml_guidance",
            "message": "Setup-managed onboarding is present. Continue with the governed lifecycle.",
        }
        next_step = "haxaml_guidance"

    call_budgets = _workflow_budget_catalog()
    return {
        "message": "Haxaml onboarding brief loaded. Call haxaml_about once per active agent/MCP session.",
        "about_version": ABOUT_PROMPT_VERSION,
        "project_dir": str(project),
        "haxaml": {
            "what_it_is": (
                "Haxaml is a deterministic governance layer for coding agents. "
                "It supervises execution through MCP tools and FRAME state."
            ),
            "core_value": "Keep context, decisions, and verification explicit instead of prompt-only.",
        },
        "frame": {
            "what_it_is": "FRAME is the project governance source of truth used by Haxaml.",
            "files": {
                "facts": ".haxaml/facts.yaml",
                "rules": ".haxaml/rules.yaml",
                "acts": ".haxaml/acts.yaml",
                "expect": ".haxaml/expect.yaml",
                "map": ".haxaml/map.yaml (optional until required by complexity policy)",
            },
        },
        "agent_prompt": {
            "role": "You are an engineer and Haxaml is your supervisor.",
            "contract": [
                "Call haxaml_about once per active agent/MCP session.",
                "Use FRAME files as operating truth.",
                "Run the governed lifecycle in order: about → guidance → prebuild → context_pack → build → verify → record → expect_sync.",
                "Treat visibility calls as optional diagnostics, not default every run.",
            ],
        },
        "modes": {
            "governed": "Project work. Use Haxaml lifecycle and FRAME journaling.",
            "utility": "Side task or unrelated request. Do not call lifecycle tools; do not edit .haxaml/*.",
            "resume_rule": UTILITY_RESUME_RULE,
        },
        "safety_rule": "Only read/write FRAME files when the task is explicitly project-governed.",
        "anti_bloat_policy": {
            "context_pack_limit": CONTEXT_PACK_LIMIT_TEXT,
            "visibility_calls": "health/needs/reconcile/state_show are optional diagnostics, not default loop calls.",
            "retry_behavior": "If the same gate error appears twice, stop retries, fix root cause, then retry once.",
            "context_refresh_policy": _compact_context_refresh_policy(),
        },
        "onboarding": onboarding,
        # Keep the onboarding payload high-signal: enough structure to guide the first call chain,
        # but not so much detail that "full" mode becomes its own source of context bloat.
        "recommended_workflow": {
            "phase_summary": "about → guidance → prebuild → context_pack → build → verify → record → expect_sync",
            "lean_default": [
                "haxaml_about",
                "haxaml_guidance",
                "haxaml_prebuild",
                "haxaml_context_pack",
                "haxaml_session_verify",
                "haxaml_session_record",
                "haxaml_expect_sync",
            ],
            "visibility_calls_optional": ["haxaml_health", "haxaml_needs", "haxaml_reconcile", "haxaml_state_show"],
        },
        "lifecycle": {
            "tool": "haxaml_about",
            "phase": "about",
            "depends_on": [],
            "preferred_next": next_step,
        },
        "next_step": next_step,
        "call_budgets": call_budgets,
    }
