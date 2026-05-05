"""MCP response formatting and compaction helpers."""

import re
from typing import Any, Optional

from haxaml.mcp.app_core import DETAIL_FULL, DETAIL_MODES, DETAIL_SHORT


def _pick_fields(payload: dict, keys: list[str]) -> dict:
    return {key: payload[key] for key in keys if key in payload}


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


def _normalize_detail(tool: str, detail: str) -> tuple[str, Optional[dict]]:
    normalized = str(detail or DETAIL_SHORT).strip().lower()
    if normalized not in DETAIL_MODES:
        return "", _err(
            tool,
            "invalid_detail",
            "Invalid detail mode. Use 'short' or 'full'.",
            {"received": detail, "allowed": [DETAIL_SHORT, DETAIL_FULL]},
        )
    return normalized, None


def _normalize_dynamic_text(text: str) -> str:
    """Normalize dynamic IDs so token profiling stays stable across runs."""
    normalized = text
    normalized = re.sub(r"session-[0-9a-f]{6,}", "session-<id>", normalized)
    normalized = re.sub(r"verify-[0-9a-f]{6,}", "verify-<id>", normalized)
    normalized = re.sub(r"run-[0-9a-f]{6,}", "run-<id>", normalized)
    return normalized


def _reconcile_summary(report: Any) -> dict:
    if not isinstance(report, dict):
        return {}
    summary = {
        "human_summary": report.get("human_summary", ""),
        "severity_totals": report.get("severity_totals", {}),
        "conflict_counts": report.get("conflict_counts", {}),
        "warning_counts": report.get("warning_counts", {}),
        "gate_reasons": report.get("gate_reasons", []),
    }
    if "deferred_map_canonical_checks" in report:
        summary["deferred_map_canonical_checks"] = report.get("deferred_map_canonical_checks")
    return summary


def _compact_context_pack_payload(payload: dict) -> dict:
    pack_data = payload.get("context_pack", {})
    meta = pack_data.get("_meta", {}) if isinstance(pack_data, dict) else {}
    resolved_pack = str(meta.get("resolved_pack", payload.get("pack", "balanced")))
    requested_pack = str(meta.get("requested_pack", payload.get("pack", resolved_pack)))
    tokens = int(payload.get("tokens", meta.get("token_count", 0)) or 0)
    message = payload.get("message", f"Context pack ready ({resolved_pack}, {tokens} tokens).")
    compact = {
        "message": message,
        "pack": resolved_pack,
        "requested_pack": requested_pack,
        "tokens": tokens,
        "context_window_usage": meta.get("context_window_usage", {}),
        "included_sections": meta.get("included_sections", []),
        "omitted_sections": meta.get("omitted_sections", []),
        "omitted_context": meta.get("omitted_context", meta.get("compaction_notes", [])),
        "state_included": bool(meta.get("state_included", True)),
        "limits": meta.get("limits", {}),
    }
    if payload.get("session_id"):
        compact["session_id"] = payload.get("session_id")
        compact["context_pack_calls"] = payload.get("context_pack_calls", 0)
        compact["refresh_reason"] = payload.get("refresh_reason", "")
        compact["refresh_reason_category"] = payload.get("refresh_reason_category", "")
    return compact


