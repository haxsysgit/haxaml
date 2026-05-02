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
    if risk_level == "high":
        base["max_calls_without_visibility"] += 1
        base["max_calls_with_visibility"] += 1
    base["recommended_detail"] = "short"
    base["recommended_profile"] = f"lean_{task_type}"
    base["workflow"] = [
        "haxaml_about",
        "haxaml_guidance",
        "haxaml_session_start",
        "haxaml_session_plan",
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
        if not any([tool, error_code, task, session_id]):
            _RETRY_GUARD_CACHE.pop(key, None)
            continue
        if any([tool, error_code, task, session_id]):
            _RETRY_GUARD_CACHE.pop(key, None)


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
            "policy": {
                "governed_mode": "Use Haxaml lifecycle only for project work.",
                "utility_mode": "Run task directly without Haxaml lifecycle and keep FRAME unchanged.",
                "resume_rule": "When you return to project work, resume with haxaml_guidance then haxaml_session_start.",
            },
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
        "Call haxaml_about once per active agent/MCP session before haxaml_session_start.",
        {
            "required_before": "haxaml_session_start",
            "project_dir": str(Path(project_dir).resolve()),
            "about_status": status,
            "retry_after": [
                "haxaml_about(project_dir='.')",
                f"{tool}(...)",
            ],
        },
    )


def _about_payload(project_dir: str) -> dict[str, Any]:
    call_budgets = _workflow_budget_catalog()
    return {
        "message": "Haxaml onboarding brief loaded. Call haxaml_about once per active agent/MCP session.",
        "about_version": ABOUT_PROMPT_VERSION,
        "project_dir": str(Path(project_dir).resolve()),
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
                "Run the governed lifecycle in order: about → guidance → prebuild (session_start, session_plan, context_pack) → build → verify → record (session_record, expect_sync).",
                "Treat visibility calls as optional diagnostics, not default every run.",
            ],
        },
        "modes": {
            "governed": "Project work. Use Haxaml lifecycle and FRAME journaling.",
            "utility": "Side task or unrelated request. Do not call lifecycle tools; do not edit .haxaml/*.",
            "resume_rule": "After utility work, resume governed lifecycle when returning to project tasks.",
        },
        "safety_rule": "Only read/write FRAME files when the task is explicitly project-governed.",
        "anti_bloat_policy": {
            "context_pack_limit": "One context_pack per task by default; repeat only with scope-change/stale-context reason.",
            "visibility_calls": "health/needs/reconcile/state_show are optional diagnostics, not default loop calls.",
            "retry_behavior": "If the same gate error appears twice, stop retries, fix root cause, then retry once.",
        },
        "recommended_workflow": {
            "phase_summary": "about → guidance → prebuild → build → verify → record",
            "phase_groups": {
                "about": ["haxaml_about"],
                "guidance": ["haxaml_guidance"],
                "prebuild": ["haxaml_session_start", "haxaml_session_plan", "haxaml_context_pack"],
                "build": [],
                "verify": ["haxaml_session_verify"],
                "record": ["haxaml_session_record", "haxaml_expect_sync"],
            },
            "lean_default": [
                "haxaml_about",
                "haxaml_guidance",
                "haxaml_session_start",
                "haxaml_session_plan",
                "haxaml_context_pack",
                "haxaml_session_verify",
                "haxaml_session_record",
                "haxaml_expect_sync",
            ],
            "visibility_calls_optional": ["haxaml_health", "haxaml_needs", "haxaml_reconcile", "haxaml_state_show"],
            "detail_policy": {
                "default": "short",
                "use_full_for": ["deep debugging", "schema inspection", "unexpected workflow behavior"],
            },
        },
        "call_budgets": call_budgets,
    }
