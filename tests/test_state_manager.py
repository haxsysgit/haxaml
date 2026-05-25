"""Tests for acts evolution system (FRAME model)."""

import os
import threading

import pytest
import yaml

from haxaml.acts_archive import ActsArchive
from haxaml.state_manager import StateManager, StateError


def _frame() -> dict:
    return {
        "file": "acts",
        "schema_version": "0.8.0",
        "role": "checked_activity_record",
        "status": "draft",
        "last_reviewed": None,
        "updated_by": None,
        "update_reason": None,
    }


def _make_state(tmp_path, data=None):
    """Create strict acts frontmatter plus Haxaml runtime state."""
    if data is None:
        data = {
            "frame": _frame(),
            "current_phase": "Phase 1",
            "active_task": {"name": "test task", "description": "testing"},
            "completed_tasks": [],
            "blocked_tasks": [],
            "decisions": [],
            "unresolved_dependencies": [],
            "runs": [],
            "sessions": [],
            "verifications": [],
            "archive": {
                "path": str(tmp_path / ".haxaml" / "archive" / "acts-history.yaml"),
                "archive_mode": "manual",
                "last_archived_at": "",
                "archived_counts": {"runs": 0, "sessions": 0, "verifications": 0},
                "hot_limits": {"runs": 5, "sessions": 5, "verifications": 5},
            },
        }
    elif isinstance(data, dict) and "frame" not in data:
        data = {"frame": _frame(), **data}
    path_obj = tmp_path / "acts.yaml"
    runtime_path = tmp_path / "runtime" / "acts-state.yaml"
    runtime_path.parent.mkdir(parents=True, exist_ok=True)
    with open(path_obj, "w") as f:
        yaml.dump({"frame": data["frame"]}, f, default_flow_style=False, sort_keys=False)
    runtime = {key: value for key, value in data.items() if key != "frame"}
    with open(runtime_path, "w") as f:
        yaml.dump(runtime, f, default_flow_style=False, sort_keys=False)
    path = str(path_obj)
    return path


class TestStateReadWrite:

    def test_read_state(self, tmp_path):
        path = _make_state(tmp_path)
        sm = StateManager(path)
        state = sm.read()
        assert state["current_phase"] == "Phase 1"
        assert state["active_task"]["name"] == "test task"
        assert not (tmp_path / "acts.lock").exists()

    def test_write_state(self, tmp_path):
        path = _make_state(tmp_path)
        sm = StateManager(path)
        state = sm.read()
        state["current_phase"] = "Phase 2"
        sm.write(state)

        reloaded = sm.read()
        assert reloaded["current_phase"] == "Phase 2"

    def test_write_invalid_state_rejected(self, tmp_path):
        path = _make_state(tmp_path)
        sm = StateManager(path)
        with pytest.raises(StateError, match="Invalid state"):
            sm.write({"invalid": "data"})

    def test_atomic_write_preserves_on_failure(self, tmp_path):
        path = _make_state(tmp_path)
        sm = StateManager(path)
        original = sm.read()

        with pytest.raises(StateError):
            sm.write({"missing": "required fields"})

        preserved = sm.read()
        assert preserved["current_phase"] == original["current_phase"]

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(StateError, match="not found"):
            StateManager(str(tmp_path / "nonexistent.yaml"))


