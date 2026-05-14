"""Doctor output for setup-managed files."""

from __future__ import annotations

import hashlib
from pathlib import Path

from haxaml.setup.planner import MANIFEST_PATH
from haxaml.setup.workflow import workflow_file_audit_metadata, workflow_manual_action_audit_metadata
from haxaml.setup.writer import extract_managed_block
from haxaml.yaml_utils import load_yaml


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _load_manifest(project_dir: Path) -> dict[str, object] | None:
    path = project_dir / MANIFEST_PATH
    if not path.exists():
        return None
    return load_yaml(path)


def _item_category(kind: str) -> str:
    return "workflow" if kind == "workflow" else "setup"


def _doctor_file_record(*, path: str, target: str, kind: str, status: str, reason: str | None = None) -> dict[str, str]:
    record: dict[str, str] = {
        "path": path,
        "target": target,
        "kind": kind,
        "category": _item_category(kind),
    }
    if reason:
        record["reason"] = reason
    if kind == "workflow":
        metadata = workflow_file_audit_metadata(target, path, status=status)
        if metadata:
            record.update(metadata)
    return record


def _doctor_manual_action_record(item: dict[str, object]) -> dict[str, str | None]:
    kind = str(item.get("kind", ""))
    record: dict[str, str | None] = {
        "target": str(item.get("target", "")),
        "kind": kind,
        "scope": str(item.get("scope", "")),
        "path": item.get("path") if item.get("path") is None else str(item.get("path")),
        "docs_url": str(item.get("docs_url", "")),
        "reason": str(item.get("reason", "")),
        "category": _item_category(kind),
    }
    if kind == "workflow":
        metadata = workflow_manual_action_audit_metadata(record["target"] or "", record["reason"] or "")
        if metadata:
            record.update(metadata)
    return record


def run_setup_doctor(project_dir: str | Path) -> dict[str, object]:
    root = Path(project_dir).resolve()
    manifest = _load_manifest(root)
    if not manifest:
        return {
            "installed": [],
            "missing": [],
            "drifted": [],
            "manual_actions": [],
            "message": "No setup manifest found. Run `haxaml setup` first.",
        }

    installed: list[dict[str, str]] = []
    missing: list[dict[str, str]] = []
    drifted: list[dict[str, str]] = []

    for item in manifest.get("managed_files", []):
        if not isinstance(item, dict):
            continue
        path = str(item.get("path", ""))
        if not path:
            continue
        resolved = Path(path) if str(item.get("scope")) == "user" else root / path
        if not resolved.exists():
            missing.append(
                _doctor_file_record(
                    path=path,
                    target=str(item.get("target", "")),
                    kind=str(item.get("kind", "")),
                    status="missing",
                    reason="missing",
                )
            )
            continue

        content = resolved.read_text(encoding="utf-8", errors="ignore")
        if str(item.get("management")) == "pointer":
            block = extract_managed_block(content)
            if block is None:
                drifted.append(
                    _doctor_file_record(
                        path=path,
                        target=str(item.get("target", "")),
                        kind=str(item.get("kind", "")),
                        status="drifted",
                        reason="managed block missing",
                    )
                )
                continue
            actual_hash = _hash(block)
        else:
            actual_hash = _hash(content)

        expected_hash = str(item.get("recipe_hash", ""))
        if expected_hash and actual_hash != expected_hash:
            drifted.append(
                _doctor_file_record(
                    path=path,
                    target=str(item.get("target", "")),
                    kind=str(item.get("kind", "")),
                    status="drifted",
                    reason="content drift",
                )
            )
            continue

        installed.append(
            _doctor_file_record(
                path=path,
                target=str(item.get("target", "")),
                kind=str(item.get("kind", "")),
                status="installed",
            )
        )

    raw_manual_actions = manifest.get("manual_actions", [])
    manual_actions = []
    if isinstance(raw_manual_actions, list):
        manual_actions = [_doctor_manual_action_record(item) for item in raw_manual_actions if isinstance(item, dict)]
    return {
        "installed": installed,
        "missing": missing,
        "drifted": drifted,
        "manual_actions": manual_actions,
        "message": (
            f"Installed: {len(installed)} | Missing: {len(missing)} | "
            f"Drifted: {len(drifted)} | Manual: {len(manual_actions)}"
        ),
    }
