"""Tests for the Haxaml MCP server tools."""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from haxaml.mcp_server import (
    haxaml_init,
    haxaml_validate,
    haxaml_context,
    haxaml_context_pack,
    haxaml_health,
    haxaml_doctor,
    haxaml_guidance,
    haxaml_session_start,
    haxaml_session_plan,
    haxaml_session_verify,
    haxaml_session_record,
    haxaml_run,
    haxaml_done,
    haxaml_export,
    haxaml_upgrade,
    haxaml_mcp_bootstrap,
    haxaml_adopt_plan,
    haxaml_adopt,
    haxaml_reconcile,
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


def _msg(result):
    if isinstance(result, dict):
        return result.get("data", {}).get("message", "")
    return str(result)


RECONCILE_REQUIRED_GUIDANCE_FIELDS = {
    "fix_confidence",
    "safe_to_auto_apply",
    "related_files",
    "why_it_matters",
    "suggested_next_tool",
}


@pytest.fixture
def fresh_project(tmp_path):
    """Create a fresh project with initialized FRAME files."""
    result = haxaml_init(str(tmp_path))
    assert result["ok"] is True
    assert "✓ Initialized FRAME" in _msg(result)
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
        assert result["ok"] is True
        assert "✓ Initialized FRAME" in _msg(result)
        assert (tmp_path / ".haxaml" / "facts.yaml").exists()
        assert (tmp_path / ".haxaml" / "rules.yaml").exists()
        assert (tmp_path / ".haxaml" / "acts.yaml").exists()
        assert (tmp_path / ".haxaml" / "expect.yaml").exists()

    def test_does_not_overwrite_existing(self, fresh_project):
        result = haxaml_init(str(fresh_project))
        assert result["ok"] is True
        assert "already exists" in _msg(result)

    def test_scaffolds_validate(self, fresh_project):
        result = haxaml_validate(str(fresh_project))
        assert result["ok"] is True
        assert "facts.yaml is valid" in _msg(result)


# ─── Validate ────────────────────────────────────────────────────────────────


class TestValidate:
    def test_all_valid(self, governed_project):
        result = haxaml_validate(str(governed_project))
        text = _msg(result)
        assert result["ok"] is True
        assert "✓ All FRAME files valid" in text
        assert "✓ facts.yaml is valid" in text
        assert "✓ rules.yaml is valid" in text
        assert "✓ acts.yaml is valid" in text
        assert "✓ expect.yaml is valid" in text

    def test_missing_facts_fails(self, tmp_path):
        result = haxaml_validate(str(tmp_path))
        assert result["ok"] is False
        assert "facts.yaml not found" in result["error"]["details"]["message"]

    def test_invalid_facts_reports_errors(self, governed_project):
        (governed_project / ".haxaml" / "facts.yaml").write_text("bad: true\n")
        result = haxaml_validate(str(governed_project))
        assert result["ok"] is False
        assert "✗ facts.yaml" in result["error"]["details"]["message"]

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
        details = result["error"]["details"]["message"]
        assert result["ok"] is False
        assert "✗ map policy: map.yaml is required" in details
        assert "✗ Validation failed" in details

    def test_fails_on_blocking_derivation_conflicts(self, governed_project):
        map_data = {
            "modules": [
                {"name": "auth", "purpose": "Auth", "files": ["src/auth/"]},
                {"name": "api", "purpose": "API", "files": ["src/api/"]},
            ],
            "dependencies": [{"from": "api", "to": "auth", "reason": "auth middleware"}],
            "impact": [{"when": "auth", "check": ["api tests"]}],
        }
        (governed_project / ".haxaml" / "map.yaml").write_text(
            yaml.dump(map_data, default_flow_style=False, sort_keys=False)
        )

        result = haxaml_validate(str(governed_project))
        assert result["ok"] is False
        assert result["error"]["code"] == "derivation_conflicts"
        assert result["error"]["details"]["reconcile"]["severity_totals"]["blocking"] > 0


# ─── Context ─────────────────────────────────────────────────────────────────


class TestContext:
    def test_returns_context_with_tokens(self, governed_project):
        result = haxaml_context(str(governed_project))
        text = _msg(result)
        assert result["ok"] is True
        assert "Project Facts" in text
        assert "Token count:" in text

    def test_without_state(self, governed_project):
        result = haxaml_context(str(governed_project), include_state=False)
        text = _msg(result)
        assert result["ok"] is True
        assert "Project Facts" in text
        assert "Current Acts" not in text

    def test_context_pack_contains_expected_sections(self, governed_project):
        result = haxaml_context_pack(
            task="implement auth module",
            project_dir=str(governed_project),
            pack="balanced",
            include_state=True,
        )
        assert result["ok"] is True
        data = result["data"]
        assert data["pack"] == "balanced"
        assert data["tokens"] > 0
        assert "essential_facts" in data["context_pack"]
        assert "relevant_rules" in data["context_pack"]


# ─── Health ──────────────────────────────────────────────────────────────────


class TestHealth:
    def test_healthy_project(self, governed_project):
        result = haxaml_health(str(governed_project))
        text = _msg(result)
        assert result["ok"] is True
        assert "Project:    test-project" in text
        assert "Ready:      ✓" in text
        assert "Facts:      ✓ valid" in text

    def test_missing_project(self, tmp_path):
        result = haxaml_health(str(tmp_path))
        assert result["ok"] is False


# ─── Doctor ──────────────────────────────────────────────────────────────────


class TestDoctor:
    def test_complete_facts(self, governed_project):
        result = haxaml_doctor(str(governed_project))
        text = _msg(result)
        assert result["ok"] is True
        assert "complete" in text or "recommendation" in text

    def test_missing_facts(self, tmp_path):
        result = haxaml_doctor(str(tmp_path))
        assert result["ok"] is False
        assert "not found" in result["error"]["message"]


# ─── Run / Done ──────────────────────────────────────────────────────────────


class TestRunDone:
    def test_start_run(self, governed_project):
        result = haxaml_run("test task", description="testing", project_dir=str(governed_project))
        assert result["ok"] is True
        assert "✓ Run started: test task" in _msg(result)

    def test_complete_run(self, governed_project):
        haxaml_run("test task", project_dir=str(governed_project))
        result = haxaml_done(
            "test task", result="success", changes="did things",
            decisions="chose X", risks="none", project_dir=str(governed_project),
        )
        text = _msg(result)
        assert result["ok"] is True
        assert "Session record complete" in text

    def test_run_fails_without_facts(self, tmp_path):
        result = haxaml_run("task", project_dir=str(tmp_path))
        assert result["ok"] is False

    def test_done_fails_without_facts(self, tmp_path):
        result = haxaml_done("task", project_dir=str(tmp_path))
        assert result["ok"] is False


class TestSessionLifecycle:
    def test_guidance_classifies_and_scores_risk(self, governed_project):
        result = haxaml_guidance(task="migrate auth database", project_dir=str(governed_project))
        assert result["ok"] is True
        assert result["data"]["task_type"] in ("implementation", "debug", "design", "strategy", "outcome")
        assert result["data"]["risk_level"] in ("low", "medium", "high")

    def test_session_flow_start_plan_verify_record(self, governed_project):
        started = haxaml_session_start(
            task="implement auth module",
            description="add login endpoint",
            project_dir=str(governed_project),
        )
        assert started["ok"] is True
        session_id = started["data"]["session_id"]

        planned = haxaml_session_plan(session_id=session_id, project_dir=str(governed_project))
        assert planned["ok"] is True
        assert len(planned["data"]["plan"]) > 0

        verify = haxaml_session_verify(
            task="implement auth module",
            project_dir=str(governed_project),
            session_id=session_id,
            inspected_context=[".haxaml/facts.yaml", ".haxaml/rules.yaml"],
            changed_files=["src/auth.py"],
            summary="Implemented login flow and validation checks.",
        )
        assert verify["ok"] is True
        assert verify["data"]["verification_id"].startswith("verify-")
        assert verify["data"]["verdict"] in ("pass", "pass_with_risks")

        record = haxaml_session_record(
            task="implement auth module",
            result="success",
            session_id=session_id,
            project_dir=str(governed_project),
            changes="Added auth endpoints",
            decisions="Used existing token signer",
            risks="Needs extra load test",
        )
        assert record["ok"] is True
        assert record["data"]["run_id"].startswith("run-")

    def test_session_record_requires_verification_for_success(self, governed_project):
        started = haxaml_session_start(
            task="add billing flow",
            description="payment integration",
            project_dir=str(governed_project),
        )
        assert started["ok"] is True
        session_id = started["data"]["session_id"]

        record = haxaml_session_record(
            task="add billing flow",
            result="success",
            session_id=session_id,
            project_dir=str(governed_project),
            changes="Added billing handlers",
        )
        assert record["ok"] is False
        assert record["error"]["code"] == "verification_required"

    def test_session_record_blocks_success_when_derivation_conflicts_exist(self, governed_project):
        map_data = {
            "modules": [
                {"name": "auth", "purpose": "Auth", "files": ["src/auth/"]},
                {"name": "api", "purpose": "API", "files": ["src/api/"]},
            ],
            "dependencies": [{"from": "api", "to": "auth", "reason": "auth middleware"}],
            "impact": [{"when": "auth", "check": ["api tests"]}],
        }
        (governed_project / ".haxaml" / "map.yaml").write_text(
            yaml.dump(map_data, default_flow_style=False, sort_keys=False)
        )
        expect_path = governed_project / ".haxaml" / "expect.yaml"
        expect = yaml.safe_load(expect_path.read_text())
        expect["planning"]["map_required"] = True
        expect_path.write_text(yaml.dump(expect, default_flow_style=False, sort_keys=False))
        started = haxaml_session_start(
            task="implement auth module",
            description="add login endpoint",
            project_dir=str(governed_project),
        )
        assert started["ok"] is True
        session_id = started["data"]["session_id"]

        verify = haxaml_session_verify(
            task="implement auth module",
            project_dir=str(governed_project),
            session_id=session_id,
            inspected_context=[".haxaml/facts.yaml", ".haxaml/rules.yaml"],
            changed_files=["src/auth.py"],
            summary="Implemented login flow and validation checks.",
        )
        assert verify["ok"] is True

        record = haxaml_session_record(
            task="implement auth module",
            result="success",
            session_id=session_id,
            project_dir=str(governed_project),
            changes="Added auth endpoints",
            decisions="Used existing token signer",
            risks="Needs extra load test",
        )
        assert record["ok"] is False
        assert record["error"]["code"] == "derivation_conflicts"

    def test_session_record_failed_requires_explicit_conflict_reason(self, governed_project):
        map_data = {
            "modules": [
                {"name": "auth", "purpose": "Auth", "files": ["src/auth/"]},
                {"name": "api", "purpose": "API", "files": ["src/api/"]},
            ],
            "dependencies": [{"from": "api", "to": "auth", "reason": "auth middleware"}],
            "impact": [{"when": "auth", "check": ["api tests"]}],
        }
        (governed_project / ".haxaml" / "map.yaml").write_text(
            yaml.dump(map_data, default_flow_style=False, sort_keys=False)
        )
        expect_path = governed_project / ".haxaml" / "expect.yaml"
        expect = yaml.safe_load(expect_path.read_text())
        expect["planning"]["map_required"] = True
        expect_path.write_text(yaml.dump(expect, default_flow_style=False, sort_keys=False))
        started = haxaml_session_start(
            task="implement auth module",
            description="add login endpoint",
            project_dir=str(governed_project),
        )
        assert started["ok"] is True

        denied = haxaml_session_record(
            task="implement auth module",
            result="failed",
            session_id=started["data"]["session_id"],
            project_dir=str(governed_project),
            changes="Stopped work",
            decisions="Waiting",
            risks="none",
        )
        assert denied["ok"] is False
        assert denied["error"]["code"] == "conflict_reason_required"

        allowed = haxaml_session_record(
            task="implement auth module",
            result="failed",
            session_id=started["data"]["session_id"],
            project_dir=str(governed_project),
            changes="Stopped due to derivation conflict",
            decisions="Reconcile required before continuing",
            risks="map mismatch unresolved",
        )
        assert allowed["ok"] is True


# ─── Export ──────────────────────────────────────────────────────────────────


class TestExport:
    def test_export_generic(self, governed_project):
        result = haxaml_export("generic", str(governed_project))
        assert result["ok"] is True
        assert "✓ Exported to" in _msg(result)
        assert (governed_project / "HAXAML.md").exists()

    def test_export_claude(self, governed_project):
        result = haxaml_export("claude", str(governed_project))
        assert result["ok"] is True
        assert "✓ Exported to" in _msg(result)
        assert (governed_project / "CLAUDE.md").exists()

    def test_export_all(self, governed_project):
        result = haxaml_export("all", str(governed_project))
        text = _msg(result)
        assert result["ok"] is True
        assert "claude" in text
        assert "codex" in text
        assert "cursor" in text

    def test_export_invalid_agent(self, governed_project):
        result = haxaml_export("nonexistent", str(governed_project))
        assert result["ok"] is False

    def test_export_codex_defaults_to_haxaml_agents(self, governed_project):
        result = haxaml_export("codex", str(governed_project))
        assert result["ok"] is True
        assert "✓ Exported to" in _msg(result)
        assert (governed_project / "haxaml-agents.md").exists()

    def test_export_codex_override_native_replaces_agents_md(self, governed_project):
        native = governed_project / "AGENTS.md"
        native.write_text("human-written file\n", encoding="utf-8")

        result = haxaml_export(
            "codex",
            str(governed_project),
            override_native=True,
        )
        assert result["ok"] is True
        assert "✓ Exported to" in _msg(result)
        assert "Generated by Haxaml from FRAME" in native.read_text(encoding="utf-8")

    def test_export_target_writes_custom_path(self, governed_project):
        custom = governed_project / "TEAM_GUIDE.md"
        result = haxaml_export(
            "generic",
            str(governed_project),
            target=str(custom),
        )
        assert result["ok"] is True
        assert "✓ Exported to" in _msg(result)
        assert custom.exists()
        assert "Generated by Haxaml from FRAME" in custom.read_text(encoding="utf-8")

    def test_export_all_rejects_target(self, governed_project):
        result = haxaml_export(
            "all",
            str(governed_project),
            target="TEAM_GUIDE.md",
        )
        assert result["ok"] is False
        assert "target cannot be used with agent='all'" in result["error"]["message"]

    def test_export_dry_run_does_not_write(self, governed_project):
        target = governed_project / "PREVIEW.md"
        result = haxaml_export(
            "generic",
            str(governed_project),
            target=str(target),
            dry_run=True,
            diff_preview=True,
        )
        assert result["ok"] is True
        assert target.exists() is False
        assert result["data"]["would_write"] is True
        assert isinstance(result["data"]["diff"], str)


class TestBootstrap:
    def test_bootstrap_snippets_only(self, governed_project):
        result = haxaml_mcp_bootstrap(str(governed_project), mode="snippets")
        assert result["ok"] is True
        assert "snippets" in result["data"]
        assert result["data"]["writes"] == []

    def test_bootstrap_write_mode(self, governed_project):
        result = haxaml_mcp_bootstrap(
            str(governed_project),
            editors=["generic"],
            mode="write",
        )
        assert result["ok"] is True
        statuses = [w["status"] for w in result["data"]["writes"]]
        assert "written" in statuses or "skipped_exists" in statuses
        assert (governed_project / ".mcp.json").exists()


class TestUpgrade:
    def test_upgrade_dry_run(self):
        result = haxaml_upgrade(target_version="9.9.9", dry_run=True)
        assert result["ok"] is True
        assert result["data"]["command"][:3] == ["uv", "tool", "upgrade"]
        assert "haxaml==9.9.9" in result["data"]["command"]

    @patch("haxaml.mcp_server.shutil.which", return_value=None)
    def test_upgrade_requires_uv(self, _which):
        result = haxaml_upgrade()
        assert result["ok"] is False
        assert result["error"]["code"] == "uv_not_found"


# ─── Adopt ───────────────────────────────────────────────────────────────────


class TestAdopt:
    def test_dry_run(self, tmp_path):
        (tmp_path / "CLAUDE.md").write_text("# Rules\nUse pytest.\n")
        (tmp_path / "README.md").write_text("# Project\n")
        result = haxaml_adopt(str(tmp_path), write=False)
        text = _msg(result)
        assert result["ok"] is True
        assert "Dry run" in text
        assert "CLAUDE.md" in text

    def test_write(self, tmp_path):
        (tmp_path / "CLAUDE.md").write_text("# Rules\nUse pytest.\n")
        result = haxaml_adopt(str(tmp_path), write=True)
        assert result["ok"] is True
        assert "✓ wrote" in _msg(result)
        assert (tmp_path / ".haxaml" / "ADOPTION.md").exists()


class TestAdoptPlan:
    def test_returns_non_destructive_inventory(self, tmp_path):
        (tmp_path / "CLAUDE.md").write_text("# Rules\nUse tests.\n")
        (tmp_path / "README.md").write_text("# Project\n")
        result = haxaml_adopt_plan(str(tmp_path))
        assert result["ok"] is True
        data = result["data"]
        assert data["non_destructive"] is True
        assert data["counts"]["native_files"] >= 1
        assert "human_summary" in data
        assert (tmp_path / ".haxaml").exists() is False


class TestReconcile:
    def test_optional_map_deferred_when_absent(self, governed_project):
        result = haxaml_reconcile(str(governed_project))
        assert result["ok"] is True
        assert result["data"]["deferred_map_canonical_checks"] is True
        assert result["data"]["conflict_counts"]["blocking"] == 0

    def test_returns_blocking_conflicts_when_map_present_and_misaligned(self, governed_project):
        map_data = {
            "modules": [
                {"name": "auth", "purpose": "Auth", "files": ["src/auth/"]},
                {"name": "api", "purpose": "API", "files": ["src/api/"]},
            ],
            "dependencies": [{"from": "api", "to": "auth", "reason": "auth middleware"}],
            "impact": [{"when": "auth", "check": ["api tests"]}],
        }
        (governed_project / ".haxaml" / "map.yaml").write_text(
            yaml.dump(map_data, default_flow_style=False, sort_keys=False)
        )

        result = haxaml_reconcile(str(governed_project))
        assert result["ok"] is False
        assert result["error"]["code"] == "derivation_conflicts"
        assert result["error"]["details"]["severity_totals"]["blocking"] > 0

        conflicts = result["error"]["details"]["conflicts"]
        assert conflicts
        allowed_confidence = {"low", "medium", "high"}
        allowed_next_tool = {
            "haxaml_validate",
            "haxaml_doctor",
            "haxaml_impact",
            "haxaml_session_verify",
            "haxaml_context_pack",
            "manual_edit",
        }
        for conflict in conflicts:
            assert RECONCILE_REQUIRED_GUIDANCE_FIELDS.issubset(conflict.keys())
            assert conflict["fix_confidence"] in allowed_confidence
            assert conflict["safe_to_auto_apply"] is False
            assert conflict["suggested_next_tool"] in allowed_next_tool
            assert isinstance(conflict["related_files"], list)
            assert len(conflict["related_files"]) > 0
            assert conflict["related_files"] == sorted(conflict["related_files"])
            assert all(isinstance(item, str) and item for item in conflict["related_files"])
            assert isinstance(conflict["why_it_matters"], str)
            assert conflict["why_it_matters"].strip()

    def test_deterministic_summary_for_equivalent_state(self, governed_project):
        map_data = {
            "modules": [
                {"name": "auth", "purpose": "Auth", "files": ["src/auth/"]},
                {"name": "api", "purpose": "API", "files": ["src/api/"]},
            ],
            "dependencies": [{"from": "api", "to": "auth", "reason": "auth middleware"}],
            "impact": [{"when": "auth", "check": ["api tests"]}],
        }
        (governed_project / ".haxaml" / "map.yaml").write_text(
            yaml.dump(map_data, default_flow_style=False, sort_keys=False)
        )

        first = haxaml_reconcile(str(governed_project))
        second = haxaml_reconcile(str(governed_project))
        first_details = first["error"]["details"]
        second_details = second["error"]["details"]
        assert first_details["human_summary"] == second_details["human_summary"]
        assert first_details["conflicts"] == second_details["conflicts"]


# ─── Needs ───────────────────────────────────────────────────────────────────


class TestNeeds:
    def test_no_blocking_needs(self, governed_project):
        result = haxaml_needs(str(governed_project))
        text = _msg(result)
        assert result["ok"] is True
        assert "ready to build" in text or "Non-blocking" in text or "Active run" in text

    def test_blocking_unresolved(self, governed_project):
        facts_path = governed_project / ".haxaml" / "facts.yaml"
        facts = yaml.safe_load(facts_path.read_text())
        facts["unresolved"] = [{"item": "DB URI", "reason": "Need production URI", "blocking": True}]
        facts_path.write_text(yaml.dump(facts, default_flow_style=False, sort_keys=False))

        result = haxaml_needs(str(governed_project))
        assert result["ok"] is True
        assert "Blocking" in _msg(result)
        assert "DB URI" in _msg(result)

    def test_missing_project(self, tmp_path):
        result = haxaml_needs(str(tmp_path))
        assert "facts.yaml not found" in _msg(result)


# ─── Impact ──────────────────────────────────────────────────────────────────


class TestImpact:
    def test_no_map(self, governed_project):
        result = haxaml_impact("auth", str(governed_project))
        assert result["ok"] is True
        assert "map.yaml not found" in _msg(result)

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
        text = _msg(result)
        assert result["ok"] is True
        assert "Module: auth" in text
        assert "Authentication" in text
        assert "src/auth/" in text
        assert "api" in text
        assert "api tests" in text

    def test_module_not_found(self, governed_project):
        map_data = {"modules": [{"name": "auth", "purpose": "Auth", "files": []}],
                     "dependencies": [], "impact": []}
        (governed_project / ".haxaml" / "map.yaml").write_text(
            yaml.dump(map_data, default_flow_style=False, sort_keys=False)
        )

        result = haxaml_impact("nonexistent", str(governed_project))
        assert result["ok"] is False
        assert "not found" in result["error"]["message"]
        assert "auth" in result["error"]["message"]


# ─── State ───────────────────────────────────────────────────────────────────


class TestState:
    def test_show(self, governed_project):
        result = haxaml_state_show(str(governed_project))
        text = _msg(result)
        assert result["ok"] is True
        assert "Phase:" in text
        assert "Active:" in text
        assert "Completed:" in text

    def test_compact_no_runs(self, governed_project):
        result = haxaml_state_compact(str(governed_project))
        assert result["ok"] is True
        assert "Compacted 0" in _msg(result)

    def test_show_missing(self, tmp_path):
        result = haxaml_state_show(str(tmp_path))
        assert result["ok"] is False
        assert "not found" in result["error"]["message"]


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
        assert len(tools) >= 24

    def test_expected_tools_registered(self):
        tools = mcp_app._tool_manager._tools
        expected = [
            "haxaml_init", "haxaml_validate", "haxaml_context", "haxaml_health",
            "haxaml_doctor", "haxaml_run", "haxaml_done", "haxaml_export",
            "haxaml_upgrade", "haxaml_mcp_bootstrap",
            "haxaml_adopt_plan", "haxaml_reconcile", "haxaml_adopt",
            "haxaml_needs", "haxaml_impact", "haxaml_state_show",
            "haxaml_state_compact", "haxaml_benchmark",
            "haxaml_context_pack", "haxaml_guidance",
            "haxaml_session_start", "haxaml_session_plan",
            "haxaml_session_verify", "haxaml_session_record",
        ]
        for name in expected:
            assert name in tools, f"Tool {name} not registered"

    def test_server_name(self):
        assert mcp_app.name == "haxaml"
