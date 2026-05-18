"""Shared in-process snapshot cache for FRAME files, archive metadata, and context packs."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from threading import RLock
from typing import Any

import hashlib
import yaml

from haxaml.paths import acts_history_path, resolve_frame_file
from haxaml.yaml_utils import load_yaml


FRAME_FILES = {
    "facts": "facts.yaml",
    "rules": "rules.yaml",
    "acts": "acts.yaml",
    "expect": "expect.yaml",
    "map": "map.yaml",
}
ARCHIVE_KIND_KEYS = {
    "run": "runs",
    "session": "sessions",
    "verification": "verifications",
    "completed_task": "completed_tasks",
    "decision": "decisions",
}


def _canonical_project_dir(project_dir: str | Path) -> str:
    return str(Path(project_dir).resolve())


def _stat_signature(path: Path | None) -> tuple[Any, ...]:
    if path is None or not path.exists():
        return ("missing",)
    stat = path.stat()
    return (str(path.resolve()), stat.st_size, stat.st_mtime_ns)


def _stable_dump(value: Any) -> str:
    return yaml.dump(value, default_flow_style=False, sort_keys=True)


def stable_fingerprint(value: Any) -> str:
    return hashlib.sha1(_stable_dump(value).encode("utf-8")).hexdigest()


def _normalize_mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _nested_value(data: Any, path: list[str]) -> Any:
    current = data
    for part in path:
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def _top_level_section_fingerprints(data: Any) -> dict[str, str]:
    if not isinstance(data, dict):
        return {}
    return {str(key): stable_fingerprint(value) for key, value in data.items()}


def _read_yaml_file(path: Path) -> tuple[Any, str]:
    try:
        return load_yaml(path), ""
    except Exception as exc:  # pragma: no cover - defensive I/O
        return None, str(exc)


def _read_archive_header(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]], str]:
    try:
        lines: list[str] = []
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                if line.strip() == "history:" and not line.startswith((" ", "\t")):
                    break
                lines.append(line)
        data = yaml.safe_load("".join(lines)) or {}
        metadata = _normalize_mapping(data.get("metadata"))
        index_raw = data.get("index", [])
        index = [item for item in index_raw if isinstance(item, dict)] if isinstance(index_raw, list) else []
        return metadata, index, ""
    except Exception as exc:  # pragma: no cover - defensive I/O
        return {}, [], str(exc)


def _legacy_archive_path(project_dir: Path) -> Path:
    return project_dir / ".haxaml" / "acts-history.yaml"


@dataclass
class FileSnapshot:
    name: str
    filename: str
    path: Path | None
    exists: bool
    signature: tuple[Any, ...]
    data: dict[str, Any] | None
    load_error: str = ""
    fingerprint: str = ""
    section_fingerprints: dict[str, str] = field(default_factory=dict)

    def section_fingerprint(self, *parts: str) -> str:
        if not parts:
            return self.fingerprint
        if len(parts) == 1:
            return self.section_fingerprints.get(parts[0], stable_fingerprint(None))
        return stable_fingerprint(_nested_value(self.data or {}, list(parts)))


@dataclass
class ArchiveIndexSnapshot:
    path: Path
    exists: bool
    signature: tuple[Any, ...]
    metadata: dict[str, Any]
    index: list[dict[str, Any]]
    load_error: str = ""


@dataclass
class ProjectSnapshot:
    project_dir: Path
    files: dict[str, FileSnapshot]
    archive_index: ArchiveIndexSnapshot


@dataclass
class ContextPackSnapshot:
    task: str
    pack: str
    include_state: bool
    full_sections: dict[str, Any]
    section_markers: dict[str, str]
    section_tokens: dict[str, int]
    tokens: int
    text: str


class RuntimeSnapshotCache:
    """In-memory canonical reads keyed by project directory."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._project_cache: dict[str, ProjectSnapshot] = {}
        self._archive_docs: dict[tuple[str, tuple[Any, ...]], dict[str, Any]] = {}
        self._context_pack_snapshots: dict[tuple[str, str], ContextPackSnapshot] = {}

    def reset(self) -> None:
        with self._lock:
            self._project_cache.clear()
            self._archive_docs.clear()
            self._context_pack_snapshots.clear()

    def get_project_snapshot(self, project_dir: str | Path) -> ProjectSnapshot:
        project_key = _canonical_project_dir(project_dir)
        project_path = Path(project_key)
        with self._lock:
            cached = self._project_cache.get(project_key)
            file_snapshots: dict[str, FileSnapshot] = {}
            cached_files = cached.files if cached else {}
            for name, filename in FRAME_FILES.items():
                resolved = resolve_frame_file(project_path, filename)
                signature = _stat_signature(resolved)
                previous = cached_files.get(name)
                if previous and previous.signature == signature:
                    file_snapshots[name] = previous
                    continue
                exists = resolved is not None and resolved.exists()
                if exists and resolved is not None:
                    raw_data, load_error = _read_yaml_file(resolved)
                else:
                    raw_data, load_error = None, ""
                data = raw_data if isinstance(raw_data, dict) else ({}
                                                                   if raw_data == {} else None)
                fingerprint = stable_fingerprint(data)
                file_snapshots[name] = FileSnapshot(
                    name=name,
                    filename=filename,
                    path=resolved,
                    exists=exists,
                    signature=signature,
                    data=data,
                    load_error=load_error,
                    fingerprint=fingerprint,
                    section_fingerprints=_top_level_section_fingerprints(data),
                )

            archive_snapshot = self._refresh_archive_index(project_path, cached.archive_index if cached else None)
            snapshot = ProjectSnapshot(project_dir=project_path, files=file_snapshots, archive_index=archive_snapshot)
            self._project_cache[project_key] = snapshot
            return snapshot

    def get_frame_bundle(self, project_dir: str | Path) -> dict[str, Any]:
        snapshot = self.get_project_snapshot(project_dir)
        load_errors: list[str] = []
        missing_files: list[str] = []
        data: dict[str, Any] = {}
        for name, file_snapshot in snapshot.files.items():
            data[name] = file_snapshot.data
            if file_snapshot.load_error:
                load_errors.append(f"{file_snapshot.filename}: {file_snapshot.load_error}")
            if not file_snapshot.exists:
                missing_files.append(file_snapshot.filename)
        return {
            "project_dir": snapshot.project_dir,
            "data": data,
            "load_errors": load_errors,
            "missing_files": missing_files,
            "files": snapshot.files,
            "archive_index": snapshot.archive_index,
        }

    def get_archive_index(self, project_dir: str | Path) -> ArchiveIndexSnapshot:
        return self.get_project_snapshot(project_dir).archive_index

    def load_archive_record_details(self, project_dir: str | Path, kind: str, record_id: str) -> dict[str, Any] | None:
        results = self.load_selected_archive_details(project_dir, [(kind, record_id)])
        return results.get((kind, record_id))

    def load_selected_archive_details(
        self,
        project_dir: str | Path,
        records: list[tuple[str, str]],
    ) -> dict[tuple[str, str], dict[str, Any]]:
        archive_index = self.get_archive_index(project_dir)
        if not archive_index.exists:
            return {}
        wanted_by_section: dict[str, set[str]] = {}
        for kind, record_id in records:
            archive_key = ARCHIVE_KIND_KEYS.get(str(kind or "").strip())
            normalized_id = str(record_id or "").strip()
            if not archive_key or not normalized_id:
                continue
            wanted_by_section.setdefault(archive_key, set()).add(normalized_id)
        if not wanted_by_section:
            return {}

        full_doc = self._load_full_archive_doc(archive_index.path, archive_index.signature)
        history = _normalize_mapping(full_doc.get("history"))
        selected: dict[tuple[str, str], dict[str, Any]] = {}
        for kind, archive_key in ARCHIVE_KIND_KEYS.items():
            wanted_ids = wanted_by_section.get(archive_key, set())
            if not wanted_ids:
                continue
            items = history.get(archive_key, [])
            if not isinstance(items, list):
                continue
            for item in items:
                if not isinstance(item, dict):
                    continue
                item_id = str(item.get("id", "")).strip()
                if item_id in wanted_ids:
                    selected[(kind, item_id)] = item
        return selected

    def get_context_pack_snapshot(self, project_dir: str | Path, session_id: str) -> ContextPackSnapshot | None:
        project_key = _canonical_project_dir(project_dir)
        return self._context_pack_snapshots.get((project_key, str(session_id or "").strip()))

    def set_context_pack_snapshot(
        self,
        project_dir: str | Path,
        session_id: str,
        snapshot: ContextPackSnapshot,
    ) -> None:
        project_key = _canonical_project_dir(project_dir)
        with self._lock:
            self._context_pack_snapshots[(project_key, str(session_id or "").strip())] = snapshot

    def _refresh_archive_index(
        self,
        project_dir: Path,
        cached: ArchiveIndexSnapshot | None,
    ) -> ArchiveIndexSnapshot:
        canonical_path = acts_history_path(project_dir)
        legacy_path = _legacy_archive_path(project_dir)
        archive_path = canonical_path if canonical_path.exists() else legacy_path
        signature = _stat_signature(archive_path)
        if cached and cached.signature == signature:
            return cached
        if not archive_path.exists():
            return ArchiveIndexSnapshot(
                path=canonical_path,
                exists=False,
                signature=signature,
                metadata={},
                index=[],
                load_error="",
            )
        metadata, index, load_error = _read_archive_header(archive_path)
        return ArchiveIndexSnapshot(
            path=archive_path,
            exists=True,
            signature=signature,
            metadata=metadata,
            index=index,
            load_error=load_error,
        )

    def _load_full_archive_doc(self, path: Path, signature: tuple[Any, ...]) -> dict[str, Any]:
        cache_key = (str(path.resolve()), signature)
        with self._lock:
            cached = self._archive_docs.get(cache_key)
            if cached is not None:
                return cached
            if not path.exists():
                doc = {}
            else:
                doc = load_yaml(path)
            self._archive_docs = {
                key: value
                for key, value in self._archive_docs.items()
                if key[0] != str(path.resolve())
            }
            self._archive_docs[cache_key] = doc
            return doc


_RUNTIME_CACHE = RuntimeSnapshotCache()


def runtime_cache() -> RuntimeSnapshotCache:
    return _RUNTIME_CACHE
