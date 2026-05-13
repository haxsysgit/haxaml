"""Shared YAML loading helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def load_yaml(path: str | Path) -> dict[str, Any]:
    """Load a YAML file and return a mapping-like document."""
    with Path(path).open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def load_yaml_if_exists(path: str | Path) -> dict[str, Any] | None:
    """Load a YAML file if it exists, otherwise return None."""
    candidate = Path(path)
    if not candidate.exists():
        return None
    return load_yaml(candidate)


def dump_yaml(data: Any, *, sort_keys: bool = False) -> str:
    """Serialize data to YAML with stable default settings."""
    return yaml.safe_dump(data, sort_keys=sort_keys, allow_unicode=False)