class TestRunRecording:

    def test_record_run(self, tmp_path):
        path = _make_state(tmp_path)
        sm = StateManager(path)
        run_id = sm.record_run(task="build feature", result="success",
                               changes="added module")
        assert run_id.startswith("run-")

        state = sm.read()
        assert len(state["runs"]) == 1
        assert state["runs"][0]["task"] == "build feature"
        assert state["runs"][0]["result"] == "success"
        assert not (tmp_path / "acts.lock").exists()

    def test_record_multiple_runs(self, tmp_path):
        path = _make_state(tmp_path)
        sm = StateManager(path)
        for i in range(5):
            sm.record_run(task=f"task {i}", result="success")

        state = sm.read()
        assert len(state["runs"]) == 5

    def test_invalid_result_rejected(self, tmp_path):
        path = _make_state(tmp_path)
        sm = StateManager(path)
        with pytest.raises(StateError, match="Invalid run result"):
            sm.record_run(task="test", result="invalid")

    def test_record_completed_run_is_atomic_for_run_and_task_close(self, tmp_path):
        path = _make_state(tmp_path)
        sm = StateManager(path)

        run_id = sm.record_completed_run(
            task="build feature",
            result="success",
            changes="added module",
            summary="done",
        )

        assert run_id.startswith("run-")
        state = sm.read()
        assert len(state["runs"]) == 1
        assert len(state["completed_tasks"]) == 1
        assert state["active_task"]["name"] == "none"


class TestTaskManagement:

    def test_complete_task(self, tmp_path):
        path = _make_state(tmp_path)
        sm = StateManager(path)
        sm.complete_task(result="success", summary="Done testing")

        state = sm.read()
        assert state["active_task"]["name"] == "none"
        assert len(state["completed_tasks"]) == 1
        assert state["completed_tasks"][0]["name"] == "test task"
        assert state["completed_tasks"][0]["result"] == "success"

    def test_complete_no_active_task_raises(self, tmp_path):
        data = {
            "current_phase": "Phase 1",
            "active_task": {"name": "none"},
            "completed_tasks": [],
            "runs": [],
        }
        path = _make_state(tmp_path, data)
        sm = StateManager(path)
        with pytest.raises(StateError, match="No active task"):
            sm.complete_task()

    def test_set_active_task(self, tmp_path):
        path = _make_state(tmp_path)
        sm = StateManager(path)
        sm.set_active_task("new task", description="something new")

        state = sm.read()
        assert state["active_task"]["name"] == "new task"
        assert state["active_task"]["description"] == "something new"

    def test_add_decision(self, tmp_path):
        path = _make_state(tmp_path)
        sm = StateManager(path)
        sm.add_decision("Use postgres", "Better scaling")

        state = sm.read()
        assert len(state["decisions"]) == 1
        assert state["decisions"][0]["decision"] == "Use postgres"

    def test_add_blocker(self, tmp_path):
        path = _make_state(tmp_path)
        sm = StateManager(path)
        sm.add_blocker("API integration", "Waiting for keys", depends_on="auth")

        state = sm.read()
        assert len(state["blocked_tasks"]) == 1
        assert state["blocked_tasks"][0]["depends_on"] == "auth"


