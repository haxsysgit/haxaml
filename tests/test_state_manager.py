"""Tests for acts evolution system (FRAME model)."""

import os
import threading

import pytest
import yaml

from haxaml.state_manager import StateManager, StateError


def _make_state(tmp_path, data=None):
    """Create an acts.yaml in tmp_path and return its path."""
    if data is None:
        data = {
            "current_phase": "Phase 1",
            "active_task": {"name": "test task", "description": "testing"},
            "completed_tasks": [],
            "blocked_tasks": [],
            "decisions": [],
            "unresolved_dependencies": [],
            "runs": [],
            "compaction": {
                "last_compacted": None,
                "total_runs_compacted": 0,
                "summary": "No runs yet.",
            },
        }
    path = str(tmp_path / "acts.yaml")
    with open(path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)
    return path


class TestStateReadWrite:

    def test_read_state(self, tmp_path):
        path = _make_state(tmp_path)
        sm = StateManager(path)
        state = sm.read()
        assert state["current_phase"] == "Phase 1"
        assert state["active_task"]["name"] == "test task"

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
        assert result["compacted"] == 0
        assert result["kept"] == 3

    def test_compact_archives_old_runs(self, tmp_path):
        path = _make_state(tmp_path)
        sm = StateManager(path)
        for i in range(12):
            sm.record_run(task=f"task {i}", result="success",
                          changes=f"change {i}",
                          decisions=f"decision {i}" if i % 3 == 0 else "")

        result = sm.compact(keep_recent=5)
        assert result["compacted"] == 7
        assert result["kept"] == 5

        state = sm.read()
        assert len(state["runs"]) == 5
        assert state["compaction"]["total_runs_compacted"] == 7
        assert "Compacted 7 runs" in state["compaction"]["summary"]

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
        assert state["compaction"]["total_runs_compacted"] == 7 + 10
        assert len(state["runs"]) == 3

    def test_compact_preserves_recent_runs(self, tmp_path):
        path = _make_state(tmp_path)
        sm = StateManager(path)
        for i in range(10):
            sm.record_run(task=f"task {i}", result="success")

        sm.compact(keep_recent=3)
        state = sm.read()
        tasks = [r["task"] for r in state["runs"]]
        assert tasks == ["task 7", "task 8", "task 9"]


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
