"""Helpers for keeping old acts history in a separate archive file.

Haxaml uses a tiered history strategy to manage context window efficiency:
1. Hot State (.haxaml/acts.yaml): Contains recent runs, sessions, and active tasks.
   This is always included in the agent's context to provide immediate continuity.
2. Cold State (.haxaml/archive/acts-history.yaml): Contains older historical records.
   This is excluded from the default context pack but remains available for
   semantic retrieval via `haxaml_context_fetch`.

This separation prevents acts.yaml from bloating over time while ensuring
the full project diary remains accessible for long-term memory.
"""

from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path
from typing import Any

from haxaml.paths import acts_history_path, frame_path
from haxaml.utils import clean_str_list, keywords_from_text, normalized_text, now_iso
from haxaml.yaml_utils import dump_yaml, load_yaml


ARCHIVE_VERSION = "0.6.7"
DEFAULT_MEMORY_POLICY = {
    "archive_mode": "on_record",
    "max_hot_runs": 5,
    "max_hot_sessions": 5,
    "max_hot_verifications": 5,
    "max_hot_completed_tasks": 5,
    "max_hot_decisions": 8,
    "max_acts_bytes": 16000,
    "keep_decisions_hot": True,
}
ARCHIVE_KINDS = {
    "run": "runs",
    "session": "sessions",
    "verification": "verifications",
    "completed_task": "completed_tasks",
    "decision": "decisions",
}


class ArchiveError(Exception):
    """Raised when archive operations fail."""

def default_memory_policy() -> dict[str, Any]:
    """Return the default advisory-first memory policy."""
    return dict(DEFAULT_MEMORY_POLICY)


def normalize_memory_policy(value: Any) -> dict[str, Any]:
    """Normalize memory policy values from rules.yaml."""
    policy = default_memory_policy()
    if not isinstance(value, dict):
        return policy

    archive_mode = normalized_text(value.get("archive_mode", policy["archive_mode"])).lower()
    if archive_mode not in {"manual", "on_record"}:
        archive_mode = policy["archive_mode"]
    policy["archive_mode"] = archive_mode

    for key in (
        "max_hot_runs",
        "max_hot_sessions",
        "max_hot_verifications",
        "max_hot_completed_tasks",
        "max_hot_decisions",
        "max_acts_bytes",
    ):
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
            "completed_tasks": keep_recent,
            "decisions": keep_recent,
        }
    normalized = normalize_memory_policy(policy)
    return {
        "runs": int(normalized["max_hot_runs"]),
        "sessions": int(normalized["max_hot_sessions"]),
        "verifications": int(normalized["max_hot_verifications"]),
        "completed_tasks": int(normalized["max_hot_completed_tasks"]),
        "decisions": int(normalized["max_hot_decisions"]),
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
        "path": normalized_text(raw.get("path", "")),
        "archive_mode": normalized_text(raw.get("archive_mode", "manual")).lower() or "manual",
        "last_archived_at": normalized_text(raw.get("last_archived_at", "")),
        "archived_counts": {
            "runs": int(counts.get("runs", 0) or 0),
            "sessions": int(counts.get("sessions", 0) or 0),
            "verifications": int(counts.get("verifications", 0) or 0),
            "completed_tasks": int(counts.get("completed_tasks", 0) or 0),
            "decisions": int(counts.get("decisions", 0) or 0),
        },
        "hot_limits": {
            "runs": int(hot_limits.get("runs", 0) or 0),
            "sessions": int(hot_limits.get("sessions", 0) or 0),
            "verifications": int(hot_limits.get("verifications", 0) or 0),
            "completed_tasks": int(hot_limits.get("completed_tasks", 0) or 0),
            "decisions": int(hot_limits.get("decisions", 0) or 0),
        },
    }


def decision_id(record: dict[str, Any]) -> str:
    """Return a stable ID for archived decision records."""
    explicit = normalized_text(record.get("id", ""))
    if explicit:
        return explicit
    seed = "|".join(
        [
            normalized_text(record.get("decision", "")),
            normalized_text(record.get("reasoning", "")),
            normalized_text(record.get("date", "")),
        ]
    )
    digest = hashlib.sha1(seed.encode("utf-8")).hexdigest()[:10]
    return f"decision-{digest}"


def decision_stub(record: dict[str, Any], *, reasoning_chars: int = 160) -> dict[str, Any]:
    """Return a compact hot-state stub for a decision."""
    reasoning = normalized_text(record.get("reasoning", ""))
    if len(reasoning) > reasoning_chars:
        reasoning = reasoning[: reasoning_chars - 3].rstrip() + "..."
    return {
        "id": decision_id(record),
        "decision": normalized_text(record.get("decision", "")),
        "reasoning": reasoning,
        "date": normalized_text(record.get("date", "")),
        "reversible": bool(record.get("reversible", True)),
        "archived": True,
    }


