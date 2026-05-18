"""Tests for the execution loop runner."""

import os
import shutil

import pytest
import yaml

from haxaml.acts_archive import ActsArchive
from haxaml.runner import ExecutionRunner, RunResult, PreflightResult
from haxaml.state_manager import StateManager


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

    if state is None:
        state = {
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

    rules = {
        "before_task": {"read_first": [".haxaml/facts.yaml", ".haxaml/rules.yaml", ".haxaml/acts.yaml"]},
        "boundaries": {"rules": ["Keep changes scoped to the active task."]},
        "after_task": {
            "report": ["Summarize what changed."],
            "update": [".haxaml/acts.yaml"],
            "verify": ["Run relevant tests or validation checks."],
        },
        "forbidden": ["Do not claim success without verification evidence."],
    }
    expect = {
        "planning": {
            "goal": "Complete one scoped task safely.",
            "strategy": "Small governed runs.",
            "estimated_runs": 1,
            "project_size": "small",
            "map_required": False,
            "map_reason": "Map is optional for this fixture.",
        },
        "map_policy": {
            "module_threshold": 10,
            "cross_impact_touch_threshold": 3,
            "cross_impact_run_threshold": 2,
            "dependency_fanout_threshold": 3,
            "impact_check_threshold": 3,
            "shared_integration_module_threshold": 2,
            "require_map_when": ["Module count exceeds policy threshold."],
            "agent_instruction": "Read map.yaml when map_required is true.",
        },
        "phases": [
            {
                "name": "Phase 1",
                "status": "active",
                "run_range": "1-1",
                "target_runs": 1,
                "description": "Fixture phase.",
                "done_when": "One run is recorded.",
            }
        ],
        "runbook": [
            {
                "run": 1,
                "phase": "Phase 1",
                "status": "active",
                "goal": "Execute one fixture task.",
                "outcome": "Fixture task recorded.",
                "depends_on": [],
                "touches": ["scoped files only"],
                "requires": ["Clear task statement"],
                "uses_map": False,
                "verify": ["Run relevant validation."],
                "done_when": "Verification passes and the session is recorded.",
            }
        ],
        "upcoming": [],
        "milestones": [],
        "open_questions": [],
    }

    haxaml_dir = tmp_path / ".haxaml"
    haxaml_dir.mkdir(exist_ok=True)

    facts_path = haxaml_dir / "facts.yaml"
    with open(facts_path, "w") as f:
        yaml.dump(brain, f, default_flow_style=False, sort_keys=False)

    acts_path = haxaml_dir / "acts.yaml"
    with open(acts_path, "w") as f:
        yaml.dump(state, f, default_flow_style=False, sort_keys=False)

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
        rules_path = tmp_path / ".haxaml" / "rules.yaml"
        rules = yaml.safe_load(rules_path.read_text())
        rules["memory_policy"] = {
            "archive_mode": "on_record",
            "max_hot_runs": 5,
            "max_hot_sessions": 5,
            "max_hot_verifications": 5,
            "max_acts_bytes": 16000,
            "keep_decisions_hot": True,
        }
        with open(rules_path, "w") as f:
            yaml.dump(rules, f, default_flow_style=False, sort_keys=False)
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
