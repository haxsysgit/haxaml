"""Shared test helpers for MCP tests."""


def msg(result):
    if isinstance(result, dict):
        return result.get("data", {}).get("message", "")
    return str(result)
