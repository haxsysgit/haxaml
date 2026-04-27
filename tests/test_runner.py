"""Tests for the execution loop runner."""

import os
import shutil

import pytest
import yaml

from haxaml.runner import ExecutionRunner, RunResult, PreflightResult
from haxaml.state_manager import StateManager


def _make_project(tmp_path, brain=None, state=None, instructions=None):
    """Create a minimal Haxaml project in tmp_path."""
    if brain is None:
        brain = {
            "identity": {"name": "test-project", "version": "0.1.0",
                         "description": "Test project"},
            "goal": {"purpose": "Testing the execution runner",
                     "scope": "Unit tests"},
            "stack": {"language": "python"},
            "architecture": {"pattern": "layered",
                             "reasoning": "Test simplicity"},
            "database": {"type": "none", "connection": "none"},
            "constraints": ["No guessing"],
            "success_criteria": ["Tests pass"],
            "tools": {"testing": "pytest"},
            "services": [],
            "roles": [{"name": "builder", "responsibility": "build"}],
            "features": [{"name": "core", "status": "planned"}],
        }

    if state is None:
        state = {
            "current_phase": "Phase 1",
            "active_task": {"name": "initial task"},
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

    facts_path = tmp_path / "facts.yaml"
    with open(facts_path, "w") as f:
        yaml.dump(brain, f, default_flow_style=False, sort_keys=False)

    acts_path = tmp_path / "acts.yaml"
    with open(acts_path, "w") as f:
        yaml.dump(state, f, default_flow_style=False, sort_keys=False)

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
        project = _make_project(tmp_path, brain={"invalid": "brain"})
        runner = ExecutionRunner(project)
        result = runner.preflight()
        assert result.ready is False
        assert result.facts_valid is False

    def test_missing_brain_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            ExecutionRunner(str(tmp_path))

    def test_blocking_unresolved_fails(self, tmp_path):
        brain = {
            "identity": {"name": "test", "version": "0.1.0",
                         "description": "Test"},
            "goal": {"purpose": "Testing blocking items",
                     "scope": "test"},
            "stack": {"language": "python"},
            "architecture": {"pattern": "layered", "reasoning": "test"},
            "database": {"type": "none", "connection": "none"},
            "constraints": ["rule"],
            "success_criteria": ["works"],
            "tools": {"testing": "pytest"},
            "services": [],
            "roles": [{"name": "dev", "responsibility": "build"}],
            "features": [],
            "unresolved": [
                {"item": "DB URI", "reason": "missing", "blocking": True}
            ],
        }
        project = _make_project(tmp_path, brain=brain)
        runner = ExecutionRunner(project)
        result = runner.preflight()
        assert result.ready is False
        assert any("BLOCKING" in e for e in result.errors)

    def test_missing_map_blocks_when_complexity_requires_it(self, tmp_path):
        project = _make_project(tmp_path)
        rules = {
            "boundaries": {
                "modules": {
                    "api": {"touches": ["auth", "db"]},
                    "auth": {"touches": ["db"]},
                    "db": {"touches": []},
                }
            }
        }
        expect = {
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
        with open(tmp_path / "rules.yaml", "w") as f:
            yaml.dump(rules, f, default_flow_style=False, sort_keys=False)
        with open(tmp_path / "expect.yaml", "w") as f:
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

        sm = StateManager(str(tmp_path / "acts.yaml"))
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

        sm = StateManager(str(tmp_path / "acts.yaml"))
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

        sm = StateManager(str(tmp_path / "acts.yaml"))
        state = sm.read()
        assert len(state["completed_tasks"]) == 12
        assert state["compaction"]["total_runs_compacted"] > 0

    def test_failed_preflight_blocks_run(self, tmp_path):
        project = _make_project(tmp_path, brain={"invalid": "brain"})
        runner = ExecutionRunner(project)
        result = runner.start_run(task="should fail")
        assert result.result == "failed"
        assert len(result.errors) > 0


class TestProjectHealth:

    def test_health_report(self, tmp_path):
        project = _make_project(tmp_path)
        runner = ExecutionRunner(project)
        health = runner.get_project_health()

        assert health["project"] == "test-project"
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

        assert ctx["facts"]["project"] == "test-project"
        assert ctx["task"] == "Build auth module"
        assert "state" in ctx
        assert ctx["_meta"]["token_count"] > 0

    def test_context_without_state(self, tmp_path):
        project = _make_project(tmp_path)
        runner = ExecutionRunner(project)
        ctx = runner.prepare_context(task="test", include_state=False)
        assert "state" not in ctx
