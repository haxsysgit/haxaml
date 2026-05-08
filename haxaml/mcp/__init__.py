"""Modular MCP package with a lazy MCP app export."""

from __future__ import annotations

from typing import Any

__all__ = ["mcp_app"]


def __getattr__(name: str) -> Any:
    if name == "mcp_app":
        from haxaml.mcp.base import mcp_app

        return mcp_app
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
