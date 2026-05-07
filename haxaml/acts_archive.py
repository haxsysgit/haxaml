"""Helpers for keeping old acts history in a separate archive file.

The main acts file should stay small and focused on current work.
Older runs, sessions, and verification records move here so they remain
available for guided lookup without bloating the default context path.
"""

from __future__ import annotations

import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from haxaml.paths import acts_history_path


ARCHIVE_VERSION = "0.6.7"
DEFAULT_MEMORY_POLICY = {
    "archive_mode": "manual",
    "max_hot_runs": 5,
    "max_hot_sessions": 5,
    "max_hot_verifications": 5,
    "max_acts_bytes": 16000,
    "keep_decisions_hot": True,
}
ARCHIVE_KINDS = {
    "run": "runs",
    "session": "sessions",
    "verification": "verifications",
}


class ArchiveError(Exception):
    """Raised when archive operations fail."""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _clean_str_list(items: Any) -> list[str]:
    if not isinstance(items, list):
        return []
    cleaned: list[str] = []
    seen = set()
    for item in items:
        text = _clean_text(item)
        if not text:
            continue
        if text in seen:
            continue
        seen.add(text)
        cleaned.append(text)
    return cleaned


def _keywords_from_text(*parts: Any, limit: int = 12) -> list[str]:
    stop = {
        "the", "and", "for", "with", "that", "this", "from", "into", "have", "will",
        "when", "what", "where", "then", "than", "them", "they", "been", "were",
        "your", "about", "after", "before", "only", "over", "under", "into", "task",
        "tasks", "work", "works", "working", "update", "updated", "using",
    }
    tokens: list[str] = []
    seen = set()
    for part in parts:
        text = _clean_text(part).lower()
        if not text:
            continue
        for raw in text.replace("/", " ").replace("-", " ").replace("_", " ").split():
            token = "".join(ch for ch in raw if ch.isalnum())
            if len(token) < 4 or token in stop or token in seen:
                continue
            seen.add(token)
            tokens.append(token)
            if len(tokens) >= limit:
                return tokens
    return tokens


def default_memory_policy() -> dict[str, Any]:
    """Return the default advisory-first memory policy."""
    return dict(DEFAULT_MEMORY_POLICY)


def normalize_memory_policy(value: Any) -> dict[str, Any]:
    """Normalize memory policy values from rules.yaml."""
    policy = default_memory_policy()
    if not isinstance(value, dict):
        return policy

    archive_mode = _clean_text(value.get("archive_mode", policy["archive_mode"])).lower()
    if archive_mode not in {"manual", "on_record"}:
        archive_mode = policy["archive_mode"]
    policy["archive_mode"] = archive_mode

    for key in ("max_hot_runs", "max_hot_sessions", "max_hot_verifications", "max_acts_bytes"):
        raw = value.get(key, policy[key])
        if isinstance(raw, int) and raw > 0:
            policy[key] = raw

    keep_hot = value.get("keep_decisions_hot", policy["keep_decisions_hot"])
    policy["keep_decisions_hot"] = bool(keep_hot)
    return policy


def hot_limits_from_policy(policy: dict[str, Any], keep_recent: int | None = None) -> dict[str, int]:
    """Return normalized hot-state limits."""
    if isinstance(keep_recent, int) and keep_recent > 0:
        return {
            "runs": keep_recent,
            "sessions": keep_recent,
            "verifications": keep_recent,
        }
    normalized = normalize_memory_policy(policy)
    return {
        "runs": int(normalized["max_hot_runs"]),
        "sessions": int(normalized["max_hot_sessions"]),
        "verifications": int(normalized["max_hot_verifications"]),
    }


def archive_metadata(state: dict[str, Any]) -> dict[str, Any]:
    """Return normalized acts.archive metadata."""
    raw = state.get("archive", {}) if isinstance(state, dict) else {}
    if not isinstance(raw, dict):
        raw = {}
    counts = raw.get("archived_counts", {})
    if not isinstance(counts, dict):
        counts = {}
    hot_limits = raw.get("hot_limits", {})
    if not isinstance(hot_limits, dict):
        hot_limits = {}
    return {
        "path": _clean_text(raw.get("path", "")),
        "archive_mode": _clean_text(raw.get("archive_mode", "manual")).lower() or "manual",
        "last_archived_at": _clean_text(raw.get("last_archived_at", "")),
        "archived_counts": {
            "runs": int(counts.get("runs", 0) or 0),
            "sessions": int(counts.get("sessions", 0) or 0),
            "verifications": int(counts.get("verifications", 0) or 0),
        },
        "hot_limits": {
            "runs": int(hot_limits.get("runs", 0) or 0),
            "sessions": int(hot_limits.get("sessions", 0) or 0),
            "verifications": int(hot_limits.get("verifications", 0) or 0),
        },
    }


