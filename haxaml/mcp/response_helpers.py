"""MCP response formatting and compaction helpers."""

import re
from typing import Any, Optional

from haxaml.mcp.app_core import DETAIL_FULL, DETAIL_MODES, DETAIL_SHORT


def _pick_fields(payload: dict, keys: list[str]) -> dict:
    return {key: payload[key] for key in keys if key in payload}


def _compact_lifecycle(payload: dict) -> dict:
    lifecycle = payload.get("lifecycle", {}) if isinstance(payload.get("lifecycle"), dict) else {}
    return _pick_fields(
        lifecycle,
        ["phase", "depends_on", "preferred_next", "allowed_next"],
    )


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
    # Short-mode context responses surface the execution facts first and leave the
    # heavy context body behind. That keeps "context_pack" useful without duplicating the pack text.
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
    compact["lifecycle"] = _compact_lifecycle(payload)
    return compact


def _normalize_full_success(payload: dict) -> dict:
    normalized = dict(payload)
    if isinstance(normalized.get("lifecycle"), dict):
        normalized["lifecycle"] = _compact_lifecycle(normalized)
    return normalized


def _compact_success(tool: str, payload: dict) -> dict:
    if not isinstance(payload, dict):
        return {}

    # Compactors are per-tool because each tool has a different notion of "high-signal fields".
    if tool == "haxaml_context_pack":
        return _compact_context_pack_payload(payload)

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
                        "anti_bloat_policy",
                    ],
                )
            )
        else:
            compact["policy"] = payload.get("policy", {})
        compact["lifecycle"] = _compact_lifecycle(payload)
        return compact

    if tool == "haxaml_prebuild":
        compact = _pick_fields(
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
        if "progress_summary" in payload:
            compact["progress_summary"] = _pick_fields(
                payload["progress_summary"],
                ["status", "reason"],
            )
        compact["lifecycle"] = _compact_lifecycle(payload)
        return compact

    if tool == "haxaml_about":
        workflow = payload.get("recommended_workflow", {}) if isinstance(payload.get("recommended_workflow"), dict) else {}
        lifecycle = payload.get("lifecycle", {}) if isinstance(payload.get("lifecycle"), dict) else {}
        modes = payload.get("modes", {}) if isinstance(payload.get("modes"), dict) else {}
        compact = {
            "message": (
                "Haxaml is the governance layer. Use the lean flow: "
                "about -> guidance -> prebuild -> context_pack -> verify -> record -> expect_sync. "
                "Use utility mode for unrelated work. Next: haxaml_guidance."
            ),
            "about_version": payload.get("about_version", ""),
            "onboarding_prompt": payload.get("agent_prompt", {}).get("role", ""),
            "governed_mode": modes.get("governed", ""),
            "utility_mode": modes.get("utility", ""),
            "resume_rule": modes.get("resume_rule", ""),
            "lean_workflow": workflow.get("lean_default", []),
            "visibility_calls_optional": workflow.get("visibility_calls_optional", []),
            "next_step": "haxaml_guidance",
            "lifecycle": {
                "tool": lifecycle.get("tool", "haxaml_about"),
                "phase": lifecycle.get("phase", "about"),
                "depends_on": lifecycle.get("depends_on", []),
                "preferred_next": lifecycle.get("preferred_next", "haxaml_guidance"),
            },
        }
        if "allowed_next" in lifecycle:
            compact["lifecycle"]["allowed_next"] = lifecycle["allowed_next"]
        return compact
    if tool == "haxaml_session_verify":
        compact = _pick_fields(
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
        compact["lifecycle"] = _compact_lifecycle(payload)
        return compact

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
        compact["lifecycle"] = _compact_lifecycle(payload)
        return compact

    if tool == "haxaml_expect_sync":
        compact = _pick_fields(
            payload,
            [
                "message",
                "synced",
                "run",
                "applied_status",
                "expect_sync",
            ],
        )
        compact["lifecycle"] = _compact_lifecycle(payload)
        return compact

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
        if isinstance(report.get("progress_summary"), dict):
            compact["progress_summary"] = _pick_fields(
                report["progress_summary"],
                ["status", "reason"],
            )
        return compact

    if tool == "haxaml_doctor":
        compact = _pick_fields(payload, ["message", "has_recommendations", "recommendations", "errors"])
        if "progress_summary" in payload:
            compact["progress_summary"] = _pick_fields(
                payload["progress_summary"],
                ["status", "reason"],
            )
        return compact

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
    # Tools build one rich payload. The response helper decides whether callers get the
    # full version or the compact high-signal summary.
    if detail == DETAIL_SHORT:
        payload = _compact_success(tool, payload)
    else:
        payload = _normalize_full_success(payload)
    return {
        "ok": True,
        "tool": tool,
        "data": payload,
        "warnings": warnings or [],
        "error": None,
    }
