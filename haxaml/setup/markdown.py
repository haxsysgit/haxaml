"""Small markdown helpers for setup output generation."""

from __future__ import annotations

import json


def section(title: str, body: str) -> str:
    return f"## {title}\n\n{body.strip()}"


def bullets(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


def numbered(items: list[str]) -> str:
    return "\n".join(f"{idx}. {item}" for idx, item in enumerate(items, start=1))


def code_block(language: str, body: str) -> str:
    return f"```{language}\n{body.rstrip()}\n```"


def metadata_comment(metadata: dict[str, object]) -> str:
    compact = json.dumps(metadata, sort_keys=True, separators=(",", ":"))
    return f"<!-- HAXAML:FILE {compact} -->"


def managed_block_start(metadata: dict[str, object]) -> str:
    compact = json.dumps(metadata, sort_keys=True, separators=(",", ":"))
    return f"<!-- HAXAML:MANAGED START {compact} -->"


MANAGED_BLOCK_END = "<!-- HAXAML:MANAGED END -->"
