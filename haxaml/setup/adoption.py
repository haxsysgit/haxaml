"""Canonical adoption inventory and analysis for setup."""

from __future__ import annotations

from dataclasses import dataclass
import re
from pathlib import Path
from typing import Iterable

from haxaml.paths import resolve_frame_file
from haxaml.setup.registry import TargetSpec, list_targets
from haxaml.utils import normalized_text
from haxaml.versioning import get_version
from haxaml.yaml_utils import dump_yaml


ADOPTION_STATE_PATH = ".haxaml/adoption/adoption.yaml"
ADOPTION_REPORT_PATH = ".haxaml/adoption/ADOPTION.md"

CONTEXT_FILE_SPECS = (
    ("README.md",),
    ("package.json",),
    ("setup.py",),
    ("pyproject.toml",),
    ("requirements.txt",),
    ("Cargo.toml",),
    ("go.mod",),
)
_DIRECTIVE_MARKERS = ("must", "should", "do not", "don't", "never", "always", "only", "must not")
_NEGATION_MARKERS = ("do not", "don't", "never", "must not", "cannot", "can't", "no ")
_README_AGENT_HEADING_MARKERS = ("agent", "ai", "instruction", "copilot", "claude", "codex", "cursor", "windsurf", "gemini")
_RECOMMENDED_NEXT_ACTION = "decide_authoritative_source_then_update_frame"


@dataclass(frozen=True)
class FoundFile:
    """A discovered project file relevant to setup adoption."""

    kind: str
    label: str
    path: str


@dataclass(frozen=True)
class AdoptionPlan:
    """Result of scanning a project for existing setup-relevant files."""

    project_dir: Path
    native_files: tuple[FoundFile, ...]
    context_files: tuple[FoundFile, ...]
    existing_frame_files: tuple[str, ...]


@dataclass(frozen=True)
class InstructionDirective:
    normalized: str
    topic: str
    polarity: str
    source: FoundFile
    scope: str


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


def _find_patterns(project_dir: Path, patterns: Iterable[str]) -> list[Path]:
    found: list[Path] = []
    for pattern in patterns:
        if any(char in pattern for char in "*?[]"):
            found.extend(path for path in project_dir.glob(pattern) if path.is_file())
            continue
        path = project_dir / pattern
        if path.is_file():
            found.append(path)
    return found


def _relative(project_dir: Path, path: Path) -> str:
    return path.relative_to(project_dir).as_posix()


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return ""


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "section"


def _is_agent_heading(heading: str) -> bool:
    lowered = heading.lower()
    return any(marker in lowered for marker in _README_AGENT_HEADING_MARKERS)


def _readme_agent_sections(project_dir: Path) -> list[tuple[str, str]]:
    readme = project_dir / "README.md"
    if not readme.is_file():
        return []
    content = _read_text(readme)
    if not content:
        return []

    sections: list[tuple[str, str]] = []
    current_heading = ""
    current_lines: list[str] = []

    def _flush() -> None:
        nonlocal current_lines
        heading = current_heading.strip()
        if heading and _is_agent_heading(heading):
            scope = f"README.md#{_slugify(heading)}"
            sections.append((scope, "\n".join(current_lines).strip()))
        current_lines = []

    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            _flush()
            current_heading = stripped.lstrip("#").strip()
            continue
        current_lines.append(line)
    _flush()
    return sections


def _normalize_rule(text: str) -> str:
    norm = text.lower().replace("`", "")
    norm = re.sub(r"\s+", " ", norm).strip()
    return norm.strip(" .;,:")


def _is_negative(text: str) -> bool:
    return any(marker in text for marker in _NEGATION_MARKERS)


def _topic_from_rule(rule: str) -> str:
    topic = re.sub(r"\b(do not|don't|never|must not|cannot|can't|must|should|always|only)\b", "", rule)
    topic = re.sub(r"\s+", " ", topic).strip(" .;,:")
    return topic or rule


def _extract_directives(content: str) -> list[dict[str, str]]:
    directives: list[dict[str, str]] = []
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        cleaned = re.sub(r"^([-*+]\s+|\d+\.\s+|\[[ xX]\]\s+)", "", stripped).strip()
        lowered = cleaned.lower()
        if not any(marker in lowered for marker in _DIRECTIVE_MARKERS):
            continue
        normalized = _normalize_rule(cleaned)
        if len(normalized) < 8:
            continue
        directives.append(
            {
                "normalized": normalized,
                "topic": _normalize_rule(_topic_from_rule(normalized)),
                "polarity": "negative" if _is_negative(normalized) else "positive",
            }
        )
    return directives


def _collect_directives(plan: AdoptionPlan) -> list[InstructionDirective]:
    directives: list[InstructionDirective] = []
    project_dir = plan.project_dir
    for found in plan.native_files:
        content = _read_text(project_dir / found.path)
        if not content:
            continue
        for directive in _extract_directives(content):
            directives.append(
                InstructionDirective(
                    normalized=directive["normalized"],
                    topic=directive["topic"],
                    polarity=directive["polarity"],
                    source=found,
                    scope="file",
                )
            )

    for scope, content in _readme_agent_sections(project_dir):
        source = FoundFile("context", "Repository context", "README.md")
        for directive in _extract_directives(content):
            directives.append(
                InstructionDirective(
                    normalized=directive["normalized"],
                    topic=directive["topic"],
                    polarity=directive["polarity"],
                    source=source,
                    scope=scope,
                )
            )
    return directives


