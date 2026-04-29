"""MCP export and bootstrap helper functions."""

import difflib
import json
from pathlib import Path
from typing import Optional

from haxaml.export_engine import AGENT_CONFIGS


def _resolve_export_target(
    project_dir: str,
    agent: str,
    target: Optional[str] = None,
    override_native: bool = False,
) -> Path:
    config = AGENT_CONFIGS[agent]
    if target:
        return Path(target).expanduser().resolve()
    filename = config.get("native_filename") if override_native else config["filename"]
    return (Path(project_dir).resolve() / filename).resolve()


def _build_unified_diff(before: str, after: str, target_path: Path) -> str:
    before_lines = before.splitlines(keepends=True)
    after_lines = after.splitlines(keepends=True)
    diff_lines = difflib.unified_diff(
        before_lines,
        after_lines,
        fromfile=str(target_path),
        tofile=str(target_path),
        lineterm="\n",
    )
    return "".join(diff_lines)


def _diff_summary(diff_text: str) -> dict:
    added = 0
    removed = 0
    for line in diff_text.splitlines():
        if line.startswith(("---", "+++", "@@")):
            continue
        if line.startswith("+"):
            added += 1
        elif line.startswith("-"):
            removed += 1
    return {
        "changed": bool(diff_text),
        "added_lines": added,
        "removed_lines": removed,
    }


def _mcp_server_config(project_dir: str, uvx: bool = True) -> dict:
    if uvx:
        return {
            "type": "stdio",
            "command": "uvx",
            "args": ["haxaml-mcp"],
            "env": {"HAXAML_PROJECT_DIR": str(Path(project_dir).resolve())},
        }
    return {
        "type": "stdio",
        "command": "haxaml-mcp",
        "args": [],
        "env": {"HAXAML_PROJECT_DIR": str(Path(project_dir).resolve())},
    }


def _editor_targets(project_dir: Path) -> dict[str, Optional[Path]]:
    return {
        "generic": (project_dir / ".mcp.json"),
        "claude_code": (project_dir / ".mcp.json"),
        "cursor": (project_dir / ".cursor" / "mcp.json"),
        "copilot": None,
    }


def _bootstrap_snippet(project_dir: str, uvx: bool = True) -> dict:
    base = _mcp_server_config(project_dir, uvx=uvx)
    return {"mcpServers": {"haxaml": base}}


def _write_bootstrap_config(
    path: Path,
    server_block: dict,
    overwrite: bool = False,
) -> tuple[str, str]:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = {}
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return "error", f"Existing config is invalid JSON: {path}"
    if not isinstance(existing, dict):
        return "error", f"Existing config must be a JSON object: {path}"

    mcp_servers = existing.setdefault("mcpServers", {})
    if not isinstance(mcp_servers, dict):
        return "error", f"`mcpServers` must be an object in {path}"

    if "haxaml" in mcp_servers and not overwrite:
        return "skipped_exists", f"Existing haxaml server preserved in {path}"

    mcp_servers["haxaml"] = server_block
    path.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")
    return "written", f"Wrote MCP config at {path}"
