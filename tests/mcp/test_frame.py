"""Tests for FRAME/core MCP tools."""

import subprocess
import yaml

from haxaml.mcp_server import (
    haxaml_context,
    haxaml_context_pack,
    haxaml_doctor,
    haxaml_guidance,
    haxaml_health,
    haxaml_init,
    haxaml_session_plan,
    haxaml_session_start,
    haxaml_validate,
)
from haxaml.versioning import get_version

from .helpers import msg as _msg


def _start_session_for_pack(project_dir, task: str = "implement auth module") -> str:
    guided = haxaml_guidance(task=task, project_dir=str(project_dir))
    assert guided["ok"] is True
    started = haxaml_session_start(task=task, description="context-pack test", project_dir=str(project_dir))
    assert started["ok"] is True
    session_id = started["data"]["session_id"]
    planned = haxaml_session_plan(session_id=session_id, project_dir=str(project_dir))
    assert planned["ok"] is True
    return session_id


class TestInit:
    def test_creates_frame_files(self, tmp_path):
        result = haxaml_init(str(tmp_path))
        assert result["ok"] is True
        assert "Initialized FRAME" in _msg(result)
        assert (tmp_path / ".haxaml" / "facts.yaml").exists()
        assert (tmp_path / ".haxaml" / "rules.yaml").exists()
        assert (tmp_path / ".haxaml" / "acts.yaml").exists()
        assert (tmp_path / ".haxaml" / "expect.yaml").exists()

    def test_does_not_overwrite_existing(self, fresh_project):
        result = haxaml_init(str(fresh_project))
        assert result["ok"] is True
        assert "already exists" in _msg(result)

    def test_syncs_rules_governance_version_for_existing_project(self, fresh_project):
        rules_path = fresh_project / ".haxaml" / "rules.yaml"
        rules = yaml.safe_load(rules_path.read_text())
        rules["governance"]["version"] = "0.0.1"
        rules_path.write_text(yaml.dump(rules, default_flow_style=False, sort_keys=False))

        result = haxaml_init(str(fresh_project))
        assert result["ok"] is True
        assert "already exists" in _msg(result)
        assert "Synced .haxaml/rules.yaml governance.version" in _msg(result)

        synced = yaml.safe_load(rules_path.read_text())
        assert synced["governance"]["version"] == get_version()

    def test_scaffolds_validate(self, fresh_project):
        result = haxaml_validate(str(fresh_project))
        assert result["ok"] is True
        assert "facts.yaml is valid" in _msg(result)


class TestValidate:
    def test_all_valid(self, governed_project):
        result = haxaml_validate(str(governed_project))
        text = _msg(result)
        assert result["ok"] is True
        assert "All FRAME files valid" in text
        assert "facts.yaml is valid" in text
        assert "rules.yaml is valid" in text
        assert "acts.yaml is valid" in text
        assert "expect.yaml is valid" in text

    def test_missing_facts_fails(self, tmp_path):
        result = haxaml_validate(str(tmp_path))
        assert result["ok"] is False
        assert "facts.yaml not found" in result["error"]["details"]["message"]

    def test_invalid_facts_reports_errors(self, governed_project):
        (governed_project / ".haxaml" / "facts.yaml").write_text("bad: true\n")
        result = haxaml_validate(str(governed_project))
        assert result["ok"] is False
        assert "facts.yaml" in result["error"]["details"]["message"]

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
        assert "map policy: map.yaml is required" in details
        assert "Validation failed" in details

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

    def test_fails_when_code_changes_have_no_governed_evidence(self, governed_project):
        project = governed_project
        subprocess.run(["git", "init"], cwd=project, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=project, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=project, check=True, capture_output=True)

        src_dir = project / "src"
        src_dir.mkdir(exist_ok=True)
        code_file = src_dir / "app.py"
        code_file.write_text("print('v1')\n")
        subprocess.run(["git", "add", "."], cwd=project, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "baseline"], cwd=project, check=True, capture_output=True)

        code_file.write_text("print('v2')\n")
        result = haxaml_validate(str(project))
        assert result["ok"] is False
        assert result["error"]["code"] == "governance_evidence_missing"

    def test_phase_run_advisories_do_not_fail_validation(self, governed_project):
        expect_path = governed_project / ".haxaml" / "expect.yaml"
        expect = yaml.safe_load(expect_path.read_text())
        expect["phases"][0]["status"] = "done"
        expect_path.write_text(yaml.dump(expect, default_flow_style=False, sort_keys=False))

        result = haxaml_validate(str(governed_project))
        assert result["ok"] is True
        assert "Phase 'phase 1' is marked done" in _msg(result) or "planned or active" in _msg(result)


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
        session_id = _start_session_for_pack(governed_project)
        result = haxaml_context_pack(
            task="implement auth module",
            project_dir=str(governed_project),
            pack="balanced",
            include_state=True,
            session_id=session_id,
        )
        assert result["ok"] is True
        data = result["data"]
        assert data["pack"] == "balanced"
        assert data["tokens"] > 0
        assert "included_sections" in data
        assert "omitted_sections" in data
        assert "omitted_context" in data
        assert "context_window_usage" in data
        assert "context_pack" not in data

    def test_context_pack_full_detail_keeps_structured_payload(self, governed_project):
        session_id = _start_session_for_pack(governed_project)
        result = haxaml_context_pack(
            task="implement auth module",
            project_dir=str(governed_project),
            pack="balanced",
            include_state=True,
            session_id=session_id,
            detail="full",
        )
        assert result["ok"] is True
        data = result["data"]
        assert data["pack"] == "balanced"
        assert "context_window_usage" in data["context_pack"]["_meta"]
        assert "essential_facts" in data["context_pack"]
        assert "relevant_rules" in data["context_pack"]

    def test_context_pack_accepts_standard_alias(self, governed_project):
        session_id = _start_session_for_pack(governed_project)
        result = haxaml_context_pack(
            task="implement auth module",
            project_dir=str(governed_project),
            pack="standard",
            include_state=True,
            session_id=session_id,
            detail="full",
        )
        assert result["ok"] is True
        assert result["data"]["pack"] == "balanced"
        assert result["data"]["context_pack"]["pack"] == "balanced"

    def test_scaffold_context_pack_avoids_blank_rule_entries(self, fresh_project):
        session_id = _start_session_for_pack(fresh_project, task="scaffold smoke check")
        result = haxaml_context_pack(
            task="scaffold smoke check",
            project_dir=str(fresh_project),
            pack="balanced",
            include_state=True,
            session_id=session_id,
            detail="full",
        )
        assert result["ok"] is True
        rules = result["data"]["context_pack"]["relevant_rules"]
        for key in ("checks", "boundaries", "forbidden", "after_verify"):
            values = rules.get(key, [])
            assert all(isinstance(v, str) and v.strip() for v in values)


