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


def metadata_line_comment(metadata: dict[str, object], *, prefix: str = "#") -> str:
    compact = json.dumps(metadata, sort_keys=True, separators=(",", ":"))
    return f"{prefix} HAXAML:FILE {compact}"


def metadata_json_document(metadata: dict[str, object], payload: dict[str, object]) -> str:
    document = {"_haxaml": metadata, **payload}
    return json.dumps(document, indent=2, sort_keys=True) + "\n"


def managed_block_start(metadata: dict[str, object]) -> str:
    compact = json.dumps(metadata, sort_keys=True, separators=(",", ":"))
    return f"<!-- HAXAML:MANAGED START {compact} -->"


MANAGED_BLOCK_END = "<!-- HAXAML:MANAGED END -->"