def completed_task_id(record: dict[str, Any]) -> str:
    """Return a stable ID for completed task archive records."""
    explicit = normalized_text(record.get("id", ""))
    if explicit:
        return explicit
    seed = "|".join(
        [
            normalized_text(record.get("name", "")),
            normalized_text(record.get("result", "")),
            normalized_text(record.get("completed", "")),
            normalized_text(record.get("summary", "")),
        ]
    )
    digest = hashlib.sha1(seed.encode("utf-8")).hexdigest()[:10]
    return f"completed-{digest}"


def completed_task_stub(record: dict[str, Any], *, summary_chars: int = 160) -> dict[str, Any]:
    """Return a compact hot-state stub for a completed task."""
    summary = normalized_text(record.get("summary", ""))
    if len(summary) > summary_chars:
        summary = summary[: summary_chars - 3].rstrip() + "..."
    return {
        "id": completed_task_id(record),
        "name": normalized_text(record.get("name", "")),
        "result": normalized_text(record.get("result", "")),
        "summary": summary,
        "completed": normalized_text(record.get("completed", "")),
        "archived": True,
    }


def build_index_entry(kind: str, record: dict[str, Any]) -> dict[str, Any]:
    """Build a compact deterministic index entry for an archived record."""
    record_id = normalized_text(record.get("id", ""))
    task = normalized_text(record.get("task", ""))
    if kind == "run":
        status = normalized_text(record.get("result", ""))
        summary = normalized_text(record.get("changes", "")) or normalized_text(record.get("decisions", ""))
        timestamp = normalized_text(record.get("timestamp", ""))
    elif kind == "session":
        status = normalized_text(record.get("status", ""))
        summary = normalized_text(record.get("description", ""))
        timestamp = (
            normalized_text(record.get("updated", ""))
            or normalized_text(record.get("ended", ""))
            or normalized_text(record.get("started", ""))
        )
    elif kind == "verification":
        status = normalized_text(record.get("verdict", ""))
        summary = normalized_text(record.get("summary", ""))
        timestamp = normalized_text(record.get("timestamp", ""))
    elif kind == "decision":
        record_id = record_id or decision_id(record)
        task = normalized_text(record.get("decision", ""))
        status = "reversible" if bool(record.get("reversible", True)) else "fixed"
        summary = normalized_text(record.get("reasoning", ""))
        timestamp = normalized_text(record.get("date", ""))
    else:
        record_id = record_id or completed_task_id(record)
        task = normalized_text(record.get("name", ""))
        status = normalized_text(record.get("result", ""))
        summary = normalized_text(record.get("summary", ""))
        timestamp = normalized_text(record.get("completed", ""))

    file_refs = clean_str_list(record.get("file_refs", []))
    if not file_refs and kind == "verification":
        file_refs = clean_str_list(record.get("evidence_refs", []))
    module_refs = clean_str_list(record.get("module_refs", []))
    keywords = clean_str_list(record.get("keywords", []))
    if not keywords:
        keywords = keywords_from_text(task, summary, status, *file_refs, *module_refs)

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
    """Managed lossless archive for older runs, sessions, and verifications.

    ActsArchive handles the 'cold' storage tier. It maintains a compact index
    of all archived records to support fast relevance ranking during retrieval
    without loading the full history body into memory.
    """

    def __init__(self, project_dir: str | Path):
        self.project_dir = Path(project_dir).resolve()
        self.path = acts_history_path(self.project_dir)
        self.legacy_path = frame_path(self.project_dir, "acts-history.yaml")

    def _read_path(self) -> Path:
        if self.path.exists():
            return self.path
        if self.legacy_path.exists():
            return self.legacy_path
        return self.path

    def exists(self) -> bool:
        return self.path.exists() or self.legacy_path.exists()

    def read(self) -> dict[str, Any]:
        read_path = self._read_path()
        if not read_path.exists():
            return self._empty_doc()
        try:
            data = load_yaml(read_path)
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
                handle.write(dump_yaml(normalized, sort_keys=False))
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
        completed_tasks: list[dict[str, Any]] | None = None,
        decisions: list[dict[str, Any]] | None = None,
        archive_mode: str,
    ) -> dict[str, int]:
        """Append cold history into the archive and update the header index."""
        runs = list(runs or [])
        sessions = list(sessions or [])
        verifications = list(verifications or [])
        completed_tasks = list(completed_tasks or [])
        decisions = list(decisions or [])
        doc = self.read()
        history = doc["history"]
        index = doc["index"]
        existing = {(item.get("kind"), item.get("id")) for item in index if isinstance(item, dict)}
        counts = {"runs": 0, "sessions": 0, "verifications": 0, "completed_tasks": 0, "decisions": 0}

        for kind, key, items in (
            ("run", "runs", runs),
            ("session", "sessions", sessions),
            ("verification", "verifications", verifications),
            ("completed_task", "completed_tasks", completed_tasks),
            ("decision", "decisions", decisions),
        ):
            for item in items:
                if not isinstance(item, dict):
                    continue
                if kind == "completed_task" and not normalized_text(item.get("id", "")):
                    item = dict(item)
                    item["id"] = completed_task_id(item)
                if kind == "decision" and not normalized_text(item.get("id", "")):
                    item = dict(item)
                    item["id"] = decision_id(item)
                entry = build_index_entry(kind, item)
                marker = (entry["kind"], entry["id"])
                if marker in existing:
                    continue
                history[key].append(item)
                index.append(entry)
                existing.add(marker)
                counts[key] += 1

        doc["metadata"]["archive_mode"] = archive_mode
        doc["metadata"]["last_archived_at"] = now_iso()
        doc["metadata"]["counts"] = {
            "runs": len(history["runs"]),
            "sessions": len(history["sessions"]),
            "verifications": len(history["verifications"]),
            "completed_tasks": len(history["completed_tasks"]),
            "decisions": len(history["decisions"]),
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
            "completed_tasks": int(counts.get("completed_tasks", 0) or 0),
            "decisions": int(counts.get("decisions", 0) or 0),
        }

    def has_record(self, record_id: str) -> bool:
        from haxaml.runtime_cache import runtime_cache

        wanted = normalized_text(record_id)
        if not wanted:
            return False
        for item in runtime_cache().get_archive_index(self.project_dir).index:
            if isinstance(item, dict) and normalized_text(item.get("id", "")) == wanted:
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
                "created_at": now_iso(),
                "last_archived_at": "",
                "archive_mode": "manual",
                "counts": {"runs": 0, "sessions": 0, "verifications": 0, "completed_tasks": 0, "decisions": 0},
            },
            "index": [],
            "history": {
                "runs": [],
                "sessions": [],
                "verifications": [],
                "completed_tasks": [],
                "decisions": [],
            },
        }

    def _normalize_doc(self, data: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(data, dict):
            raise ArchiveError("Archive root must be a mapping.")
        doc = self._empty_doc()
        metadata = data.get("metadata", {})
        if not isinstance(metadata, dict):
            raise ArchiveError("Archive metadata must be a mapping.")
        doc["metadata"]["version"] = normalized_text(metadata.get("version", ARCHIVE_VERSION)) or ARCHIVE_VERSION
        doc["metadata"]["managed_by"] = normalized_text(metadata.get("managed_by", "haxaml")) or "haxaml"
        doc["metadata"]["created_at"] = normalized_text(metadata.get("created_at", doc["metadata"]["created_at"]))
        doc["metadata"]["last_archived_at"] = normalized_text(metadata.get("last_archived_at", ""))
        doc["metadata"]["archive_mode"] = normalized_text(metadata.get("archive_mode", "manual")).lower() or "manual"

        counts = metadata.get("counts", {})
        if isinstance(counts, dict):
            doc["metadata"]["counts"] = {
                "runs": int(counts.get("runs", 0) or 0),
                "sessions": int(counts.get("sessions", 0) or 0),
                "verifications": int(counts.get("verifications", 0) or 0),
                "completed_tasks": int(counts.get("completed_tasks", 0) or 0),
                "decisions": int(counts.get("decisions", 0) or 0),
            }

        index = data.get("index", [])
        if not isinstance(index, list):
            raise ArchiveError("Archive index must be a list.")
        doc["index"] = [item for item in index if isinstance(item, dict)]

        history = data.get("history", {})
        if not isinstance(history, dict):
            raise ArchiveError("Archive history must be a mapping.")
        for key in ("runs", "sessions", "verifications", "completed_tasks", "decisions"):
            items = history.get(key, [])
            if not isinstance(items, list):
                raise ArchiveError(f"Archive history.{key} must be a list.")
            doc["history"][key] = [item for item in items if isinstance(item, dict)]
        doc["metadata"]["counts"] = {
            "runs": len(doc["history"]["runs"]),
            "sessions": len(doc["history"]["sessions"]),
            "verifications": len(doc["history"]["verifications"]),
            "completed_tasks": len(doc["history"]["completed_tasks"]),
            "decisions": len(doc["history"]["decisions"]),
        }
        return doc
