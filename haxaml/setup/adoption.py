"""Adoption inventory and state for setup."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from haxaml.adoption import analyze_adoption_instructions, scan_native_sources
from haxaml.setup.registry import TargetSpec, list_targets
from haxaml.versioning import get_version


ADOPTION_STATE_PATH = ".haxaml/adoption/adoption.yaml"
ADOPTION_REPORT_PATH = ".haxaml/adoption/ADOPTION.md"


@dataclass(frozen=True)
class AdoptionInventory:
    """Detected native setup surfaces and adoption analysis."""

    project_dir: Path
    detected_targets: tuple[str, ...]
    native_files: tuple[dict[str, str], ...]
    analysis: dict[str, object]

    def to_state(
        self,
        *,
        selected_targets: list[str],
        sidecars: list[str],
        skipped_files: list[str],
    ) -> dict[str, object]:
        return {
            "version": get_version(),
            "managed_by": "haxaml-setup",
            "mode": "adopted",
            "selected_targets": selected_targets,
            "detected_targets": list(self.detected_targets),
            "native_files": list(self.native_files),
            "analysis": self.analysis,
            "sidecars": sidecars,
            "skipped_files": skipped_files,
        }


def _find_patterns(project_dir: Path, patterns: tuple[str, ...]) -> list[str]:
    found: list[str] = []
    for pattern in patterns:
        if any(marker in pattern for marker in "*?[]"):
            for path in project_dir.glob(pattern):
                if path.is_file():
                    found.append(path.relative_to(project_dir).as_posix())
            continue
        candidate = project_dir / pattern
        if candidate.is_file():
            found.append(candidate.relative_to(project_dir).as_posix())
    return found


def detect_targets(project_dir: str | Path) -> tuple[str, ...]:
    project = Path(project_dir).resolve()
    detected: list[str] = []
    for target in list_targets():
        if target.target_id == "generic":
            continue
        if _find_patterns(project, target.detect_patterns):
            detected.append(target.target_id)
    return tuple(sorted(set(detected)))


def detect_target_files(project_dir: str | Path, target: TargetSpec) -> tuple[str, ...]:
    project = Path(project_dir).resolve()
    return tuple(sorted(set(_find_patterns(project, target.detect_patterns))))


def build_adoption_inventory(project_dir: str | Path) -> AdoptionInventory:
    project = Path(project_dir).resolve()
    legacy_plan = scan_native_sources(project)
    analysis = analyze_adoption_instructions(legacy_plan)
    detected_targets = detect_targets(project)

    native_files = [
        {"kind": found.kind, "label": found.label, "path": found.path}
        for found in legacy_plan.native_files
    ]
    known_paths = {item["path"] for item in native_files}
    for target in list_targets():
        if target.target_id in {"generic", *detected_targets}:
            for path in detect_target_files(project, target):
                if path not in known_paths:
                    native_files.append({"kind": target.target_id, "label": target.display_name, "path": path})
                    known_paths.add(path)

    native_files.sort(key=lambda item: item["path"])
    return AdoptionInventory(
        project_dir=project,
        detected_targets=detected_targets,
        native_files=tuple(native_files),
        analysis=analysis,
    )


def dump_adoption_state(state: dict[str, object]) -> str:
    return yaml.safe_dump(state, sort_keys=False, allow_unicode=False)