class TestCompaction:

    def test_compact_no_op_when_few_runs(self, tmp_path):
        path = _make_state(tmp_path)
        sm = StateManager(path)
        for i in range(3):
            sm.record_run(task=f"task {i}", result="success")

        result = sm.compact(keep_recent=5)
        assert result["archived"]["runs"] == 0
        assert result["hot"]["runs"] == 3

    def test_compact_archives_old_runs(self, tmp_path):
        path = _make_state(tmp_path)
        sm = StateManager(path)
        for i in range(12):
            sm.record_run(task=f"task {i}", result="success",
                          changes=f"change {i}",
                          decisions=f"decision {i}" if i % 3 == 0 else "")

        result = sm.compact(keep_recent=5)
        assert result["archived"]["runs"] == 7
        assert result["hot"]["runs"] == 5

        state = sm.read()
        assert len(state["runs"]) == 5
        assert state["archive"]["archived_counts"]["runs"] == 7
        assert ActsArchive(tmp_path).get_counts()["runs"] == 7

    def test_compact_accumulates(self, tmp_path):
        path = _make_state(tmp_path)
        sm = StateManager(path)

        for i in range(10):
            sm.record_run(task=f"batch1-{i}", result="success")
        sm.compact(keep_recent=3)

        for i in range(10):
            sm.record_run(task=f"batch2-{i}", result="success")
        result = sm.compact(keep_recent=3)

        state = sm.read()
        assert state["archive"]["archived_counts"]["runs"] == 7 + 10
        assert len(state["runs"]) == 3
        assert result["archived"]["runs"] == 10

    def test_compact_preserves_recent_runs(self, tmp_path):
        path = _make_state(tmp_path)
        sm = StateManager(path)
        for i in range(10):
            sm.record_run(task=f"task {i}", result="success")

        sm.compact(keep_recent=3)
        state = sm.read()
        tasks = [r["task"] for r in state["runs"]]
        assert tasks == ["task 7", "task 8", "task 9"]

    def test_compact_dry_run_does_not_mutate_state(self, tmp_path):
        path = _make_state(tmp_path)
        sm = StateManager(path)
        for i in range(8):
            sm.record_run(task=f"task {i}", result="success")

        before = sm.read()
        result = sm.compact(keep_recent=3, dry_run=True)
        after = sm.read()

        assert result["dry_run"] is True
        assert result["archived"]["runs"] == 5
        assert len(after["runs"]) == len(before["runs"]) == 8
        assert after.get("archive", {}).get("archived_counts", {}).get("runs", 0) == 0

    def test_archive_on_record_can_trigger_from_size_pressure(self, tmp_path):
        data = {
            "current_phase": "Phase 1",
            "active_task": {"name": "test task", "description": "testing"},
            "completed_tasks": [],
            "blocked_tasks": [],
            "decisions": [],
            "unresolved_dependencies": [],
            "runs": [{"id": f"run-{i}", "task": f"task {i}", "result": "success", "changes": "x" * 500} for i in range(8)],
            "sessions": [],
            "verifications": [],
            "archive": {
                "path": str(tmp_path / ".haxaml" / "archive" / "acts-history.yaml"),
                "archive_mode": "manual",
                "last_archived_at": "",
                "archived_counts": {"runs": 0, "sessions": 0, "verifications": 0},
                "hot_limits": {"runs": 3, "sessions": 3, "verifications": 3},
            },
        }
        path = _make_state(tmp_path, data)
        rules_dir = tmp_path / ".haxaml"
        rules_dir.mkdir(exist_ok=True)
        (rules_dir / "rules.yaml").write_text(
            "memory_policy:\n  archive_mode: manual\n  max_hot_runs: 3\n  max_hot_sessions: 3\n  max_hot_verifications: 3\n  max_acts_bytes: 512\n",
            encoding="utf-8",
        )
        sm = StateManager(path)

        result = sm.archive_on_record()

        assert result["trigger"] == "size"
        assert result["archived"]["runs"] >= 5
        assert len(sm.read()["runs"]) <= 3

    def test_compact_preserves_full_archived_record(self, tmp_path):
        path = _make_state(tmp_path)
        sm = StateManager(path)
        sm.record_run(
            task="seed archive",
            result="success",
            changes="Updated docs and tests",
            decisions="Kept hot state lean",
            risks="Need another docs pass",
            file_refs=["docs/lifecycle.md", "tests/test_state_manager.py"],
            module_refs=["docs"],
            verification_id="verify-abc123",
            keywords=["archive", "docs"],
        )
        for i in range(6):
            sm.record_run(task=f"task {i}", result="success")

        sm.compact(keep_recent=5)
        archive = ActsArchive(tmp_path)
        runs = archive.read()["history"]["runs"]
        record = next(item for item in runs if item["task"] == "seed archive")

        assert record["changes"] == "Updated docs and tests"
        assert record["decisions"] == "Kept hot state lean"
        assert record["verification_id"] == "verify-abc123"
        assert "docs/lifecycle.md" in record["file_refs"]

    def test_completed_tasks_are_capped_in_hot_acts_and_archived(self, tmp_path):
        path = _make_state(tmp_path)
        rules_dir = tmp_path / ".haxaml"
        rules_dir.mkdir(exist_ok=True)
        (rules_dir / "rules.yaml").write_text(
            "memory_policy:\n"
            "  archive_mode: on_record\n"
            "  max_hot_runs: 5\n"
            "  max_hot_sessions: 5\n"
            "  max_hot_verifications: 5\n"
            "  max_hot_completed_tasks: 3\n"
            "  max_acts_bytes: 16000\n",
            encoding="utf-8",
        )
        sm = StateManager(path)

        for index in range(8):
            sm.set_active_task(f"task {index}", description=f"summary {index}")
            sm.record_completed_run(
                task=f"task {index}",
                result="success",
                changes=f"completed task {index}",
                summary=f"full completed task summary {index}",
            )
            sm.archive_on_record()

        state = sm.read()
        assert len(state["completed_tasks"]) == 3
        assert all(item.get("archived") is True for item in state["completed_tasks"])
        assert state["archive"]["archived_counts"]["completed_tasks"] == 8

    def test_archived_completed_tasks_can_be_loaded_by_id(self, tmp_path):
        path = _make_state(tmp_path)
        sm = StateManager(path)
        sm.set_active_task("archive completed task", description="archive me")
        sm.record_completed_run(
            task="archive completed task",
            result="success",
            changes="done",
            summary="needle completed task summary",
        )
        sm.compact(keep_recent=1)

        archive = ActsArchive(tmp_path)
        entries = [item for item in archive.index_entries() if item["kind"] == "completed_task"]
        assert entries
        detail = archive.load_record_details("completed_task", entries[0]["id"])
        assert detail is not None
        assert detail["summary"] == "needle completed task summary"

    def test_size_pressure_reduces_hot_records_below_count_limits(self, tmp_path):
        data = {
            "current_phase": "Phase 1",
            "active_task": {"name": "test task", "description": "testing"},
            "completed_tasks": [],
            "blocked_tasks": [],
            "decisions": [],
            "unresolved_dependencies": [],
            "runs": [
                {"id": f"run-{i}", "task": f"task {i}", "result": "success", "changes": "x" * 1200}
                for i in range(6)
            ],
            "sessions": [],
            "verifications": [],
            "archive": {
                "path": str(tmp_path / ".haxaml" / "archive" / "acts-history.yaml"),
                "archive_mode": "manual",
                "last_archived_at": "",
                "archived_counts": {"runs": 0, "sessions": 0, "verifications": 0, "completed_tasks": 0},
                "hot_limits": {"runs": 5, "sessions": 5, "verifications": 5, "completed_tasks": 5},
            },
        }
        path = _make_state(tmp_path, data)
        rules_dir = tmp_path / ".haxaml"
        rules_dir.mkdir(exist_ok=True)
        (rules_dir / "rules.yaml").write_text(
            "memory_policy:\n"
            "  archive_mode: manual\n"
            "  max_hot_runs: 5\n"
            "  max_hot_sessions: 5\n"
            "  max_hot_verifications: 5\n"
            "  max_hot_completed_tasks: 5\n"
            "  max_acts_bytes: 1024\n",
            encoding="utf-8",
        )
        sm = StateManager(path)

        result = sm.archive_on_record()

        assert result["trigger"] == "size"
        assert len(sm.read()["runs"]) < 5

    def test_decisions_are_bounded_in_hot_state_and_archived(self, tmp_path):
        path = _make_state(tmp_path)
        rules_dir = tmp_path / ".haxaml"
        rules_dir.mkdir(exist_ok=True)
        (rules_dir / "rules.yaml").write_text(
            "memory_policy:\n"
            "  archive_mode: on_record\n"
            "  max_hot_runs: 5\n"
            "  max_hot_sessions: 5\n"
            "  max_hot_verifications: 5\n"
            "  max_hot_completed_tasks: 5\n"
            "  max_hot_decisions: 3\n"
            "  max_acts_bytes: 16000\n",
            encoding="utf-8",
        )
        sm = StateManager(path)

        for index in range(6):
            sm.add_decision(f"decision {index}", f"reason {index}")
        result = sm.archive_on_record()

        state = sm.read()
        assert result["archived"]["decisions"] == 3
        assert len(state["decisions"]) == 3
        assert [item["decision"] for item in state["decisions"]] == ["decision 3", "decision 4", "decision 5"]
        assert state["archive"]["archived_counts"]["decisions"] == 3

    def test_continuity_summary_keeps_blockers_and_failures_hot(self, tmp_path):
        data = {
            "current_phase": "Phase 1",
            "active_task": {"name": "test task", "description": "testing"},
            "completed_tasks": [],
            "blocked_tasks": [{"name": "API key", "reason": "waiting on owner"}],
            "decisions": [{"decision": "keep hot state lean", "reasoning": "token pressure", "date": "2026-01-01T00:00:00+00:00"}],
            "unresolved_dependencies": [{"item": "Sandbox key", "blocking": True, "owner": "owner"}],
            "runs": [{"id": "run-1", "task": "failed task", "result": "failed", "risks": "missing secret", "timestamp": "2026-01-01T00:00:00+00:00"}],
            "sessions": [],
            "verifications": [],
        }
        path = _make_state(tmp_path, data)
        sm = StateManager(path)

        sm.archive_on_record()
        continuity = sm.read()["continuity"]

        assert continuity["recent_decisions"]
        assert continuity["current_blockers"]
        assert continuity["recent_failures"]
        assert continuity["context_pressure"]["status"] in {"healthy", "tight", "over_budget"}

    def test_legacy_archive_file_is_read_and_migrated_on_compaction(self, tmp_path):
        path = _make_state(tmp_path)
        sm = StateManager(path)
        legacy_path = tmp_path / ".haxaml" / "acts-history.yaml"
        legacy_path.parent.mkdir(parents=True, exist_ok=True)
        legacy_path.write_text(
            yaml.dump(
                {
                    "metadata": {
                        "version": "0.6.7",
                        "managed_by": "haxaml",
                        "archive_mode": "manual",
                        "counts": {"runs": 1, "sessions": 0, "verifications": 0, "completed_tasks": 0, "decisions": 0},
                    },
                    "index": [{"kind": "run", "id": "run-old", "task": "old task", "status_or_result": "success", "summary": "legacy"}],
                    "history": {"runs": [{"id": "run-old", "task": "old task", "result": "success"}], "sessions": [], "verifications": [], "completed_tasks": [], "decisions": []},
                },
                default_flow_style=False,
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        for index in range(8):
            sm.record_run(task=f"task {index}", result="success")

        result = sm.compact(keep_recent=2)

        assert result["archived"]["runs"] >= 6
        assert (tmp_path / ".haxaml" / "archive" / "acts-history.yaml").exists()
        assert ActsArchive(tmp_path).has_record("run-old") is True


class TestStats:

    def test_get_stats(self, tmp_path):
        path = _make_state(tmp_path)
        sm = StateManager(path)
        sm.record_run(task="t1", result="success")
        sm.add_decision("d1", "r1")

        stats = sm.get_stats()
        assert stats["current_phase"] == "Phase 1"
        assert stats["run_count"] == 1
        assert stats["decision_count"] == 1
        assert stats["file_size_bytes"] > 0


class TestConcurrency:

    def test_concurrent_run_recording(self, tmp_path):
        """Verify concurrent writes don't corrupt state."""
        path = _make_state(tmp_path)
        errors = []

        def record_runs(thread_id):
            try:
                sm = StateManager(path)
                for i in range(5):
                    sm.record_run(task=f"thread-{thread_id}-task-{i}",
                                  result="success")
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=record_runs, args=(t,)) for t in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Errors during concurrent access: {errors}"

        sm = StateManager(path)
        state = sm.read()
        assert len(state["runs"]) == 20
