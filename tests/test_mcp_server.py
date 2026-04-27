"""Tests for the Haxaml MCP server tools."""

import os
import tempfile
from pathlib import Path

import pytest
import yaml

from haxaml.mcp_server import (
    haxaml_init,
    haxaml_validate,
    haxaml_context,
    haxaml_health,
    haxaml_doctor,
    haxaml_run,
    haxaml_done,
    haxaml_export,
    haxaml_adopt,
    haxaml_needs,
    haxaml_impact,
    haxaml_state_show,
    haxaml_state_compact,
    resource_facts,
    resource_rules,
    resource_acts,
    resource_expect,
    resource_map,
    resource_context,
    mcp_app,
)


@pytest.fixture
def fresh_project(tmp_path):
    """Create a fresh project with initialized FRAME files."""
    result = haxaml_init(str(tmp_path))
    assert "✓ Initialized FRAME" in result
    return tmp_path


@pytest.fixture
def governed_project(fresh_project):
    """A project with FRAME files filled in with valid content."""
    facts = {
        "identity": {"name": "test-project", "version": "0.1.0", "description": "A test project"},
        "goal": {"purpose": "Testing", "scope": "Unit tests", "out_of_scope": []},
        "stack": {"language": "python", "backend": "fastapi", "frontend": "none",
                  "runtime": "python3.12", "package_manager": "pip"},
        "architecture": {"pattern": "layered", "reasoning": "Simple project", "boundaries": []},
        "database": {"type": "sqlite", "connection": "sqlite:///test.db", "migrations": "alembic"},
        "tools": {"testing": "pytest", "mcp": [], "ci": "none", "other": []},
        "services": [],
        "constraints": ["Must pass all tests"],
        "success_criteria": ["All tests green"],
        "roles": [],
        "features": [],
        "unresolved": [],
    }
    rules = {
        "governance": {"system": "haxaml", "version": "0.1.0"},
        "before_task": {"read_first": [".haxaml/facts.yaml"], "then_read": [], "check": ["Confirm task"]},
        "boundaries": {"modules": {}, "rules": ["Stay in scope"]},
        "while_coding": {"constraints": ["Keep changes small"], "discipline": ["Run tests"]},
        "after_task": {"report": ["What changed"], "update": [".haxaml/acts.yaml"], "verify": ["Validate"]},
        "forbidden": ["Do not guess"],
        "escalation": {"act_independently": ["Small fixes"], "ask_first": ["Arch changes"]},
    }
    acts = {
        "current_phase": "Phase 1",
        "active_task": {"name": "none"},
        "completed_tasks": [],
        "blocked_tasks": [],
        "decisions": [],
        "unresolved_dependencies": [],
        "runs": [],
        "compaction": {"last_compacted": None, "total_runs_compacted": 0, "summary": "No runs yet."},
    }
    expect = {
        "planning": {
            "goal": "Build test project",
            "strategy": "Incremental",
            "estimated_runs": 3,
            "project_size": "small",
            "map_required": False,
            "map_reason": "Small project",
        },
        "map_policy": {
            "small_project_max_runs": 5,
            "medium_project_max_runs": 12,
            "require_map_when": ["10+ modules"],
            "agent_instruction": "Read map.yaml when required.",
        },
        "phases": [{"name": "Phase 1", "status": "active", "run_range": "1-3",
                     "target_runs": 3, "description": "Build it", "done_when": "Tests pass"}],
        "runbook": [{
            "run": 1, "phase": "Phase 1", "status": "active",
            "goal": "Setup", "outcome": "Project scaffolded",
            "depends_on": [], "touches": ["all"], "requires": ["Stack decision"],
            "uses_map": False, "verify": ["haxaml validate"], "done_when": "Scaffolded",
        }],
        "upcoming": [{"task": "Setup project", "priority": "critical",
                       "phase": "Phase 1", "description": "Initial setup"}],
        "milestones": [{"name": "Setup done", "status": "pending", "criteria": "Validate passes"}],
        "open_questions": [],
    }

    haxaml_dir = fresh_project / ".haxaml"
    for name, data in [("facts.yaml", facts), ("rules.yaml", rules),
                        ("acts.yaml", acts), ("expect.yaml", expect)]:
        (haxaml_dir / name).write_text(yaml.dump(data, default_flow_style=False, sort_keys=False))

    return fresh_project


