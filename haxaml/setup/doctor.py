"""Doctor output for setup-managed files."""

from __future__ import annotations

import hashlib
from pathlib import Path

import yaml

from haxaml.setup.planner import MANIFEST_PATH
from haxaml.setup.writer import extract_managed_block


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _load_manifest(project_dir: Path) -> dict[str, object] | None:
    path = project_dir / MANIFEST_PATH
    if not path.exists():
        return None
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


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
                {
                    "path": path,
                    "target": str(item.get("target", "")),
                    "kind": str(item.get("kind", "")),
                    "reason": "missing",
                }
            )
            continue

        content = resolved.read_text(encoding="utf-8", errors="ignore")
        if str(item.get("management")) == "pointer":
            block = extract_managed_block(content)
            if block is None:
                drifted.append(
                    {
                        "path": path,
                        "target": str(item.get("target", "")),
                        "kind": str(item.get("kind", "")),
                        "reason": "managed block missing",
                    }
                )
                continue
            actual_hash = _hash(block)
        else:
            actual_hash = _hash(content)

        expected_hash = str(item.get("recipe_hash", ""))
        if expected_hash and actual_hash != expected_hash:
            drifted.append(
                {
                    "path": path,
                    "target": str(item.get("target", "")),
                    "kind": str(item.get("kind", "")),
                    "reason": "content drift",
                }
            )
            continue

        installed.append(
            {
                "path": path,
                "target": str(item.get("target", "")),
                "kind": str(item.get("kind", "")),
            }
        )

    manual_actions = manifest.get("manual_actions", [])
    return {
        "installed": installed,
        "missing": missing,
        "drifted": drifted,
        "manual_actions": manual_actions if isinstance(manual_actions, list) else [],
        "message": (
            f"Installed: {len(installed)} | Missing: {len(missing)} | "
            f"Drifted: {len(drifted)} | Manual: {len(manual_actions) if isinstance(manual_actions, list) else 0}"
        ),
    }