def _source_key(source: FoundFile, scope: str) -> tuple[str, str, str]:
    return source.kind, source.path, scope


def _sorted_source_refs(items: list[InstructionDirective]) -> list[dict[str, str]]:
    refs: dict[tuple[str, str, str], dict[str, str]] = {}
    for item in items:
        key = _source_key(item.source, item.scope)
        refs[key] = {
            "kind": item.source.kind,
            "label": item.source.label,
            "path": item.source.path,
            "scope": item.scope,
        }
    return [refs[key] for key in sorted(refs)]


def analyze_adoption_instructions(plan: AdoptionPlan) -> dict[str, object]:
    """Return deterministic metadata-only instruction analysis for adoption."""
    directives = _collect_directives(plan)
    groups: dict[str, list[InstructionDirective]] = {}
    for item in directives:
        groups.setdefault(item.normalized, []).append(item)

    duplicates: list[dict[str, object]] = []
    for counter, normalized in enumerate(sorted(groups), start=1):
        items = groups[normalized]
        if len({_source_key(d.source, d.scope) for d in items}) < 2:
            continue
        duplicates.append(
            {
                "id": f"adopt-duplicate-{counter:03d}",
                "rule_summary": normalized,
                "sources": _sorted_source_refs(items),
            }
        )

    topic_groups: dict[str, list[InstructionDirective]] = {}
    for item in directives:
        if item.topic:
            topic_groups.setdefault(item.topic, []).append(item)

    conflicts: list[dict[str, object]] = []
    conflict_counter = 0
    for topic in sorted(topic_groups):
        items = topic_groups[topic]
        if len({item.polarity for item in items}) < 2:
            continue
        if len({_source_key(d.source, d.scope) for d in items}) < 2:
            continue
        conflict_counter += 1
        conflicts.append(
            {
                "id": f"adopt-conflict-{conflict_counter:03d}",
                "category": "precedence_conflict",
                "severity": "warning",
                "rule_summary": topic,
                "sources": _sorted_source_refs(items),
                "requires_user_choice": True,
                "why_it_matters": "Conflicting instruction sources can cause inconsistent agent behavior unless one source is chosen as authoritative.",
                "recommended_next_action": _RECOMMENDED_NEXT_ACTION,
            }
        )

    precedence_candidates: list[dict[str, str]] = []
    seen = set()
    for conflict in conflicts:
        for source in conflict["sources"]:
            key = (source["kind"], source["path"], source["scope"])
            if key in seen:
                continue
            seen.add(key)
            precedence_candidates.append(source)

    readme_sections_scanned = len(_readme_agent_sections(plan.project_dir))
    sources_scanned = len(plan.native_files) + readme_sections_scanned
    return {
        "conflicts": conflicts,
        "duplicates": duplicates,
        "precedence_decision_required": bool(conflicts),
        "precedence_candidates": precedence_candidates,
        "counts": {
            "conflicts": len(conflicts),
            "duplicates": len(duplicates),
            "sources_scanned": sources_scanned,
            "readme_sections_scanned": readme_sections_scanned,
        },
    }


def scan_native_sources(project_dir: str | Path) -> AdoptionPlan:
    """Scan a project for native setup surfaces and lightweight repo context."""
    project = Path(project_dir).resolve()
    native: list[FoundFile] = []
    context: list[FoundFile] = []

    for target in list_targets():
        if target.target_id == "generic":
            continue
        for path in _find_patterns(project, target.detect_patterns):
            native.append(FoundFile(target.target_id, target.display_name, _relative(project, path)))

    for patterns in CONTEXT_FILE_SPECS:
        for path in _find_patterns(project, patterns):
            context.append(FoundFile("context", "Repository context", _relative(project, path)))

    existing_frame_files = tuple(
        _relative(project, path)
        for name in ("facts.yaml", "rules.yaml", "acts.yaml", "expect.yaml", "map.yaml")
        for path in [resolve_frame_file(project, name)]
        if path
    )

    return AdoptionPlan(
        project_dir=project,
        native_files=tuple(sorted(native, key=lambda item: item.path)),
        context_files=tuple(sorted(context, key=lambda item: item.path)),
        existing_frame_files=existing_frame_files,
    )


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
    return tuple(sorted({_relative(project, path) for path in _find_patterns(project, target.detect_patterns)}))


def build_adoption_inventory(project_dir: str | Path) -> AdoptionInventory:
    project = Path(project_dir).resolve()
    plan = scan_native_sources(project)
    analysis = analyze_adoption_instructions(plan)
    detected_targets = detect_targets(project)

    native_files = [
        {"kind": found.kind, "label": found.label, "path": found.path}
        for found in plan.native_files
    ]
    known_paths = {item["path"] for item in native_files}
    for target in list_targets():
        if target.target_id in {"generic", *detected_targets}:
            for path in detect_target_files(project, target):
                if path in known_paths:
                    continue
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
    """Serialize setup adoption state."""
    return dump_yaml(state, sort_keys=False)
