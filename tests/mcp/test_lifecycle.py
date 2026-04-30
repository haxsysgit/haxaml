"""Tests for MCP lifecycle tools."""

import yaml

from haxaml.mcp_server import (
    haxaml_about,
    haxaml_done,
    haxaml_expect_sync,
    haxaml_guidance,
    haxaml_init,
    haxaml_needs,
    haxaml_run,
    haxaml_session_plan,
    haxaml_session_record,
    haxaml_session_start,
    haxaml_session_verify,
    haxaml_validate,
)

from .helpers import msg as _msg


class TestAbout:
    def test_about_returns_onboarding_payload(self, fresh_project):
        result = haxaml_about(str(fresh_project))
        assert result["ok"] is True
        data = result["data"]
        assert data["about_version"]
        assert "lean_workflow" in data
        assert "call_budget_targets" in data

    def test_session_start_requires_about_first(self, tmp_path):
        init = haxaml_init(str(tmp_path))
        assert init["ok"] is True
        result = haxaml_session_start(
            task="implement auth module",
            description="add login endpoint",
            project_dir=str(tmp_path),
        )
        assert result["ok"] is False
        assert result["error"]["code"] == "about_required"

    def test_session_start_repeated_about_missing_is_retry_blocked(self, tmp_path):
        init = haxaml_init(str(tmp_path))
        assert init["ok"] is True

        first = haxaml_session_start(
            task="implement auth module",
            description="add login endpoint",
            project_dir=str(tmp_path),
        )
        assert first["ok"] is False
        assert first["error"]["code"] == "about_required"

        second = haxaml_session_start(
            task="implement auth module",
            description="add login endpoint",
            project_dir=str(tmp_path),
        )
        assert second["ok"] is False
        assert second["error"]["code"] == "retry_policy_blocked"

    def test_about_allows_multiple_session_starts_in_same_runtime(self, tmp_path):
        init = haxaml_init(str(tmp_path))
        assert init["ok"] is True

        about = haxaml_about(str(tmp_path))
        assert about["ok"] is True

        first_start = haxaml_session_start(
            task="implement auth module",
            description="add login endpoint",
            project_dir=str(tmp_path),
        )
        assert first_start["ok"] is True

        second_start = haxaml_session_start(
            task="implement billing module",
            description="add payment endpoint",
            project_dir=str(tmp_path),
        )
        assert second_start["ok"] is True