# ─── Init ────────────────────────────────────────────────────────────────────


class TestInit:
    def test_creates_frame_files(self, tmp_path):
        result = haxaml_init(str(tmp_path))
        assert "✓ Initialized FRAME" in result
        assert (tmp_path / ".haxaml" / "facts.yaml").exists()
        assert (tmp_path / ".haxaml" / "rules.yaml").exists()
        assert (tmp_path / ".haxaml" / "acts.yaml").exists()
        assert (tmp_path / ".haxaml" / "expect.yaml").exists()

    def test_does_not_overwrite_existing(self, fresh_project):
        result = haxaml_init(str(fresh_project))
        assert "already exists" in result

    def test_scaffolds_validate(self, fresh_project):
        result = haxaml_validate(str(fresh_project))
        assert "facts.yaml is valid" in result


# ─── Validate ────────────────────────────────────────────────────────────────


class TestValidate:
    def test_all_valid(self, governed_project):
        result = haxaml_validate(str(governed_project))
        assert "✓ All FRAME files valid" in result
        assert "✓ facts.yaml is valid" in result
        assert "✓ rules.yaml is valid" in result
        assert "✓ acts.yaml is valid" in result
        assert "✓ expect.yaml is valid" in result

    def test_missing_facts_fails(self, tmp_path):
        result = haxaml_validate(str(tmp_path))
        assert "✗ facts.yaml not found" in result

    def test_invalid_facts_reports_errors(self, governed_project):
        (governed_project / ".haxaml" / "facts.yaml").write_text("bad: true\n")
        result = haxaml_validate(str(governed_project))
        assert "✗ facts.yaml" in result

    def test_fails_when_complexity_requires_map_but_map_missing(self, governed_project):
        rules_path = governed_project / ".haxaml" / "rules.yaml"
        rules = yaml.safe_load(rules_path.read_text())
        rules["boundaries"]["modules"] = {
            "api": {"touches": ["auth", "db"]},
            "auth": {"touches": ["db"]},
            "db": {"touches": []},
        }
        rules_path.write_text(yaml.dump(rules, default_flow_style=False, sort_keys=False))

        expect_path = governed_project / ".haxaml" / "expect.yaml"
        expect = yaml.safe_load(expect_path.read_text())
        expect["planning"]["map_required"] = False
        expect["map_policy"]["module_threshold"] = 3
        expect_path.write_text(yaml.dump(expect, default_flow_style=False, sort_keys=False))

        result = haxaml_validate(str(governed_project))
        assert "✗ map policy: map.yaml is required" in result
        assert "✗ Validation failed" in result


# ─── Context ─────────────────────────────────────────────────────────────────


class TestContext:
    def test_returns_context_with_tokens(self, governed_project):
        result = haxaml_context(str(governed_project))
        assert "Project Facts" in result
        assert "Token count:" in result

    def test_without_state(self, governed_project):
        result = haxaml_context(str(governed_project), include_state=False)
        assert "Project Facts" in result
        assert "Current Acts" not in result


# ─── Health ──────────────────────────────────────────────────────────────────


class TestHealth:
    def test_healthy_project(self, governed_project):
        result = haxaml_health(str(governed_project))
        assert "Project:    test-project" in result
        assert "Ready:      ✓" in result
        assert "Facts:      ✓ valid" in result

    def test_missing_project(self, tmp_path):
        result = haxaml_health(str(tmp_path))
        assert "✗" in result