def _compact_success(tool: str, payload: dict) -> dict:
    if not isinstance(payload, dict):
        return {}

    if tool == "haxaml_context_pack":
        return _compact_context_pack_payload(payload)

    if tool == "haxaml_context":
        return _pick_fields(payload, ["message", "tokens", "include_state", "deprecation"])

    if tool == "haxaml_guidance":
        compact = _pick_fields(
            payload,
            [
                "message",
                "execution_mode",
                "status",
                "task_type",
                "risk_level",
                "required_questions",
                "recommended_packs",
                "next_step",
            ],
        )
        if payload.get("execution_mode") == "governed":
            compact.update(
                _pick_fields(
                    payload,
                    [
                        "call_budget",
                        "visibility_calls_optional",
                        "anti_bloat_policy",
                    ],
                )
            )
        else:
            compact["policy"] = payload.get("policy", {})
        return compact

    if tool == "haxaml_prebuild":
        return _pick_fields(
            payload,
            [
                "message",
                "session_id",
                "readiness_status",
                "task_type",
                "guidance_type",
                "required_questions",
                "next_step",
                "policy",
            ],
        )

    if tool == "haxaml_about":
        workflow = payload.get("recommended_workflow", {}) if isinstance(payload.get("recommended_workflow"), dict) else {}
        budgets = payload.get("call_budgets", {}) if isinstance(payload.get("call_budgets"), dict) else {}
        budget_targets = {
            key: {
                "target_calls": value.get("target_calls"),
                "max_calls_without_visibility": value.get("max_calls_without_visibility"),
                "max_calls_with_visibility": value.get("max_calls_with_visibility"),
            }
            for key, value in budgets.items()
            if isinstance(value, dict)
        }
        return {
            "message": payload.get("message", ""),
            "about_version": payload.get("about_version", ""),
            "project_dir": payload.get("project_dir", ""),
            "onboarding_prompt": payload.get("agent_prompt", {}).get("role", ""),
            "modes": payload.get("modes", {}),
            "safety_rule": payload.get("safety_rule", ""),
            "anti_bloat_policy": payload.get("anti_bloat_policy", {}),
            "lean_workflow": workflow.get("lean_default", []),
            "visibility_calls_optional": workflow.get("visibility_calls_optional", []),
            "call_budget_targets": budget_targets,
        }

    if tool == "haxaml_session_start":
        return _pick_fields(
            payload,
            [
                "message",
                "session_id",
                "execution_mode",
                "status",
                "risk_level",
                "task_type",
                "required_reads",
                "required_questions",
                "recommended_context_packs",
            ],
        )

    if tool == "haxaml_session_plan":
        return _pick_fields(
            payload,
            [
                "message",
                "session_id",
                "execution_mode",
                "status",
                "risk_level",
                "plan",
                "verification_expectations",
                "visibility_policy",
                "retry_policy",
            ],
        )

    if tool == "haxaml_session_verify":
        return _pick_fields(
            payload,
            [
                "message",
                "verification_id",
                "session_id",
                "task",
                "verdict",
                "risky_paths",
                "unresolved_questions",
                "follow_ups",
            ],
        )

    if tool == "haxaml_session_record":
        compact = _pick_fields(
            payload,
            [
                "message",
                "session_id",
                "run_id",
                "verification_id",
                "verification_verdict",
                "gate_reasons",
                "last_pack_tokens",
                "last_context_window_usage",
                "auto_exported",
                "expect_sync_required",
            ],
        )
        compact["reconcile"] = _reconcile_summary(payload.get("reconcile"))
        return compact

    if tool == "haxaml_expect_sync":
        return _pick_fields(
            payload,
            [
                "message",
                "synced",
                "run",
                "applied_status",
                "expect_sync",
            ],
        )

    if tool == "haxaml_validate":
        compact = _pick_fields(payload, ["message", "valid"])
        compact["reconcile"] = _reconcile_summary(payload.get("reconcile"))
        return compact

    if tool == "haxaml_reconcile":
        compact = _pick_fields(payload, ["message"])
        compact.update(_reconcile_summary(payload))
        return compact

    if tool == "haxaml_health":
        report = payload.get("report", {}) if isinstance(payload.get("report"), dict) else {}
        compact = _pick_fields(payload, ["message"])
        compact["summary"] = {
            "project": report.get("project"),
            "ready": report.get("ready"),
            "facts_valid": report.get("facts_valid"),
            "acts_valid": report.get("acts_valid"),
            "facts_complete": report.get("facts_complete"),
            "context_tokens": report.get("context_tokens"),
        }
        return compact

    if tool == "haxaml_doctor":
        return _pick_fields(payload, ["message", "has_recommendations", "recommendations", "errors"])

    if tool == "haxaml_benchmark":
        return _pick_fields(
            payload,
            [
                "message",
                "mode",
                "profiles",
                "transport_overhead",
                "guardrails",
            ],
        )

    return payload


def _ok(
    tool: str,
    data: Optional[dict] = None,
    warnings: Optional[list[str]] = None,
    detail: str = DETAIL_SHORT,
) -> dict:
    payload = data or {}
    if detail == DETAIL_SHORT:
        payload = _compact_success(tool, payload)
    return {
        "ok": True,
        "tool": tool,
        "data": payload,
        "warnings": warnings or [],
        "error": None,
    }
