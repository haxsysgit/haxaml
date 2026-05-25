"""Shared fixtures/helpers for MCP module tests."""

from pathlib import Path

import pytest
import yaml

from haxaml.mcp_server import haxaml_about, haxaml_init

from .helpers import write_runtime_state


def _msg(result):
    if isinstance(result, dict):
        return result.get("data", {}).get("message", "")
    return str(result)


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


@pytest.fixture
def fresh_project(tmp_path: Path) -> Path:
    """Create a fresh project with initialized FRAME files."""
    result = haxaml_init(str(tmp_path))
    assert result["ok"] is True
    assert "Initialized FRAME" in _msg(result)
    about = haxaml_about(str(tmp_path))
    assert about["ok"] is True
    return tmp_path


@pytest.fixture
def governed_project(fresh_project: Path) -> Path:
    """A project with FRAME files filled in with valid content."""
    facts = {
        "frame": _frame("facts", "stable_project_truth"),
        "identity": {"name": "test-project", "version": "0.1.0", "description": "A test project"},
        "goal": {"purpose": "Testing", "scope": "Unit tests", "out_of_scope": []},
        "stack": {
            "language": "python",
            "backend": "fastapi",
            "frontend": "none",
            "runtime": "python3.12",
            "package_manager": "pip",
        },
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
        "frame": _frame("rules", "project_constraints"),
        "governance": {"system": "haxaml", "version": "0.1.0"},
        "before_task": {"read_first": [".haxaml/facts.yaml"], "then_read": [], "check": ["Confirm task"]},
        "boundaries": {"modules": {}, "rules": ["Stay in scope"]},
        "while_coding": {"constraints": ["Keep changes small"], "discipline": ["Run tests"]},
        "after_task": {"report": ["What changed"], "update": [".haxaml/acts.yaml"], "verify": ["Validate"]},
        "forbidden": ["Do not guess"],
        "escalation": {"act_independently": ["Small fixes"], "ask_first": ["Arch changes"]},
    }
    acts = {
        "frame": _frame("acts", "checked_activity_record"),
        "current_phase": "Phase 1",
        "active_task": {"name": "none"},
        "completed_tasks": [],
        "blocked_tasks": [],
        "decisions": [],
        "unresolved_dependencies": [],
        "runs": [],
        "sessions": [],
        "verifications": [],
        "archive": {
            "path": str(fresh_project / ".haxaml" / "archive" / "acts-history.yaml"),
            "archive_mode": "manual",
            "last_archived_at": "",
            "archived_counts": {"runs": 0, "sessions": 0, "verifications": 0},
            "hot_limits": {"runs": 5, "sessions": 5, "verifications": 5},
        },
    }
    expect = {
        "frame": _frame("expect", "planned_direction"),
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
        "phases": [
            {
                "name": "Phase 1",
                "status": "active",
                "run_range": "1-3",
                "target_runs": 3,
                "description": "Build it",
                "done_when": "Tests pass",
            }
        ],
        "runbook": [
            {
                "run": 1,
                "phase": "Phase 1",
                "status": "active",
                "goal": "Setup",
                "outcome": "Project scaffolded",
                "depends_on": [],
                "touches": ["all"],
                "requires": ["Stack decision"],
                "uses_map": False,
                "verify": ["haxaml validate"],
                "done_when": "Scaffolded",
            }
        ],
        "upcoming": [
            {
                "task": "Setup project",
                "priority": "critical",
                "phase": "Phase 1",
                "description": "Initial setup",
            }
        ],
        "milestones": [{"name": "Setup done", "status": "pending", "criteria": "Validate passes"}],
        "open_questions": [],
    }

    haxaml_dir = fresh_project / ".haxaml"
    for name, data in [
        ("facts.yaml", {"frame": facts["frame"]}),
        ("rules.yaml", {"frame": rules["frame"]}),
        ("acts.yaml", {"frame": acts["frame"]}),
        ("expect.yaml", {"frame": expect["frame"]}),
    ]:
        (haxaml_dir / name).write_text(yaml.dump(data, default_flow_style=False, sort_keys=False))
    write_runtime_state(fresh_project, {key: value for key, value in acts.items() if key != "frame"})

    about = haxaml_about(str(fresh_project))
    assert about["ok"] is True
    return fresh_project