# ─── Doctor ──────────────────────────────────────────────────────────────────


class TestDoctor:
    def test_complete_facts(self, governed_project):
        result = haxaml_doctor(str(governed_project))
        assert "complete" in result or "recommendation" in result

    def test_missing_facts(self, tmp_path):
        result = haxaml_doctor(str(tmp_path))
        assert "not found" in result


# ─── Run / Done ──────────────────────────────────────────────────────────────


class TestRunDone:
    def test_start_run(self, governed_project):
        result = haxaml_run("test task", description="testing", project_dir=str(governed_project))
        assert "✓ Run started: test task" in result

    def test_complete_run(self, governed_project):
        haxaml_run("test task", project_dir=str(governed_project))
        result = haxaml_done(
            "test task", result="success", changes="did things",
            decisions="chose X", risks="none", project_dir=str(governed_project),
        )
        assert "✓ Run" in result
        assert "recorded (success)" in result

    def test_run_fails_without_facts(self, tmp_path):
        result = haxaml_run("task", project_dir=str(tmp_path))
        assert "✗" in result

    def test_done_fails_without_facts(self, tmp_path):
        result = haxaml_done("task", project_dir=str(tmp_path))
        assert "✗" in result


# ─── Export ──────────────────────────────────────────────────────────────────


class TestExport:
    def test_export_generic(self, governed_project):
        result = haxaml_export("generic", str(governed_project))
        assert "✓ Exported to" in result
        assert (governed_project / "HAXAML.md").exists()

    def test_export_claude(self, governed_project):
        result = haxaml_export("claude", str(governed_project))
        assert "✓ Exported to" in result
        assert (governed_project / "CLAUDE.md").exists()

    def test_export_all(self, governed_project):
        result = haxaml_export("all", str(governed_project))
        assert "claude" in result
        assert "codex" in result
        assert "cursor" in result

    def test_export_invalid_agent(self, governed_project):
        result = haxaml_export("nonexistent", str(governed_project))
        assert "✗" in result


# ─── Adopt ───────────────────────────────────────────────────────────────────


class TestAdopt:
    def test_dry_run(self, tmp_path):
        (tmp_path / "CLAUDE.md").write_text("# Rules\nUse pytest.\n")
        (tmp_path / "README.md").write_text("# Project\n")
        result = haxaml_adopt(str(tmp_path), write=False)
        assert "Dry run" in result
        assert "CLAUDE.md" in result

    def test_write(self, tmp_path):
        (tmp_path / "CLAUDE.md").write_text("# Rules\nUse pytest.\n")
        result = haxaml_adopt(str(tmp_path), write=True)
        assert "✓ wrote" in result
        assert (tmp_path / ".haxaml" / "ADOPTION.md").exists()


# ─── Needs ───────────────────────────────────────────────────────────────────


class TestNeeds:
    def test_no_blocking_needs(self, governed_project):
        result = haxaml_needs(str(governed_project))
        assert "ready to build" in result or "Non-blocking" in result or "Active run" in result

    def test_blocking_unresolved(self, governed_project):
        facts_path = governed_project / ".haxaml" / "facts.yaml"
        facts = yaml.safe_load(facts_path.read_text())
        facts["unresolved"] = [{"item": "DB URI", "reason": "Need production URI", "blocking": True}]
        facts_path.write_text(yaml.dump(facts, default_flow_style=False, sort_keys=False))

        result = haxaml_needs(str(governed_project))
        assert "Blocking" in result
        assert "DB URI" in result

    def test_missing_project(self, tmp_path):
        result = haxaml_needs(str(tmp_path))
        assert "facts.yaml not found" in result


# ─── Impact ──────────────────────────────────────────────────────────────────


