"""Shared lifecycle state helpers with no MCP runtime dependency."""

from __future__ import annotations

from typing import Any


def expect_sync_state(state: dict[str, Any]) -> dict[str, Any]:
    """Return normalized expect-sync lifecycle state from acts payload."""
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
