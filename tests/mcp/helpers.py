"""Shared test helpers for MCP tests."""

from pathlib import Path

import yaml


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


def runtime_state_path(project_dir: str | Path) -> Path:
    return Path(project_dir) / ".haxaml" / "runtime" / "acts-state.yaml"


def read_runtime_state(project_dir: str | Path) -> dict:
    path = runtime_state_path(project_dir)
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text()) or {}


def write_runtime_state(project_dir: str | Path, state: dict) -> None:
    path = runtime_state_path(project_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.dump(state, default_flow_style=False, sort_keys=False))