class TestDetailMode:
    def test_invalid_detail_returns_error(self, governed_project):
        result = haxaml_guidance(
            task="implement auth module",
            project_dir=str(governed_project),
            detail="verbose",
        )
        assert result["ok"] is False
        assert result["error"]["code"] == "invalid_detail"

    def test_guidance_full_detail_includes_extended_fields(self, governed_project):
        full_result = haxaml_guidance(
            task="implement auth module",
            project_dir=str(governed_project),
            detail="full",
        )
        assert full_result["ok"] is True
        assert "missing_context" in full_result["data"]


class TestHealth:
    def test_healthy_project(self, governed_project):
        result = haxaml_health(str(governed_project), detail="full")
        text = _msg(result)
        assert result["ok"] is True
        assert "Project:    test-project" in text
        assert "Ready:      " in text
        assert "Facts:      " in text
        assert result["data"]["report"]["progress_summary"]["status"] == "on_track"

    def test_missing_project(self, tmp_path):
        result = haxaml_health(str(tmp_path))
        assert result["ok"] is False

    def test_sync_pending_health_reports_not_ready(self, governed_project):
        acts_path = governed_project / ".haxaml" / "acts.yaml"
        acts = yaml.safe_load(acts_path.read_text())
        acts["runs"] = [{"id": "run-1", "task": "implement auth", "result": "success"}]
        acts["expect_sync"] = {
            "required": True,
            "pending_run_id": "run-1",
            "pending_task": "implement auth",
            "pending_result": "success",
        }
        acts_path.write_text(yaml.dump(acts, default_flow_style=False, sort_keys=False))

        result = haxaml_health(str(governed_project))
        assert result["ok"] is False
        report = result["error"]["details"]["report"]
        assert report["progress_summary"]["status"] == "sync_pending"
        assert "Derived:    sync_pending" in result["error"]["details"]["message"]


class TestDoctor:
    def test_complete_facts(self, governed_project):
        result = haxaml_doctor(str(governed_project), detail="full")
        text = _msg(result)
        assert result["ok"] is True
        assert "complete" in text or "recommendation" in text
        assert result["data"]["progress_summary"]["status"] == "on_track"

    def test_missing_facts(self, tmp_path):
        result = haxaml_doctor(str(tmp_path))
        assert result["ok"] is False
        assert "not found" in result["error"]["message"]

    def test_doctor_surfaces_stale_state_consistency_findings(self, governed_project):
        acts_path = governed_project / ".haxaml" / "acts.yaml"
        acts = yaml.safe_load(acts_path.read_text())
        acts["active_task"] = {"name": "implement auth"}
        acts["sessions"] = [
            {
                "id": "session-1",
                "task": "update docs",
                "status": "acting",
                "started": "2026-01-01T00:00:00+00:00",
            }
        ]
        acts_path.write_text(yaml.dump(acts, default_flow_style=False, sort_keys=False))

        result = haxaml_doctor(str(governed_project), detail="full")
        assert result["ok"] is True
        assert result["data"]["progress_summary"]["status"] == "stale_state"
        assert any(
            finding["code"] == "active_task_session_mismatch"
            for finding in result["data"]["consistency_findings"]
        )