class TestImpact:
    def test_no_map(self, governed_project):
        result = haxaml_impact("auth", str(governed_project))
        assert "map.yaml not found" in result

    def test_module_found(self, governed_project):
        map_data = {
            "modules": [
                {"name": "auth", "purpose": "Authentication", "files": ["src/auth/"]},
                {"name": "api", "purpose": "API routes", "files": ["src/api/"]},
            ],
            "dependencies": [
                {"from": "api", "to": "auth", "reason": "API needs auth middleware"},
            ],
            "impact": [
                {"when": "auth", "check": ["api tests", "middleware tests"]},
            ],
        }
        (governed_project / ".haxaml" / "map.yaml").write_text(
            yaml.dump(map_data, default_flow_style=False, sort_keys=False)
        )

        result = haxaml_impact("auth", str(governed_project))
        assert "Module: auth" in result
        assert "Authentication" in result
        assert "src/auth/" in result
        assert "api" in result
        assert "api tests" in result

    def test_module_not_found(self, governed_project):
        map_data = {"modules": [{"name": "auth", "purpose": "Auth", "files": []}],
                     "dependencies": [], "impact": []}
        (governed_project / ".haxaml" / "map.yaml").write_text(
            yaml.dump(map_data, default_flow_style=False, sort_keys=False)
        )

        result = haxaml_impact("nonexistent", str(governed_project))
        assert "not found" in result
        assert "auth" in result


# ─── State ───────────────────────────────────────────────────────────────────


class TestState:
    def test_show(self, governed_project):
        result = haxaml_state_show(str(governed_project))
        assert "Phase:" in result
        assert "Active:" in result
        assert "Completed:" in result

    def test_compact_no_runs(self, governed_project):
        result = haxaml_state_compact(str(governed_project))
        assert "Compacted 0" in result

    def test_show_missing(self, tmp_path):
        result = haxaml_state_show(str(tmp_path))
        assert "not found" in result


# ─── Resources ───────────────────────────────────────────────────────────────


class TestResources:
    def test_facts_resource(self, governed_project, monkeypatch):
        monkeypatch.setenv("HAXAML_PROJECT_DIR", str(governed_project))
        content = resource_facts()
        assert "test-project" in content

    def test_rules_resource(self, governed_project, monkeypatch):
        monkeypatch.setenv("HAXAML_PROJECT_DIR", str(governed_project))
        content = resource_rules()
        assert "haxaml" in content

    def test_acts_resource(self, governed_project, monkeypatch):
        monkeypatch.setenv("HAXAML_PROJECT_DIR", str(governed_project))
        content = resource_acts()
        assert "Phase 1" in content

    def test_expect_resource(self, governed_project, monkeypatch):
        monkeypatch.setenv("HAXAML_PROJECT_DIR", str(governed_project))
        content = resource_expect()
        assert "goal" in content

    def test_map_resource_missing(self, governed_project, monkeypatch):
        monkeypatch.setenv("HAXAML_PROJECT_DIR", str(governed_project))
        content = resource_map()
        assert "not found" in content

    def test_context_resource(self, governed_project, monkeypatch):
        monkeypatch.setenv("HAXAML_PROJECT_DIR", str(governed_project))
        content = resource_context()
        assert "Project Facts" in content


# ─── Server registration ────────────────────────────────────────────────────


class TestServerRegistration:
    def test_tool_count(self):
        tools = mcp_app._tool_manager._tools
        assert len(tools) == 14

    def test_expected_tools_registered(self):
        tools = mcp_app._tool_manager._tools
        expected = [
            "haxaml_init", "haxaml_validate", "haxaml_context", "haxaml_health",
            "haxaml_doctor", "haxaml_run", "haxaml_done", "haxaml_export",
            "haxaml_adopt", "haxaml_needs", "haxaml_impact", "haxaml_state_show",
            "haxaml_state_compact", "haxaml_benchmark",
        ]
        for name in expected:
            assert name in tools, f"Tool {name} not registered"

    def test_server_name(self):
        assert mcp_app.name == "haxaml"
