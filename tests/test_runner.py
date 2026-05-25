"""Tests for the execution loop runner."""

import os
import shutil

import pytest
import yaml

from haxaml.acts_archive import ActsArchive
from haxaml.runner import ExecutionRunner, RunResult, PreflightResult
from haxaml.state_manager import StateManager


def _frame(file: str, role: str) -> dict:
    return {
        "file": file,
        "schema_version": "0.8.0",
        "role": role,
        "status": "draft",
        "last_reviewed": None,
        "updated_by": None,
        "update_reason": None,
    }


def _make_project(tmp_path, brain=None, state=None, instructions=None):
    """Create a minimal Haxaml project in tmp_path."""
    if brain is None:
        brain = {
            "identity": {"name": "test-project", "version": "0.1.0",
                         "description": "Test project"},
            "goal": {"purpose": "Testing the execution runner",
                     "scope": "Unit tests",
                     "out_of_scope": []},
            "stack": {"language": "python"},
            "architecture": {"pattern": "layered",
                             "reasoning": "Test simplicity"},
            "database": {"type": "none", "connection": "none"},
            "constraints": ["No guessing"],
            "success_criteria": ["Tests pass"],
            "tools": {"testing": "pytest"},
            "services": [{"name": "api", "purpose": "Test surface"}],
            "roles": [{"name": "builder", "responsibility": "build"}],
            "features": [{"name": "core", "status": "planned"}],
        }
    if isinstance(brain, dict) and "frame" not in brain:
        brain = {"frame": _frame("facts", "stable_project_truth")}

    if state is None:
        state = {
            "frame": _frame("acts", "checked_activity_record"),
            "current_phase": "Phase 1",
            "active_task": {"name": "initial task"},
            "completed_tasks": [],
            "blocked_tasks": [],
            "decisions": [],
            "unresolved_dependencies": [],
            "runs": [],
            "sessions": [],
            "verifications": [],
            "archive": {
                "path": ".haxaml/archive/acts-history.yaml",
                "archive_mode": "manual",
                "last_archived_at": "",
                "archived_counts": {"runs": 0, "sessions": 0, "verifications": 0},
                "hot_limits": {"runs": 5, "sessions": 5, "verifications": 5},
            },
        }
    elif isinstance(state, dict) and "frame" not in state:
        state = {"frame": _frame("acts", "checked_activity_record"), **state}

    rules = {"frame": _frame("rules", "project_constraints")}
    expect = {"frame": _frame("expect", "planned_direction")}

    haxaml_dir = tmp_path / ".haxaml"
    haxaml_dir.mkdir(exist_ok=True)

    facts_path = haxaml_dir / "facts.yaml"
    with open(facts_path, "w") as f:
        yaml.dump(brain, f, default_flow_style=False, sort_keys=False)

    acts_path = haxaml_dir / "acts.yaml"
    with open(acts_path, "w") as f:
        yaml.dump({"frame": state["frame"]}, f, default_flow_style=False, sort_keys=False)
    runtime_path = haxaml_dir / "runtime" / "acts-state.yaml"
    runtime_path.parent.mkdir(parents=True, exist_ok=True)
    with open(runtime_path, "w") as f:
        yaml.dump({key: value for key, value in state.items() if key != "frame"}, f, default_flow_style=False, sort_keys=False)

    rules_path = haxaml_dir / "rules.yaml"
    with open(rules_path, "w") as f:
        yaml.dump(rules, f, default_flow_style=False, sort_keys=False)

    expect_path = haxaml_dir / "expect.yaml"
    with open(expect_path, "w") as f:
        yaml.dump(expect, f, default_flow_style=False, sort_keys=False)

    if instructions is not None:
        inst_path = tmp_path / "instruction.md"
        inst_path.write_text(instructions)

    return str(tmp_path)


