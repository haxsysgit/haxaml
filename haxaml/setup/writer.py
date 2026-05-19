"""Safe writes for setup plans."""

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

from haxaml.setup.config_merge import plan_managed_config_write
from haxaml.setup.markdown import MANAGED_BLOCK_END
from haxaml.setup.planner import PlannedFile, SetupPlan


_HTML_FILE_MARKER = "<!-- HAXAML:FILE "
_LINE_FILE_MARKERS = ("# HAXAML:FILE ", "// HAXAML:FILE ")
_BLOCK_RE = re.compile(r"<!-- HAXAML:MANAGED START .*?<!-- HAXAML:MANAGED END -->\n?", re.DOTALL)
_SETUP_METADATA_PREFIXES = (
    ".haxaml/setup/",
    ".haxaml/adoption/",
)


def has_managed_file_marker(text: str) -> bool:
    stripped = text.lstrip()
    if stripped.startswith(_HTML_FILE_MARKER):
        return True
    if stripped.startswith(_LINE_FILE_MARKERS):
        return True
    if not stripped.startswith("{"):
        return False
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError:
        return False
    metadata = payload.get("_haxaml")
    return isinstance(metadata, dict) and metadata.get("generator") == "haxaml-setup"


def _has_managed_skill_frontmatter(text: str) -> bool:
    stripped = text.lstrip()
    if not stripped.startswith("---"):
        return False
    lines = stripped.splitlines()
    if not lines or lines[0].strip() != "---":
        return False
    try:
        end_idx = next(index for index, line in enumerate(lines[1:], start=1) if line.strip() == "---")
    except StopIteration:
        return False
    frontmatter_text = "\n".join(lines[1:end_idx])
    try:
        payload = yaml.safe_load(frontmatter_text) or {}
    except yaml.YAMLError:
        return False
    metadata = payload.get("metadata")
    return isinstance(metadata, dict) and metadata.get("generator") == "haxaml-setup"


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


def _is_setup_metadata_file(item: PlannedFile) -> bool:
    return any(item.path.startswith(prefix) for prefix in _SETUP_METADATA_PREFIXES)


def _apply_item(project_dir: Path, item: PlannedFile, force: bool) -> tuple[str, str]:
    path = Path(item.path) if item.scope == "user" else project_dir / item.path
    if item.management == "merge":
        existing = path.read_text(encoding="utf-8", errors="ignore") if path.exists() else None
        merge_plan = plan_managed_config_write(
            existing_text=existing,
            config_format=item.format,
            desired_content=item.content,
        )
        if merge_plan.action == "skip":
            return "skipped", item.path
        if merge_plan.action == "manual" or merge_plan.content is None:
            return "skipped", item.path
        _write_file(path, merge_plan.content)
        if merge_plan.action == "create":
            return "created", item.path
        return "merged", item.path

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
        if (
            not force
            and not _is_setup_metadata_file(item)
            and not (has_managed_file_marker(existing) or _has_managed_skill_frontmatter(existing))
        ):
            return "skipped", item.path
        action = "updated"
    else:
        action = "created"
    _write_file(path, item.content)
    return action, item.path


def apply_setup_plan(plan: SetupPlan, *, force: bool = False) -> dict[str, object]:
    created: list[str] = []
    updated: list[str] = []
    merged: list[str] = []
    skipped: list[str] = []
    items: list[dict[str, object]] = []
    for item in plan.planned_files:
        action, path = _apply_item(plan.project_dir, item, force)
        item_result = {
            "path": path,
            "status": action,
            "target": item.target,
            "kind": item.kind,
            "scope": item.scope,
            "action_reason": item.action_reason,
            "preview": item.preview,
            "merge_status": item.merge_status,
            "candidate_targets": item.candidate_targets,
            "managed_key_path": item.managed_key_path,
        }
        if action == "created":
            created.append(path)
            items.append(item_result)
        elif action == "updated":
            updated.append(path)
            items.append(item_result)
        elif action == "merged":
            merged.append(path)
            items.append(item_result)
        else:
            skipped.append(path)
            items.append(item_result)

    return {
        "created": created,
        "updated": updated,
        "merged": merged,
        "skipped": skipped,
        "items": items,
        "manual_actions": [item.to_dict() for item in plan.manual_actions],
    }
