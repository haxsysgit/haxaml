"""Acts evolution system — safe read/write/compact for acts.yaml (FRAME model).

Handles:
- Atomic writes (write-to-temp then rename)
- File locking (advisory fcntl locks)
- Run recording and compaction
- Decision persistence
"""

import fcntl
import os
import shutil
import tempfile
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import yaml

from haxaml.validator import load_yaml, validate_acts


class StateError(Exception):
    """Raised when acts operations fail."""
    pass


class StateManager:
    """Safe, disciplined acts.yaml manager (FRAME model)."""

    def __init__(self, state_path: str):
        self.path = Path(state_path).resolve()
        if not self.path.exists():
            raise StateError(f"Acts file not found: {self.path}")

    def read(self) -> dict:
        """Read state with shared lock."""
        with self._lock(shared=True):
            return load_yaml(str(self.path))

    def write(self, state: dict) -> None:
        """Write state atomically with exclusive lock.

        Writes to a temp file first, then renames. This prevents
        partial writes from corrupting state.
        """
        errors = self._validate_dict(state)
        if errors:
            raise StateError(f"Invalid state: {'; '.join(errors)}")

        with self._lock(shared=False):
            self._atomic_write(state)

    def record_run(self, task: str, result: str, changes: str = "",
                   decisions: str = "", risks: str = "") -> str:
        """Record a completed run and return its ID."""
        if result not in ("success", "partial", "failed"):
            raise StateError(f"Invalid run result: {result}")

        run_id = f"run-{uuid.uuid4().hex[:8]}"
        now = datetime.now(timezone.utc).isoformat()

        run_entry = {
            "id": run_id,
            "task": task,
            "result": result,
            "changes": changes,
            "decisions": decisions,
            "risks": risks,
            "timestamp": now,
        }

        with self._lock(shared=False):
            state = load_yaml(str(self.path))
            if "runs" not in state:
                state["runs"] = []
            state["runs"].append(run_entry)
            self._atomic_write(state)

        return run_id

    def complete_task(self, result: str = "success", summary: str = "") -> None:
        """Move active_task to completed_tasks and clear active."""
        if result not in ("success", "partial", "failed"):
            raise StateError(f"Invalid result: {result}")

        with self._lock(shared=False):
            state = load_yaml(str(self.path))
            active = state.get("active_task", {})
            if not active or not active.get("name") or active.get("name") == "none":
                raise StateError("No active task to complete")

            completed_entry = {
                "name": active["name"],
                "result": result,
                "summary": summary or active.get("description", ""),
                "completed": datetime.now(timezone.utc).isoformat(),
            }

            if "completed_tasks" not in state:
                state["completed_tasks"] = []
            state["completed_tasks"].append(completed_entry)

            state["active_task"] = {"name": "none"}
            self._atomic_write(state)

    def set_active_task(self, name: str, description: str = "",
                        assignee: str = "builder") -> None:
        """Set a new active task."""
        with self._lock(shared=False):
            state = load_yaml(str(self.path))
            state["active_task"] = {
                "name": name,
                "description": description,
                "started": datetime.now(timezone.utc).isoformat(),
                "assignee": assignee,
            }
            self._atomic_write(state)

    def add_decision(self, decision: str, reasoning: str,
                     reversible: bool = True) -> None:
        """Record a project decision."""
        with self._lock(shared=False):
            state = load_yaml(str(self.path))
            if "decisions" not in state:
                state["decisions"] = []
            state["decisions"].append({
                "decision": decision,
                "reasoning": reasoning,
                "date": datetime.now(timezone.utc).isoformat(),
                "reversible": reversible,
            })
            self._atomic_write(state)

    def add_blocker(self, name: str, reason: str,
                    depends_on: str = "") -> None:
        """Add a blocked task."""
        with self._lock(shared=False):
            state = load_yaml(str(self.path))
            if "blocked_tasks" not in state:
                state["blocked_tasks"] = []
            entry = {"name": name, "reason": reason}
            if depends_on:
                entry["depends_on"] = depends_on
            state["blocked_tasks"].append(entry)
            self._atomic_write(state)

    def compact(self, keep_recent: int = 5) -> dict:
        """Compact old runs into a summary.

        Keeps the most recent `keep_recent` runs and summarizes the rest.
        Returns compaction stats.
        """
        with self._lock(shared=False):
            state = load_yaml(str(self.path))
            runs = state.get("runs", [])

            if len(runs) <= keep_recent:
                return {"compacted": 0, "kept": len(runs), "total": len(runs)}

            old_runs = runs[:-keep_recent]
            kept_runs = runs[-keep_recent:]

            success_count = sum(1 for r in old_runs if r.get("result") == "success")
            partial_count = sum(1 for r in old_runs if r.get("result") == "partial")
            failed_count = sum(1 for r in old_runs if r.get("result") == "failed")

            key_decisions = [
                r["decisions"] for r in old_runs
                if r.get("decisions")
            ]

            key_changes = [
                r["changes"] for r in old_runs
                if r.get("changes")
            ]

            summary_parts = [
                f"Compacted {len(old_runs)} runs: "
                f"{success_count} success, {partial_count} partial, {failed_count} failed.",
            ]
            if key_decisions:
                summary_parts.append(f"Key decisions: {'; '.join(key_decisions[:5])}")
            if key_changes:
                summary_parts.append(f"Key changes: {'; '.join(key_changes[:5])}")

            compaction = state.get("compaction", {})
            prev_compacted = compaction.get("total_runs_compacted", 0)
            prev_summary = compaction.get("summary", "")

            if prev_summary and prev_summary != "No runs yet.":
                combined_summary = f"{prev_summary} | {' '.join(summary_parts)}"
            else:
                combined_summary = " ".join(summary_parts)

            state["runs"] = kept_runs
            state["compaction"] = {
                "last_compacted": datetime.now(timezone.utc).isoformat(),
                "total_runs_compacted": prev_compacted + len(old_runs),
                "summary": combined_summary,
            }

            self._atomic_write(state)

            return {
                "compacted": len(old_runs),
                "kept": len(kept_runs),
                "total": prev_compacted + len(old_runs) + len(kept_runs),
            }

    def get_stats(self) -> dict:
        """Get state statistics for diagnostics."""
        state = self.read()
        runs = state.get("runs", [])
        completed = state.get("completed_tasks", [])
        blocked = state.get("blocked_tasks", [])
        decisions = state.get("decisions", [])
        unresolved = state.get("unresolved_dependencies", [])
        compaction = state.get("compaction", {})

        yaml_text = yaml.dump(state, default_flow_style=False)
        file_size = self.path.stat().st_size

        return {
            "current_phase": state.get("current_phase", "unknown"),
            "active_task": state.get("active_task", {}).get("name", "none"),
            "completed_count": len(completed),
            "blocked_count": len(blocked),
            "decision_count": len(decisions),
            "unresolved_count": len(unresolved),
            "run_count": len(runs),
            "total_runs_compacted": compaction.get("total_runs_compacted", 0),
            "file_size_bytes": file_size,
            "yaml_chars": len(yaml_text),
        }

    @contextmanager
    def _lock(self, shared: bool = True):
        """Advisory file lock using fcntl."""
        lock_path = self.path.with_suffix(".lock")
        lock_fd = open(lock_path, "w")
        try:
            if shared:
                fcntl.flock(lock_fd, fcntl.LOCK_SH)
            else:
                fcntl.flock(lock_fd, fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            lock_fd.close()

    def _atomic_write(self, state: dict) -> None:
        """Write state to temp file then rename for atomicity."""
        dir_path = self.path.parent
        fd, tmp_path = tempfile.mkstemp(
            suffix=".yaml", prefix=".state_", dir=str(dir_path)
        )
        try:
            with os.fdopen(fd, "w") as f:
                yaml.dump(state, f, default_flow_style=False, sort_keys=False)
            os.replace(tmp_path, str(self.path))
        except Exception:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise

    def _validate_dict(self, state: dict) -> list[str]:
        """Validate state dict against schema without writing."""
        from jsonschema import Draft202012Validator
        from haxaml.validator import load_schema

        schema = load_schema("acts.schema.yaml")
        validator = Draft202012Validator(schema)
        errors = []
        for error in validator.iter_errors(state):
            path = ".".join(str(p) for p in error.absolute_path) or "(root)"
            errors.append(f"[{path}] {error.message}")
        return errors