def build_index_entry(kind: str, record: dict[str, Any]) -> dict[str, Any]:
    """Build a compact deterministic index entry for an archived record."""
    record_id = _clean_text(record.get("id", ""))
    task = _clean_text(record.get("task", ""))
    if kind == "run":
        status = _clean_text(record.get("result", ""))
        summary = _clean_text(record.get("changes", "")) or _clean_text(record.get("decisions", ""))
        timestamp = _clean_text(record.get("timestamp", ""))
    elif kind == "session":
        status = _clean_text(record.get("status", ""))
        summary = _clean_text(record.get("description", ""))
        timestamp = _clean_text(record.get("updated", "")) or _clean_text(record.get("ended", "")) or _clean_text(record.get("started", ""))
    else:
        status = _clean_text(record.get("verdict", ""))
        summary = _clean_text(record.get("summary", ""))
        timestamp = _clean_text(record.get("timestamp", ""))

    file_refs = _clean_str_list(record.get("file_refs", []))
    if not file_refs and kind == "verification":
        file_refs = _clean_str_list(record.get("evidence_refs", []))
    module_refs = _clean_str_list(record.get("module_refs", []))
    keywords = _clean_str_list(record.get("keywords", []))
    if not keywords:
        keywords = _keywords_from_text(task, summary, status, *file_refs, *module_refs)

    return {
        "kind": kind,
        "id": record_id,
        "task": task,
        "status_or_result": status,
        "timestamp": timestamp,
        "summary": summary,
        "file_refs": file_refs,
        "module_refs": module_refs,
        "keywords": keywords,
    }


