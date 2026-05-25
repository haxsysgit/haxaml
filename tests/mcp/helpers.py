"""Shared test helpers for MCP tests."""


def msg(result):
    if isinstance(result, dict):
        return result.get("data", {}).get("message", "")
    return str(result)


def frame(file: str, role: str) -> dict:
    return {
        "file": file,
        "schema_version": "0.8.0",
        "role": role,
        "status": "draft",
        "last_reviewed": None,
        "updated_by": None,
        "update_reason": None,
    }
