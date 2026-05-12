"""Safe writes for setup plans."""

from __future__ import annotations

import re
from pathlib import Path

from haxaml.setup.markdown import MANAGED_BLOCK_END
from haxaml.setup.planner import PlannedFile, SetupPlan


_FILE_MARKER = "<!-- HAXAML:FILE "
_BLOCK_RE = re.compile(r"<!-- HAXAML:MANAGED START .*?<!-- HAXAML:MANAGED END -->\n?", re.DOTALL)


def has_managed_file_marker(text: str) -> bool:
    return text.lstrip().startswith(_FILE_MARKER)


def has_managed_block(text: str) -> bool:
    return bool(_BLOCK_RE.search(text))


def extract_managed_block(text: str) -> str | None:
    match = _BLOCK_RE.search(text)
    if match is None:
        return None
    return match.group(0)


def _upsert_pointer(existing: str, block: str) -> str:
    if _BLOCK_RE.search(existing):
        return _BLOCK_RE.sub(block.rstrip() + "\n", existing, count=1)
    base = existing.rstrip()
    if base:
        return f"{base}\n\n{block.rstrip()}\n"
    return block.rstrip() + "\n"


def _write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _apply_item(project_dir: Path, item: PlannedFile, force: bool) -> tuple[str, str]:
    path = Path(item.path) if item.scope == "user" else project_dir / item.path
    if item.management == "pointer":
        existing = path.read_text(encoding="utf-8") if path.exists() else ""
        if path.exists():
            updated = _upsert_pointer(existing, item.content)
            _write_file(path, updated)
            action = "updated"
        else:
            _write_file(path, item.content)
            action = "created"
        return action, item.path

    if path.exists():
        existing = path.read_text(encoding="utf-8", errors="ignore")
        if not force and not has_managed_file_marker(existing):
            return "skipped", item.path
        action = "updated"
    else:
        action = "created"
    _write_file(path, item.content)
    return action, item.path


def apply_setup_plan(plan: SetupPlan, *, force: bool = False) -> dict[str, object]:
    created: list[str] = []
    updated: list[str] = []
    skipped: list[str] = []
    for item in plan.planned_files:
        action, path = _apply_item(plan.project_dir, item, force)
        if action == "created":
            created.append(path)
        elif action == "updated":
            updated.append(path)
        else:
            skipped.append(path)

    return {
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "manual_actions": [item.to_dict() for item in plan.manual_actions],
    }