class TestPreflight:

    def test_valid_project_passes(self, tmp_path):
        project = _make_project(tmp_path)
        runner = ExecutionRunner(project)
        result = runner.preflight()
        assert result.ready is True
        assert result.facts_valid is True
        assert result.acts_valid is True

    def test_invalid_brain_fails(self, tmp_path):
        project = _make_project(
            tmp_path,
            brain={"frame": {**_frame("facts", "stable_project_truth"), "file": "rules"}},
        )
        runner = ExecutionRunner(project)
        result = runner.preflight()
        assert result.ready is False
        assert result.facts_valid is False

    def test_missing_brain_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            ExecutionRunner(str(tmp_path))

    def test_blocking_unresolved_fails(self, tmp_path):
        brain = {"frame": _frame("facts", "stable_project_truth"), "unresolved": [{"item": "DB URI", "reason": "missing", "blocking": True}]}
        project = _make_project(tmp_path, brain=brain)
        runner = ExecutionRunner(project)
        result = runner.preflight()
        assert result.ready is False
        assert any("unresolved" in e for e in result.errors)

    def test_missing_map_blocks_when_complexity_requires_it(self, tmp_path):
        project = _make_project(tmp_path)
        rules = {
            "frame": _frame("rules", "project_constraints"),
            "boundaries": {
                "modules": {
                    "api": {"touches": ["auth", "db"]},
                    "auth": {"touches": ["db"]},
                    "db": {"touches": []},
                }
            }
        }
        expect = {
            "frame": _frame("expect", "planned_direction"),
            "planning": {
                "estimated_runs": 6,
                "project_size": "medium",
                "map_required": False,
            },
            "map_policy": {
                "module_threshold": 3,
            },
            "runbook": [],
        }
        with open(tmp_path / ".haxaml" / "rules.yaml", "w") as f:
            yaml.dump(rules, f, default_flow_style=False, sort_keys=False)
        with open(tmp_path / ".haxaml" / "expect.yaml", "w") as f:
            yaml.dump(expect, f, default_flow_style=False, sort_keys=False)

        runner = ExecutionRunner(project)
        result = runner.preflight()
        assert result.ready is False
        assert any("map.yaml is required" in e for e in result.errors)


class TestExecutionLoop:

    def test_start_run(self, tmp_path):
        project = _make_project(tmp_path)
        runner = ExecutionRunner(project)
        result = runner.start_run(task="implement feature X")
        assert result.result == "pending"

        sm = StateManager(str(tmp_path / ".haxaml" / "acts.yaml"))
        state = sm.read()
        assert state["active_task"]["name"] == "implement feature X"

    def test_finish_run(self, tmp_path):
        project = _make_project(tmp_path)
        runner = ExecutionRunner(project)

        runner.start_run(task="implement feature X")
        result = runner.finish_run(
            task="implement feature X",
            result="success",
            changes="Added module X",
            decisions="Used approach A",
        )

        assert result.run_id.startswith("run-")
        assert result.result == "success"
        assert result.token_count > 0

        sm = StateManager(str(tmp_path / ".haxaml" / "acts.yaml"))
        state = sm.read()
        assert len(state["runs"]) == 1
        assert len(state["completed_tasks"]) == 1

    def test_full_cycle(self, tmp_path):
        """Test complete FRAME → run → acts → compact cycle."""
        project = _make_project(tmp_path)
        runner = ExecutionRunner(project)

        for i in range(12):
            runner.start_run(task=f"task {i}", description=f"Build feature {i}")
            runner.finish_run(
                task=f"task {i}", result="success",
                changes=f"Implemented feature {i}",
                auto_compact=True, compact_threshold=10,
            )

        sm = StateManager(str(tmp_path / ".haxaml" / "acts.yaml"))
        state = sm.read()
        assert len(state["completed_tasks"]) == 5
        assert all(item.get("archived") is True for item in state["completed_tasks"])
        assert state["archive"]["archived_counts"]["runs"] > 0
        assert state["archive"]["archived_counts"]["completed_tasks"] == 12
        assert ActsArchive(tmp_path).get_counts()["completed_tasks"] == 12

    def test_failed_preflight_blocks_run(self, tmp_path):
        project = _make_project(
            tmp_path,
            brain={"frame": {**_frame("facts", "stable_project_truth"), "file": "rules"}},
        )
        runner = ExecutionRunner(project)
        result = runner.start_run(task="should fail")
        assert result.result == "failed"
        assert len(result.errors) > 0


class TestProjectHealth:

    def test_health_report(self, tmp_path):
        project = _make_project(tmp_path)
        runner = ExecutionRunner(project)
        health = runner.get_project_health()

        assert health["project"] == "unknown"
        assert health["ready"] is True
        assert health["facts_valid"] is True
        assert health["context_tokens"] > 0

    def test_health_includes_state_stats(self, tmp_path):
        project = _make_project(tmp_path)
        runner = ExecutionRunner(project)

        runner.start_run(task="t1")
        runner.finish_run(task="t1", result="success")

        health = runner.get_project_health()
        assert health["completed_tasks"] == 1
        assert health["total_runs"] >= 1


class TestContextPreparation:

    def test_prepare_context_structure(self, tmp_path):
        project = _make_project(tmp_path)
        runner = ExecutionRunner(project)
        ctx = runner.prepare_context(task="Build auth module")

        assert ctx["facts"]["project"] == "unknown"
        assert ctx["task"] == "Build auth module"
        assert "state" in ctx
        assert ctx["_meta"]["token_count"] > 0

    def test_context_without_state(self, tmp_path):
        project = _make_project(tmp_path)
        runner = ExecutionRunner(project)
        ctx = runner.prepare_context(task="test", include_state=False)
        assert "state" not in ctx
