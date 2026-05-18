"""Acts state management with tiered hot/cold history."""

from __future__ import annotations

import fcntl
import hashlib
import os
import tempfile
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import yaml

from haxaml.acts_archive import (
    ActsArchive,
    archive_metadata,
    decision_id,
    completed_task_id,
    completed_task_stub,
    default_memory_policy,
    hot_limits_from_policy,
    normalize_memory_policy,
)
from haxaml.paths import resolve_frame_file
from haxaml.utils import clean_str_list, keywords_from_text, now_iso
from haxaml.validator import load_yaml


class StateError(Exception):
    """Raised when acts operations fail."""

class StateManager:
    """Safe, disciplined acts.yaml manager."""

    def __init__(self, state_path: str):
        self.path = Path(state_path).resolve()
        self.project_dir = self.path.parent.parent if self.path.parent.name == ".haxaml" else self.path.parent
        self.archive = ActsArchive(self.project_dir)
        if not self.path.exists():
            raise StateError(f"Acts file not found: {self.path}")

    def read(self) -> dict:
        """Read state with shared lock."""
        with self._lock(shared=True):
            return load_yaml(str(self.path))

    def write(self, state: dict) -> None:
        """Write state atomically with exclusive lock."""
        errors = self._validate_dict(state)
        if errors:
            raise StateError(f"Invalid state: {'; '.join(errors)}")

        with self._lock(shared=False):
            self._atomic_write(state)

    def record_run(
        self,
        task: str,
        result: str,
        changes: str = "",
        decisions: str = "",
        risks: str = "",
        *,
        file_refs: list[str] | None = None,
        module_refs: list[str] | None = None,
        verification_id: str = "",
        keywords: list[str] | None = None,
    ) -> str:
        """Record a completed run and return its ID."""
        if result not in ("success", "partial", "failed"):
            raise StateError(f"Invalid run result: {result}")

        run_id = f"run-{uuid.uuid4().hex[:8]}"
        now = now_iso()
        run_entry = {
            "id": run_id,
            "task": task,
            "result": result,
            "changes": changes,
            "decisions": decisions,
            "risks": risks,
            "timestamp": now,
            "file_refs": clean_str_list(file_refs or []),
            "module_refs": clean_str_list(module_refs or []),
            "verification_id": str(verification_id or "").strip(),
            "keywords": clean_str_list(keywords or []) or keywords_from_text(task, changes, decisions, risks),
        }

        with self._lock(shared=False):
            state = load_yaml(str(self.path))
            runs = state.get("runs", [])
            if not isinstance(runs, list):
                runs = []
            runs.append(run_entry)
            state["runs"] = runs
            self._ensure_archive_state(state)
            self._atomic_write(state)

        return run_id

    def record_completed_run(
        self,
        task: str,
        result: str,
        changes: str = "",
        decisions: str = "",
        risks: str = "",
        summary: str = "",
        *,
        file_refs: list[str] | None = None,
        module_refs: list[str] | None = None,
        verification_id: str = "",
        keywords: list[str] | None = None,
    ) -> str:
        """Record a run and close the active task in one atomic state write."""
        if result not in ("success", "partial", "failed"):
            raise StateError(f"Invalid run result: {result}")

        run_id = f"run-{uuid.uuid4().hex[:8]}"
        now = now_iso()
        run_entry = {
            "id": run_id,
            "task": task,
            "result": result,
            "changes": changes,
            "decisions": decisions,
            "risks": risks,
            "timestamp": now,
            "file_refs": clean_str_list(file_refs or []),
            "module_refs": clean_str_list(module_refs or []),
            "verification_id": str(verification_id or "").strip(),
            "keywords": clean_str_list(keywords or []) or keywords_from_text(task, changes, decisions, risks),
        }

        with self._lock(shared=False):
            state = load_yaml(str(self.path))
            active = state.get("active_task", {})
            if not active or not active.get("name") or active.get("name") == "none":
                raise StateError("No active task to complete")

            runs = state.get("runs", [])
            if not isinstance(runs, list):
                runs = []
            runs.append(run_entry)
            state["runs"] = runs

            completed = state.get("completed_tasks", [])
            if not isinstance(completed, list):
                completed = []
            completed.append(
                {
                    "id": f"completed-{uuid.uuid4().hex[:8]}",
                    "name": active["name"],
                    "result": result,
                    "summary": summary or changes or active.get("description", ""),
                    "completed": now,
                }
            )
            state["completed_tasks"] = completed
            state["active_task"] = {"name": "none"}
            self._ensure_archive_state(state)
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
                "id": f"completed-{uuid.uuid4().hex[:8]}",
                "name": active["name"],
                "result": result,
                "summary": summary or active.get("description", ""),
                "completed": now_iso(),
            }

            completed = state.get("completed_tasks", [])
            if not isinstance(completed, list):
                completed = []
            completed.append(completed_entry)
            state["completed_tasks"] = completed
            state["active_task"] = {"name": "none"}
            self._ensure_archive_state(state)
            self._atomic_write(state)

    def set_active_task(self, name: str, description: str = "", assignee: str = "builder") -> None:
        """Set a new active task."""
        with self._lock(shared=False):
            state = load_yaml(str(self.path))
            state["active_task"] = {
                "name": name,
                "description": description,
                "started": now_iso(),
                "assignee": assignee,
            }
            self._ensure_archive_state(state)
            self._atomic_write(state)

    def add_decision(
        self,
        decision: str,
        reasoning: str,
        reversible: bool = True,
        *,
        file_refs: list[str] | None = None,
        module_refs: list[str] | None = None,
    ) -> None:
        """Record a durable project decision."""
        with self._lock(shared=False):
            state = load_yaml(str(self.path))
            decisions = state.get("decisions", [])
            if not isinstance(decisions, list):
                decisions = []
            decisions.append(
                {
                    "id": f"decision-{uuid.uuid4().hex[:8]}",
                    "decision": decision,
                    "reasoning": reasoning,
                    "date": now_iso(),
                    "reversible": reversible,
                    "file_refs": clean_str_list(file_refs or []),
                    "module_refs": clean_str_list(module_refs or []),
                }
            )
            state["decisions"] = decisions
            self._ensure_archive_state(state)
            self._atomic_write(state)

    def add_blocker(self, name: str, reason: str, depends_on: str = "") -> None:
        """Add a blocked task."""
        with self._lock(shared=False):
            state = load_yaml(str(self.path))
            blocked = state.get("blocked_tasks", [])
            if not isinstance(blocked, list):
                blocked = []
            entry = {"name": name, "reason": reason}
            if depends_on:
                entry["depends_on"] = depends_on
            blocked.append(entry)
            state["blocked_tasks"] = blocked
            self._ensure_archive_state(state)
            self._atomic_write(state)

    def memory_policy(self) -> dict[str, Any]:
        """Load and normalize rules.memory_policy."""
        rules_path = resolve_frame_file(self.project_dir, "rules.yaml")
        if not rules_path:
            return default_memory_policy()
        rules = load_yaml(str(rules_path))
        return normalize_memory_policy((rules.get("memory_policy") or {}))

    def compact(self, keep_recent: int = 5, dry_run: bool = False) -> dict:
        """Archive cold runs, sessions, and verifications into acts-history.yaml."""
        with self._lock(shared=False):
            state = load_yaml(str(self.path))
            policy = self.memory_policy()
            limits = hot_limits_from_policy(policy, keep_recent=keep_recent)
            return self._archive_cold_history(
                state,
                limits=limits,
                archive_mode="manual",
                dry_run=dry_run,
            )

    def archive_on_record(self) -> dict:
        """Archive cold history after a record when policy enables it."""
        with self._lock(shared=False):
            state = load_yaml(str(self.path))
            policy = self.memory_policy()
            archive_mode = policy.get("archive_mode", "manual")
            max_acts_bytes = int(policy.get("max_acts_bytes", 16000) or 16000)
            size_triggered = self.path.exists() and self.path.stat().st_size > max_acts_bytes
            if archive_mode != "on_record" and not size_triggered:
                self._ensure_archive_state(state, archive_mode=policy.get("archive_mode", "manual"))
                self._atomic_write(state)
                return {
                    "archive_mode": policy.get("archive_mode", "manual"),
                    "trigger": "manual",
                    "archived": {"runs": 0, "sessions": 0, "verifications": 0, "completed_tasks": 0, "decisions": 0},
                    "hot": {
                        "runs": len(state.get("runs", []) or []),
                        "sessions": len(state.get("sessions", []) or []),
                        "verifications": len(state.get("verifications", []) or []),
                        "completed_tasks": len(state.get("completed_tasks", []) or []),
                        "decisions": len(state.get("decisions", []) or []),
                    },
                    "dry_run": False,
                }
            limits = hot_limits_from_policy(policy)
            result = self._archive_cold_history(
                state,
                limits=limits,
                archive_mode=archive_mode,
                dry_run=False,
                max_bytes=max_acts_bytes if size_triggered else 0,
            )
            result["trigger"] = "size" if size_triggered and archive_mode != "on_record" else "on_record"
            return result

    def get_stats(self) -> dict:
        """Get state statistics for diagnostics."""
        state = self.read()
        runs = state.get("runs", [])
        completed = state.get("completed_tasks", [])
        blocked = state.get("blocked_tasks", [])
        decisions = state.get("decisions", [])
        unresolved = state.get("unresolved_dependencies", [])
        archive = archive_metadata(state)
        archive_counts = archive.get("archived_counts", {})
        file_size = self.path.stat().st_size
        yaml_text = yaml.dump(state, default_flow_style=False)

        return {
            "current_phase": state.get("current_phase", "unknown"),
            "active_task": state.get("active_task", {}).get("name", "none"),
            "completed_count": len(completed) if isinstance(completed, list) else 0,
            "blocked_count": len(blocked) if isinstance(blocked, list) else 0,
            "decision_count": len(decisions) if isinstance(decisions, list) else 0,
            "unresolved_count": len(unresolved) if isinstance(unresolved, list) else 0,
            "run_count": len(runs) if isinstance(runs, list) else 0,
            "session_count": len(state.get("sessions", []) or []),
            "verification_count": len(state.get("verifications", []) or []),
            "archived_run_count": int(archive_counts.get("runs", 0) or 0),
            "archived_session_count": int(archive_counts.get("sessions", 0) or 0),
            "archived_verification_count": int(archive_counts.get("verifications", 0) or 0),
            "archived_completed_count": int(archive_counts.get("completed_tasks", 0) or 0),
            "archived_decision_count": int(archive_counts.get("decisions", 0) or 0),
            "archive_mode": archive.get("archive_mode", "manual"),
            "archive_path": archive.get("path", ""),
            "file_size_bytes": file_size,
            "yaml_chars": len(yaml_text),
            "total_runs": (len(runs) if isinstance(runs, list) else 0) + int(archive_counts.get("runs", 0) or 0),
            "total_sessions": len(state.get("sessions", []) or []) + int(archive_counts.get("sessions", 0) or 0),
            "total_verifications": len(state.get("verifications", []) or []) + int(archive_counts.get("verifications", 0) or 0),
            "total_completed_tasks": max(
                len(completed) if isinstance(completed, list) else 0,
                int(archive_counts.get("completed_tasks", 0) or 0),
            ),
            "total_decisions": (len(decisions) if isinstance(decisions, list) else 0) + int(archive_counts.get("decisions", 0) or 0),
        }

    @contextmanager
    def _lock(self, shared: bool = True):
        """Advisory file lock using fcntl."""
        lock_dir = Path(tempfile.gettempdir()) / "haxaml-locks"
        lock_dir.mkdir(parents=True, exist_ok=True)
        lock_key = hashlib.sha256(str(self.path).encode("utf-8")).hexdigest()[:24]
        lock_path = lock_dir / f"{lock_key}.lock"
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
            suffix=".yaml",
            prefix=".state_",
            dir=str(dir_path),
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                yaml.dump(state, handle, default_flow_style=False, sort_keys=False)
            os.replace(tmp_path, str(self.path))
        except Exception:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise

    def _archive_cold_history(
        self,
        state: dict[str, Any],
        *,
        limits: dict[str, int],
        archive_mode: str,
        dry_run: bool,
        max_bytes: int = 0,
    ) -> dict[str, Any]:
        runs = list(state.get("runs", []) or [])
        sessions = list(state.get("sessions", []) or [])
        verifications = list(state.get("verifications", []) or [])
        completed_tasks = [
            self._normalize_completed_task(item)
            for item in (state.get("completed_tasks", []) or [])
            if isinstance(item, dict)
        ]
        decisions = [
            self._normalize_decision(item)
            for item in (state.get("decisions", []) or [])
            if isinstance(item, dict)
        ]

        if max_bytes > 0:
            limits = self._limits_under_size_budget(
                state,
                limits=limits,
                runs=runs,
                sessions=sessions,
                verifications=verifications,
                completed_tasks=completed_tasks,
                decisions=decisions,
                max_bytes=max_bytes,
            )

        cold_runs = runs[:-limits["runs"]] if limits["runs"] > 0 and len(runs) > limits["runs"] else (runs[:] if limits["runs"] == 0 else [])
        cold_sessions = (
            sessions[:-limits["sessions"]]
            if limits["sessions"] > 0 and len(sessions) > limits["sessions"]
            else (sessions[:] if limits["sessions"] == 0 else [])
        )
        cold_verifications = (
            verifications[:-limits["verifications"]]
            if limits["verifications"] > 0 and len(verifications) > limits["verifications"]
            else (verifications[:] if limits["verifications"] == 0 else [])
        )
        cold_completed = completed_tasks
        cold_decisions = (
            decisions[:-limits["decisions"]]
            if limits["decisions"] > 0 and len(decisions) > limits["decisions"]
            else (decisions[:] if limits["decisions"] == 0 else [])
        )

        archived_counts = {
            "runs": len(cold_runs),
            "sessions": len(cold_sessions),
            "verifications": len(cold_verifications),
            "completed_tasks": len(cold_completed),
            "decisions": len(cold_decisions),
        }
        hot_counts = {
            "runs": len(runs) - len(cold_runs),
            "sessions": len(sessions) - len(cold_sessions),
            "verifications": len(verifications) - len(cold_verifications),
            "completed_tasks": min(len(completed_tasks), limits["completed_tasks"]),
            "decisions": len(decisions) - len(cold_decisions),
        }

        self._ensure_archive_state(state, archive_mode=archive_mode, hot_limits=limits)
        archive = archive_metadata(state)
        prior_counts = archive.get("archived_counts", {})
        result = {
            "archive_mode": archive_mode,
            "archive_path": str(self.archive.path),
            "archived": archived_counts,
            "hot": hot_counts,
            "totals": {
                "runs": hot_counts["runs"] + int(prior_counts.get("runs", 0) or 0) + archived_counts["runs"],
                "sessions": hot_counts["sessions"] + int(prior_counts.get("sessions", 0) or 0) + archived_counts["sessions"],
                "verifications": hot_counts["verifications"] + int(prior_counts.get("verifications", 0) or 0) + archived_counts["verifications"],
                "completed_tasks": hot_counts["completed_tasks"] + int(prior_counts.get("completed_tasks", 0) or 0) + archived_counts["completed_tasks"],
                "decisions": hot_counts["decisions"] + int(prior_counts.get("decisions", 0) or 0) + archived_counts["decisions"],
            },
            "dry_run": dry_run,
            "hot_limits": dict(limits),
        }

        if dry_run:
            return result

        if any(archived_counts.values()):
            append_counts = self.archive.append(
                runs=cold_runs,
                sessions=cold_sessions,
                verifications=cold_verifications,
                completed_tasks=cold_completed,
                decisions=cold_decisions,
                archive_mode=archive_mode,
            )
        else:
            append_counts = {"runs": 0, "sessions": 0, "verifications": 0, "completed_tasks": 0, "decisions": 0}

        state["runs"] = runs[-limits["runs"] :] if limits["runs"] > 0 else []
        state["sessions"] = sessions[-limits["sessions"] :] if limits["sessions"] > 0 else []
        state["verifications"] = (
            verifications[-limits["verifications"] :]
            if limits["verifications"] > 0
            else []
        )
        state["completed_tasks"] = [
            completed_task_stub(item)
            for item in (completed_tasks[-limits["completed_tasks"] :] if limits["completed_tasks"] > 0 else [])
        ]
        state["decisions"] = decisions[-limits["decisions"] :] if limits["decisions"] > 0 else []
        self._ensure_archive_state(state, archive_mode=archive_mode, hot_limits=limits)
        archive_counts_total = self.archive.get_counts()
        state["archive"]["last_archived_at"] = now_iso()
        state["archive"]["archived_counts"] = archive_counts_total
        self._refresh_continuity_summary(state, max_acts_bytes=max_bytes or int(self.memory_policy().get("max_acts_bytes", 16000) or 16000))
        self._atomic_write(state)

        result["archived"] = append_counts
        result["hot"] = {
            "runs": len(state["runs"]),
            "sessions": len(state["sessions"]),
            "verifications": len(state["verifications"]),
            "completed_tasks": len(state["completed_tasks"]),
            "decisions": len(state["decisions"]),
        }
        result["totals"] = {
            "runs": len(state["runs"]) + archive_counts_total["runs"],
            "sessions": len(state["sessions"]) + archive_counts_total["sessions"],
            "verifications": len(state["verifications"]) + archive_counts_total["verifications"],
            "completed_tasks": max(len(state["completed_tasks"]), archive_counts_total["completed_tasks"]),
            "decisions": len(state["decisions"]) + archive_counts_total["decisions"],
        }
        return result

    def _normalize_completed_task(self, item: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(item)
        normalized["id"] = completed_task_id(normalized)
        return normalized

    def _normalize_decision(self, item: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(item)
        normalized["id"] = decision_id(normalized)
        return normalized

    def _limits_under_size_budget(
        self,
        state: dict[str, Any],
        *,
        limits: dict[str, int],
        runs: list[dict[str, Any]],
        sessions: list[dict[str, Any]],
        verifications: list[dict[str, Any]],
        completed_tasks: list[dict[str, Any]],
        decisions: list[dict[str, Any]],
        max_bytes: int,
    ) -> dict[str, int]:
        effective = {key: max(0, int(value or 0)) for key, value in limits.items()}
        kinds = ("runs", "sessions", "verifications", "completed_tasks", "decisions")

        def projected_size(candidate_limits: dict[str, int]) -> int:
            projected = dict(state)
            projected["runs"] = runs[-candidate_limits["runs"] :]
            projected["sessions"] = sessions[-candidate_limits["sessions"] :]
            projected["verifications"] = verifications[-candidate_limits["verifications"] :]
            projected["completed_tasks"] = [
                completed_task_stub(item)
                for item in completed_tasks[-candidate_limits["completed_tasks"] :]
            ]
            projected["decisions"] = [
                dict(item)
                for item in decisions[-candidate_limits["decisions"] :]
            ]
            self._refresh_continuity_summary(
                projected,
                max_acts_bytes=max_bytes,
            )
            return len(yaml.dump(projected, default_flow_style=False, sort_keys=False).encode("utf-8"))

        while projected_size(effective) > max_bytes:
            reducible = [kind for kind in kinds if effective.get(kind, 0) > 0]
            if not reducible:
                break
            largest = max(reducible, key=lambda kind: effective[kind])
            effective[largest] -= 1
        return effective

    def _ensure_archive_state(
        self,
        state: dict[str, Any],
        *,
        archive_mode: str | None = None,
        hot_limits: dict[str, int] | None = None,
    ) -> None:
        current = archive_metadata(state)
        if archive_mode is None:
            archive_mode = current.get("archive_mode", "manual")
        if hot_limits is None:
            hot_limits = hot_limits_from_policy(self.memory_policy())
        if not self.archive.exists():
            archived_counts = current.get("archived_counts", {})
        else:
            archived_counts = self.archive.get_counts()
        relative_archive_path = str(self.archive.path.relative_to(self.project_dir))
        self._refresh_continuity_summary(
            state,
            max_acts_bytes=int(self.memory_policy().get("max_acts_bytes", 16000) or 16000),
        )
        state["archive"] = {
            "path": relative_archive_path,
            "archive_mode": archive_mode,
            "last_archived_at": current.get("last_archived_at", ""),
            "archived_counts": archived_counts,
            "hot_limits": {
                "runs": int(hot_limits.get("runs", 0) or 0),
                "sessions": int(hot_limits.get("sessions", 0) or 0),
                "verifications": int(hot_limits.get("verifications", 0) or 0),
                "completed_tasks": int(hot_limits.get("completed_tasks", 0) or 0),
                "decisions": int(hot_limits.get("decisions", 0) or 0),
            },
        }

    def _refresh_continuity_summary(self, state: dict[str, Any], *, max_acts_bytes: int) -> None:
        runs = [item for item in (state.get("runs", []) or []) if isinstance(item, dict)]
        verifications = [item for item in (state.get("verifications", []) or []) if isinstance(item, dict)]
        decisions = [item for item in (state.get("decisions", []) or []) if isinstance(item, dict)]
        blocked_tasks = [item for item in (state.get("blocked_tasks", []) or []) if isinstance(item, dict)]
        unresolved = [
            item
            for item in (state.get("unresolved_dependencies", []) or [])
            if isinstance(item, dict)
        ]
        failures: list[dict[str, Any]] = []
        for run in reversed(runs):
            result = str(run.get("result", "")).strip().lower()
            if result not in {"failed", "partial"}:
                continue
            failures.append(
                {
                    "kind": "run",
                    "id": str(run.get("id", "")).strip(),
                    "task": str(run.get("task", "")).strip(),
                    "result": result,
                    "summary": str(run.get("risks") or run.get("changes") or run.get("decisions") or "").strip(),
                    "timestamp": str(run.get("timestamp", "")).strip(),
                }
            )
            if len(failures) >= 4:
                break
        for verification in reversed(verifications):
            verdict = str(verification.get("verdict", "")).strip().lower()
            if verdict not in {"fail", "needs_clarification", "pass_with_risks"}:
                continue
            failures.append(
                {
                    "kind": "verification",
                    "id": str(verification.get("id", "")).strip(),
                    "task": str(verification.get("task", "")).strip(),
                    "result": verdict,
                    "summary": str(verification.get("summary", "")).strip(),
                    "timestamp": str(verification.get("timestamp", "")).strip(),
                }
            )
            if len(failures) >= 4:
                break
        blockers: list[dict[str, Any]] = []
        for item in blocked_tasks[-4:]:
            blockers.append(
                {
                    "kind": "blocked_task",
                    "name": str(item.get("name", "")).strip(),
                    "reason": str(item.get("reason", "")).strip(),
                    "depends_on": str(item.get("depends_on", "")).strip(),
                }
            )
        for item in unresolved:
            if not bool(item.get("blocking")):
                continue
            blockers.append(
                {
                    "kind": "unresolved_dependency",
                    "name": str(item.get("item", "")).strip(),
                    "reason": str(item.get("reason", "") or item.get("owner", "")).strip(),
                    "owner": str(item.get("owner", "")).strip(),
                }
            )
            if len(blockers) >= 6:
                break
        decision_summary = []
        for item in decisions[-4:]:
            decision_summary.append(
                {
                    "decision": str(item.get("decision", "")).strip(),
                    "reasoning": str(item.get("reasoning", "")).strip(),
                    "date": str(item.get("date", "")).strip(),
                }
            )
        hot_bytes = len(yaml.dump(state, default_flow_style=False, sort_keys=False).encode("utf-8"))
        pressure_ratio = (hot_bytes / max_acts_bytes) if max_acts_bytes > 0 else 0.0
        if pressure_ratio >= 1:
            pressure = "over_budget"
        elif pressure_ratio >= 0.85:
            pressure = "tight"
        else:
            pressure = "healthy"
        state["continuity"] = {
            "recent_decisions": decision_summary,
            "current_blockers": blockers,
            "recent_failures": failures[:4],
            "context_pressure": {
                "hot_bytes": hot_bytes,
                "max_hot_bytes": max_acts_bytes,
                "status": pressure,
            },
        }

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
