"""Tests for MCP lifecycle tools."""

import yaml

from haxaml.mcp_server import (
    haxaml_about,
    haxaml_context_pack,
    haxaml_done,
    haxaml_expect_sync,
    haxaml_guidance,
    haxaml_init,
    haxaml_prebuild,
    haxaml_needs,
    haxaml_run,
    haxaml_session_plan,
    haxaml_session_record,
    haxaml_session_start,
    haxaml_session_verify,
    haxaml_validate,
)

from .helpers import msg as _msg


def _start_governed_session(project_dir, task: str, description: str = "") -> str:
    guided = haxaml_guidance(task=task, project_dir=str(project_dir))
    assert guided["ok"] is True
    started = haxaml_session_start(task=task, description=description, project_dir=str(project_dir))
    assert started["ok"] is True
    session_id = started["data"]["session_id"]
    planned = haxaml_session_plan(session_id=session_id, project_dir=str(project_dir))
    assert planned["ok"] is True
    packed = haxaml_context_pack(
        task=task,
        project_dir=str(project_dir),
        pack="balanced",
        include_state=True,
        session_id=session_id,
    )
    assert packed["ok"] is True
    return session_id


class TestAbout:
    def test_about_returns_onboarding_payload(self, fresh_project):
        result = haxaml_about(str(fresh_project))
        assert result["ok"] is True
        data = result["data"]
        assert data["about_version"]
        assert "lean_workflow" in data
        assert data["next_step"] == "haxaml_guidance"
        assert data["lifecycle"]["preferred_next"] == "haxaml_guidance"
        assert "allowed_next" not in data["lifecycle"]

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

        guided_first = haxaml_guidance(task="implement auth module", project_dir=str(tmp_path))
        assert guided_first["ok"] is True
        first_start = haxaml_session_start(
            task="implement auth module",
            description="add login endpoint",
            project_dir=str(tmp_path),
        )
        assert first_start["ok"] is True

        planned_first = haxaml_session_plan(session_id=first_start["data"]["session_id"], project_dir=str(tmp_path))
        assert planned_first["ok"] is True
        packed_first = haxaml_context_pack(
            task="implement auth module",
            project_dir=str(tmp_path),
            pack="minimal",
            include_state=True,
            session_id=first_start["data"]["session_id"],
        )
        assert packed_first["ok"] is True

        verify_first = haxaml_session_verify(
            task="implement auth module",
            project_dir=str(tmp_path),
            session_id=first_start["data"]["session_id"],
            inspected_context=[".haxaml/facts.yaml", ".haxaml/rules.yaml", ".haxaml/acts.yaml"],
            changed_files=["src/auth.py"],
            summary="Initial auth implementation.",
        )
        assert verify_first["ok"] is True
        record_first = haxaml_session_record(
            task="implement auth module",
            result="success",
            session_id=first_start["data"]["session_id"],
            project_dir=str(tmp_path),
            changes="Added auth endpoint",
        )
        assert record_first["ok"] is True
        synced = haxaml_expect_sync(project_dir=str(tmp_path))
        assert synced["ok"] is True

        guided_second = haxaml_guidance(task="implement billing module", project_dir=str(tmp_path))
        assert guided_second["ok"] is True
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
    def test_session_start_requires_guidance_step(self, governed_project):
        result = haxaml_session_start(
            task="implement auth module",
            description="add login endpoint",
            project_dir=str(governed_project),
        )
        assert result["ok"] is False
        assert result["error"]["code"] == "lifecycle_contract_violation"

    def test_guidance_classifies_and_scores_risk(self, governed_project):
        result = haxaml_guidance(task="migrate auth database", project_dir=str(governed_project))
        assert result["ok"] is True
        assert result["data"]["task_type"] in ("implementation", "debug", "design", "strategy", "outcome")
        assert result["data"]["risk_level"] in ("low", "medium", "high")

    def test_session_flow_start_plan_verify_record(self, governed_project):
        session_id = _start_governed_session(
            governed_project,
            task="implement auth module",
            description="add login endpoint",
        )

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
        guided = haxaml_guidance(task="sort files in this folder", project_dir=str(governed_project))
        assert guided["ok"] is True
        assert guided["data"]["execution_mode"] == "utility"
        assert guided["data"]["next_step"] == "run_outside_governed_flow"
        assert "call_budget" not in guided["data"]
        result = haxaml_session_start(
            task="sort files in this folder",
            description="side task",
            project_dir=str(governed_project),
        )
        assert result["ok"] is False
        assert result["error"]["code"] == "utility_mode_task"

    def test_context_pack_repeat_requires_refresh_reason(self, governed_project):
        guided = haxaml_guidance(task="implement auth module", project_dir=str(governed_project))
        assert guided["ok"] is True
        started = haxaml_session_start(
            task="implement auth module",
            description="add login endpoint",
            project_dir=str(governed_project),
        )
        assert started["ok"] is True
        session_id = started["data"]["session_id"]

        planned = haxaml_session_plan(session_id=session_id, project_dir=str(governed_project))
        assert planned["ok"] is True

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

        vague = haxaml_context_pack(
            task="implement auth module",
            project_dir=str(governed_project),
            pack="balanced",
            include_state=True,
            session_id=session_id,
            refresh_reason="again",
        )
        assert vague["ok"] is False
        assert vague["error"]["code"] == "context_pack_refresh_reason_too_vague"

        third = haxaml_context_pack(
            task="implement auth module",
            project_dir=str(governed_project),
            pack="balanced",
            include_state=True,
            session_id=session_id,
            refresh_reason="context stale after updated tests",
        )
        assert third["ok"] is True
        assert third["data"]["refresh_reason_category"] == "stale_context"

    def test_prebuild_short_response_is_compact(self, governed_project):
        about = haxaml_about(str(governed_project))
        assert about["ok"] is True
        guided = haxaml_guidance(task="update lifecycle guidance docs", project_dir=str(governed_project))
        assert guided["ok"] is True

        prebuild = haxaml_prebuild(
            task="update lifecycle guidance docs",
            description="workflow benchmark profile",
            project_dir=str(governed_project),
        )
        assert prebuild["ok"] is True
        data = prebuild["data"]
        assert data["readiness_status"] in ("ready_to_build", "ready_to_build_with_warnings")
        assert data["next_step"] == "haxaml_context_pack"
        assert data["lifecycle"]["preferred_next"] == "haxaml_context_pack"
        assert "frame_health" not in data
        assert "plan" not in data

    def test_lifecycle_tools_point_to_next_step(self, governed_project):
        about = haxaml_about(str(governed_project))
        assert about["ok"] is True
        assert about["data"]["lifecycle"]["preferred_next"] == "haxaml_guidance"

        guidance = haxaml_guidance(task="update lifecycle guidance docs", project_dir=str(governed_project))
        assert guidance["ok"] is True
        assert guidance["data"]["lifecycle"]["preferred_next"] == "haxaml_prebuild"

        prebuild = haxaml_prebuild(
            task="update lifecycle guidance docs",
            description="workflow benchmark profile",
            project_dir=str(governed_project),
        )
        assert prebuild["ok"] is True
        session_id = prebuild["data"]["session_id"]
        assert prebuild["data"]["lifecycle"]["preferred_next"] == "haxaml_context_pack"

        packed = haxaml_context_pack(
            task="update lifecycle guidance docs",
            project_dir=str(governed_project),
            pack="balanced",
            include_state=True,
            session_id=session_id,
        )
        assert packed["ok"] is True
        assert packed["data"]["lifecycle"]["preferred_next"] == "haxaml_session_verify"

    def test_prebuild_surfaces_blocked_progress_as_warning(self, governed_project):
        expect_path = governed_project / ".haxaml" / "expect.yaml"
        expect = yaml.safe_load(expect_path.read_text())
        expect["runbook"][0]["depends_on"] = [99]
        expect_path.write_text(yaml.dump(expect, default_flow_style=False, sort_keys=False))

        about = haxaml_about(str(governed_project))
        assert about["ok"] is True
        guided = haxaml_guidance(task="update lifecycle guidance docs", project_dir=str(governed_project))
        assert guided["ok"] is True

        prebuild = haxaml_prebuild(
            task="update lifecycle guidance docs",
            description="workflow note",
            project_dir=str(governed_project),
            detail="full",
        )
        assert prebuild["ok"] is True
        assert prebuild["data"]["progress_summary"]["status"] == "blocked"
        assert prebuild["data"]["readiness_status"] == "ready_to_build_with_warnings"
        assert "Progress: blocked" in prebuild["data"]["message"]

    def test_session_record_requires_verification_for_success(self, governed_project):
        session_id = _start_governed_session(
            governed_project,
            task="add billing flow",
            description="payment integration",
        )

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

        guided = haxaml_guidance(task="test verify filtering", project_dir=str(governed_project))
        assert guided["ok"] is True
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

        session_id = _start_governed_session(
            governed_project,
            task="implement auth module",
            description="add login endpoint",
        )

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
        session_id = _start_governed_session(
            governed_project,
            task="implement auth module",
            description="add login endpoint",
        )

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

        session_id = _start_governed_session(
            governed_project,
            task="implement auth module",
            description="add login endpoint",
        )

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
        first_id = _start_governed_session(governed_project, task="task one", description="first slice")

        verify_first = haxaml_session_verify(
            task="task one",
            project_dir=str(governed_project),
            session_id=first_id,
            inspected_context=[".haxaml/facts.yaml", ".haxaml/rules.yaml"],
            changed_files=["src/one.py"],
            summary="Done first slice.",
        )
        assert verify_first["ok"] is True

        record_first = haxaml_session_record(
            task="task one",
            result="success",
            session_id=first_id,
            project_dir=str(governed_project),
            changes="First run done",
        )
        assert record_first["ok"] is True

        guided_second = haxaml_guidance(task="task two", project_dir=str(governed_project))
        assert guided_second["ok"] is False
        assert guided_second["error"]["code"] == "lifecycle_contract_violation"

        second = haxaml_session_start(
            task="task two",
            description="second slice",
            project_dir=str(governed_project),
        )
        assert second["ok"] is False
        assert second["error"]["code"] == "lifecycle_contract_violation"

        synced = haxaml_expect_sync(project_dir=str(governed_project))
        assert synced["ok"] is True

        second_id = _start_governed_session(governed_project, task="task two", description="second slice")

        verify_second = haxaml_session_verify(
            task="task two",
            project_dir=str(governed_project),
            session_id=second_id,
            inspected_context=[".haxaml/facts.yaml", ".haxaml/rules.yaml"],
            changed_files=["src/two.py"],
            summary="Done second slice.",
        )
        assert verify_second["ok"] is True

        blocked_record = haxaml_session_record(
            task="task two",
            result="success",
            session_id=second_id,
            project_dir=str(governed_project),
            changes="Second run done",
        )
        assert blocked_record["ok"] is True

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

        session_id = _start_governed_session(governed_project, task="task one", description="first slice")
        verify = haxaml_session_verify(
            task="task one",
            project_dir=str(governed_project),
            session_id=session_id,
            inspected_context=[".haxaml/facts.yaml", ".haxaml/rules.yaml"],
            changed_files=["src/one.py"],
            summary="Done first slice.",
        )
        assert verify["ok"] is True
        record = haxaml_session_record(
            task="task one",
            result="success",
            session_id=session_id,
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

        session_id = _start_governed_session(
            governed_project,
            task="implement auth module",
            description="add login endpoint",
        )

        denied = haxaml_session_record(
            task="implement auth module",
            result="failed",
            session_id=session_id,
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
            session_id=session_id,
            project_dir=str(governed_project),
            changes="Stopped due to derivation conflict",
            decisions="Reconcile required before continuing",
            risks="map mismatch unresolved",
        )
        assert allowed["ok"] is True