class ActsArchive:
    """Managed lossless archive for older runs, sessions, and verifications."""

    def __init__(self, project_dir: str | Path):
        self.project_dir = Path(project_dir).resolve()
        self.path = acts_history_path(self.project_dir)

    def exists(self) -> bool:
        return self.path.exists()

    def read(self) -> dict[str, Any]:
        if not self.path.exists():
            return self._empty_doc()
        try:
            with open(self.path, encoding="utf-8") as handle:
                data = yaml.safe_load(handle) or {}
        except Exception as exc:  # pragma: no cover - defensive I/O
            raise ArchiveError(f"Could not read archive: {exc}") from exc
        return self._normalize_doc(data)

    def write(self, doc: dict[str, Any]) -> None:
        normalized = self._normalize_doc(doc)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(
            suffix=".yaml",
            prefix=".acts-history_",
            dir=str(self.path.parent),
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                yaml.dump(normalized, handle, default_flow_style=False, sort_keys=False)
            os.replace(tmp_path, self.path)
        except Exception as exc:  # pragma: no cover - defensive I/O
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise ArchiveError(f"Could not write archive: {exc}") from exc

    def append(
        self,
        *,
        runs: list[dict[str, Any]] | None = None,
        sessions: list[dict[str, Any]] | None = None,
        verifications: list[dict[str, Any]] | None = None,
        archive_mode: str,
    ) -> dict[str, int]:
        """Append cold history into the archive and update the header index."""
        runs = list(runs or [])
        sessions = list(sessions or [])
        verifications = list(verifications or [])
        doc = self.read()
        history = doc["history"]
        index = doc["index"]
        existing = {(item.get("kind"), item.get("id")) for item in index if isinstance(item, dict)}
        counts = {"runs": 0, "sessions": 0, "verifications": 0}

        for kind, key, items in (
            ("run", "runs", runs),
            ("session", "sessions", sessions),
            ("verification", "verifications", verifications),
        ):
            for item in items:
                if not isinstance(item, dict):
                    continue
                entry = build_index_entry(kind, item)
                marker = (entry["kind"], entry["id"])
                if marker in existing:
                    continue
                history[key].append(item)
                index.append(entry)
                existing.add(marker)
                counts[key] += 1

        doc["metadata"]["archive_mode"] = archive_mode
        doc["metadata"]["last_archived_at"] = _now_iso()
        doc["metadata"]["counts"] = {
            "runs": len(history["runs"]),
            "sessions": len(history["sessions"]),
            "verifications": len(history["verifications"]),
        }
        self.write(doc)
        return counts

    def get_counts(self) -> dict[str, int]:
        from haxaml.runtime_cache import runtime_cache

        snapshot = runtime_cache().get_archive_index(self.project_dir)
        counts = snapshot.metadata.get("counts", {}) if snapshot.exists else {}
        return {
            "runs": int(counts.get("runs", 0) or 0),
            "sessions": int(counts.get("sessions", 0) or 0),
            "verifications": int(counts.get("verifications", 0) or 0),
        }

    def has_record(self, record_id: str) -> bool:
        from haxaml.runtime_cache import runtime_cache

        wanted = _clean_text(record_id)
        if not wanted:
            return False
        for item in runtime_cache().get_archive_index(self.project_dir).index:
            if isinstance(item, dict) and _clean_text(item.get("id", "")) == wanted:
                return True
        return False

    def load_record_details(self, kind: str, record_id: str) -> dict[str, Any] | None:
        """Return one archived record by kind/id."""
        from haxaml.runtime_cache import runtime_cache

        return runtime_cache().load_archive_record_details(self.project_dir, kind, record_id)

    def load_selected_record_details(self, records: list[tuple[str, str]]) -> dict[tuple[str, str], dict[str, Any]]:
        """Return full details for the selected archived records with one archive read."""
        from haxaml.runtime_cache import runtime_cache

        return runtime_cache().load_selected_archive_details(self.project_dir, records)

    # Compatibility wrappers kept during the 0.6.x line while internal call sites
    # move to more readable names.
    def hydrate(self, kind: str, record_id: str) -> dict[str, Any] | None:
        return self.load_record_details(kind, record_id)

    def hydrate_many(self, records: list[tuple[str, str]]) -> dict[tuple[str, str], dict[str, Any]]:
        return self.load_selected_record_details(records)

    def index_entries(self) -> list[dict[str, Any]]:
        from haxaml.runtime_cache import runtime_cache

        return list(runtime_cache().get_archive_index(self.project_dir).index)

    def _empty_doc(self) -> dict[str, Any]:
        return {
            "metadata": {
                "version": ARCHIVE_VERSION,
                "managed_by": "haxaml",
                "created_at": _now_iso(),
                "last_archived_at": "",
                "archive_mode": "manual",
                "counts": {"runs": 0, "sessions": 0, "verifications": 0},
            },
            "index": [],
            "history": {
                "runs": [],
                "sessions": [],
                "verifications": [],
            },
        }

    def _normalize_doc(self, data: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(data, dict):
            raise ArchiveError("Archive root must be a mapping.")
        doc = self._empty_doc()
        metadata = data.get("metadata", {})
        if not isinstance(metadata, dict):
            raise ArchiveError("Archive metadata must be a mapping.")
        doc["metadata"]["version"] = _clean_text(metadata.get("version", ARCHIVE_VERSION)) or ARCHIVE_VERSION
        doc["metadata"]["managed_by"] = _clean_text(metadata.get("managed_by", "haxaml")) or "haxaml"
        doc["metadata"]["created_at"] = _clean_text(metadata.get("created_at", doc["metadata"]["created_at"]))
        doc["metadata"]["last_archived_at"] = _clean_text(metadata.get("last_archived_at", ""))
        doc["metadata"]["archive_mode"] = _clean_text(metadata.get("archive_mode", "manual")).lower() or "manual"

        counts = metadata.get("counts", {})
        if isinstance(counts, dict):
            doc["metadata"]["counts"] = {
                "runs": int(counts.get("runs", 0) or 0),
                "sessions": int(counts.get("sessions", 0) or 0),
                "verifications": int(counts.get("verifications", 0) or 0),
            }

        index = data.get("index", [])
        if not isinstance(index, list):
            raise ArchiveError("Archive index must be a list.")
        doc["index"] = [item for item in index if isinstance(item, dict)]

        history = data.get("history", {})
        if not isinstance(history, dict):
            raise ArchiveError("Archive history must be a mapping.")
        for key in ("runs", "sessions", "verifications"):
            items = history.get(key, [])
            if not isinstance(items, list):
                raise ArchiveError(f"Archive history.{key} must be a list.")
            doc["history"][key] = [item for item in items if isinstance(item, dict)]

        if not doc["metadata"]["counts"]:
            doc["metadata"]["counts"] = {
                "runs": len(doc["history"]["runs"]),
                "sessions": len(doc["history"]["sessions"]),
                "verifications": len(doc["history"]["verifications"]),
            }
        else:
            doc["metadata"]["counts"] = {
                "runs": len(doc["history"]["runs"]),
                "sessions": len(doc["history"]["sessions"]),
                "verifications": len(doc["history"]["verifications"]),
            }
        return doc