class TestRunDone:
    def test_start_run(self, governed_project):
        result = haxaml_run("test task", description="testing", project_dir=str(governed_project))
        assert result["ok"] is True
        assert "Run started" in _msg(result)

    def test_complete_run(self, governed_project):
        haxaml_run("test task", project_dir=str(governed_project))
        result = haxaml_done(
            "test task",
            result="success",
            changes="did things",
            decisions="chose X",
            risks="none",
            project_dir=str(governed_project),
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
        assert "last_pack_tokens" in record["data"]
        assert "last_context_window_usage" in record["data"]

    def test_session_start_rejects_utility_mode_tasks(self, governed_project):
        result = haxaml_session_start(
            task="sort files in this folder",
            description="side task",
            project_dir=str(governed_project),
        )
        assert result["ok"] is False
        assert result["error"]["code"] == "utility_mode_task"

    def test_context_pack_repeat_requires_refresh_reason(self, governed_project):
        from haxaml.mcp_server import haxaml_context_pack

        started = haxaml_session_start(
            task="implement auth module",
            description="add login endpoint",
            project_dir=str(governed_project),
        )
        assert started["ok"] is True
        session_id = started["data"]["session_id"]

        first = haxaml_context_pack(
            task="implement auth module",
            project_dir=str(governed_project),
            pack="balanced",
            include_state=True,
            session_id=session_id,
        )
        assert first["ok"] is True

        second = haxaml_context_pack(
            task="implement auth module",
            project_dir=str(governed_project),
            pack="balanced",
            include_state=True,
            session_id=session_id,
        )
        assert second["ok"] is False
        assert second["error"]["code"] == "context_pack_refresh_reason_required"

        third = haxaml_context_pack(
            task="implement auth module",
            project_dir=str(governed_project),
            pack="balanced",
            include_state=True,
            session_id=session_id,
            refresh_reason="context stale after updated tests",
        )
        assert third["ok"] is True

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

    def test_session_plan_filters_blank_verify_expectations(self, governed_project):
        rules_path = governed_project / ".haxaml" / "rules.yaml"
        rules = yaml.safe_load(rules_path.read_text())
        rules["after_task"]["verify"] = ["", "Run unit tests"]
        rules_path.write_text(yaml.dump(rules, default_flow_style=False, sort_keys=False))

        started = haxaml_session_start(
            task="test verify filtering",
            description="verify list cleanup",
            project_dir=str(governed_project),
        )
        assert started["ok"] is True

        planned = haxaml_session_plan(
            session_id=started["data"]["session_id"],
            project_dir=str(governed_project),
        )
        assert planned["ok"] is True
        assert planned["data"]["verification_expectations"] == ["Run unit tests"]

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

    def test_record_sets_expect_sync_and_validate_blocks_until_synced(self, governed_project):
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
            summary="Implemented login flow.",
        )
        assert verify["ok"] is True

        record = haxaml_session_record(
            task="implement auth module",
            result="success",
            session_id=session_id,
            project_dir=str(governed_project),
            changes="Added auth endpoints",
            decisions="Used existing signer",
            risks="none",
        )
        assert record["ok"] is True
        assert record["data"]["expect_sync_required"] is True

        blocked_validate = haxaml_validate(project_dir=str(governed_project))
        assert blocked_validate["ok"] is False
        assert blocked_validate["error"]["code"] == "lifecycle_drift"

        needs = haxaml_needs(project_dir=str(governed_project))
        assert needs["ok"] is True
        assert "Blocking lifecycle sync" in _msg(needs)

        synced = haxaml_expect_sync(project_dir=str(governed_project))
        assert synced["ok"] is True
        assert synced["data"]["synced"] is True

        validated = haxaml_validate(project_dir=str(governed_project))
        assert validated["ok"] is True

    def test_expect_sync_success_activates_next_runnable_run(self, governed_project):
        expect_path = governed_project / ".haxaml" / "expect.yaml"
        expect = yaml.safe_load(expect_path.read_text())
        expect["runbook"].append(
            {
                "run": 2,
                "phase": "Phase 1",
                "status": "planned",
                "goal": "Next run",
                "outcome": "Second slice done",
                "depends_on": [1],
                "touches": ["api"],
                "requires": [],
                "uses_map": False,
                "verify": ["haxaml validate"],
                "done_when": "Done",
            }
        )
        expect_path.write_text(yaml.dump(expect, default_flow_style=False, sort_keys=False))

        started = haxaml_session_start(
            task="implement auth module",
            description="add login endpoint",
            project_dir=str(governed_project),
        )
        assert started["ok"] is True

        verify = haxaml_session_verify(
            task="implement auth module",
            project_dir=str(governed_project),
            session_id=started["data"]["session_id"],
            inspected_context=[".haxaml/facts.yaml", ".haxaml/rules.yaml"],
            changed_files=["src/auth.py"],
            summary="Implemented login flow.",
        )
        assert verify["ok"] is True

        record = haxaml_session_record(
            task="implement auth module",
            result="success",
            session_id=started["data"]["session_id"],
            project_dir=str(governed_project),
            changes="Added auth endpoints",
        )
        assert record["ok"] is True

        sync = haxaml_expect_sync(project_dir=str(governed_project))
        assert sync["ok"] is True
        assert sync["data"]["run"] == 1
        assert sync["data"]["applied_status"] == "done"

        updated = yaml.safe_load(expect_path.read_text())
        runbook = {item["run"]: item for item in updated["runbook"]}
        assert runbook[1]["status"] == "done"
        assert runbook[2]["status"] == "active"

    def test_session_start_warns_and_record_blocks_when_expect_sync_pending(self, governed_project):
        first = haxaml_session_start(
            task="task one",
            description="first slice",
            project_dir=str(governed_project),
        )
        assert first["ok"] is True

        verify_first = haxaml_session_verify(
            task="task one",
            project_dir=str(governed_project),
            session_id=first["data"]["session_id"],
            inspected_context=[".haxaml/facts.yaml", ".haxaml/rules.yaml"],
            changed_files=["src/one.py"],
            summary="Done first slice.",
        )
        assert verify_first["ok"] is True

        record_first = haxaml_session_record(
            task="task one",
            result="success",
            session_id=first["data"]["session_id"],
            project_dir=str(governed_project),
            changes="First run done",
        )
        assert record_first["ok"] is True

        second = haxaml_session_start(
            task="task two",
            description="second slice",
            project_dir=str(governed_project),
        )
        assert second["ok"] is True
        assert second["warnings"]
        assert "Expect sync is pending" in second["warnings"][0]

        verify_second = haxaml_session_verify(
            task="task two",
            project_dir=str(governed_project),
            session_id=second["data"]["session_id"],
            inspected_context=[".haxaml/facts.yaml", ".haxaml/rules.yaml"],
            changed_files=["src/two.py"],
            summary="Done second slice.",
        )
        assert verify_second["ok"] is True

        blocked_record = haxaml_session_record(
            task="task two",
            result="success",
            session_id=second["data"]["session_id"],
            project_dir=str(governed_project),
            changes="Second run done",
        )
        assert blocked_record["ok"] is False
        assert blocked_record["error"]["code"] == "expect_sync_required"

    def test_expect_sync_requires_explicit_run_when_active_run_is_ambiguous(self, governed_project):
        expect_path = governed_project / ".haxaml" / "expect.yaml"
        expect = yaml.safe_load(expect_path.read_text())
        expect["runbook"].append(
            {
                "run": 2,
                "phase": "Phase 1",
                "status": "active",
                "goal": "Competing active run",
                "outcome": "N/A",
                "depends_on": [],
                "touches": ["api"],
                "requires": [],
                "uses_map": False,
                "verify": ["haxaml validate"],
                "done_when": "Done",
            }
        )
        expect_path.write_text(yaml.dump(expect, default_flow_style=False, sort_keys=False))

        started = haxaml_session_start(task="task one", description="first slice", project_dir=str(governed_project))
        assert started["ok"] is True
        verify = haxaml_session_verify(
            task="task one",
            project_dir=str(governed_project),
            session_id=started["data"]["session_id"],
            inspected_context=[".haxaml/facts.yaml", ".haxaml/rules.yaml"],
            changed_files=["src/one.py"],
            summary="Done first slice.",
        )
        assert verify["ok"] is True
        record = haxaml_session_record(
            task="task one",
            result="success",
            session_id=started["data"]["session_id"],
            project_dir=str(governed_project),
            changes="First run done",
        )
        assert record["ok"] is True

        ambiguous = haxaml_expect_sync(project_dir=str(governed_project))
        assert ambiguous["ok"] is False
        assert ambiguous["error"]["code"] == "ambiguous_active_run"

        explicit = haxaml_expect_sync(project_dir=str(governed_project), run=1)
        assert explicit["ok"] is True

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
