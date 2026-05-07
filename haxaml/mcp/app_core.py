"""Core MCP app state and constants."""

import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP


mcp_app = FastMCP(
    "haxaml",
    instructions=(
        "Deterministic FRAME governance for AI-assisted development. "
        "Plan first, then build. Use FRAME as your project journal."
    ),
)

DETAIL_SHORT = "short"
DETAIL_FULL = "full"
DETAIL_MODES = {DETAIL_SHORT, DETAIL_FULL}
ABOUT_PROMPT_VERSION = "0.6.7b0"

_ABOUT_ACK_CACHE: set[str] = set()
_RETRY_GUARD_CACHE: dict[str, int] = {}

UTILITY_TASK_HINTS = [
    "todo list",
    "to-do list",
    "sort files",
    "sort the files",
    "organize files",
    "organize folder",
    "clean folder",
    "rename files",
    "quick question",
    "outside project",
    "outside the project",
    "unrelated task",
    "side task",
    "practice app",
    "sample app",
    "demo app",
]


def _project() -> Path:
    """Resolve the project directory from HAXAML_PROJECT_DIR env or CWD."""
    return Path(os.environ.get("HAXAML_PROJECT_DIR", ".")).resolve()
