"""Tests for the public governed lifecycle."""

import yaml

from haxaml.mcp_server import (
    haxaml_about,
    haxaml_context_pack,
    haxaml_expect_sync,
    haxaml_guidance,
    haxaml_init,
    haxaml_needs,
    haxaml_prebuild,
    haxaml_session_record,
    haxaml_session_verify,
    haxaml_validate,
)

from .helpers import msg as _msg


def _start_governed_session(
    project_dir,
    task: str = "update lifecycle guidance docs",
    description: str = "workflow note",
) -> str:
    guided = haxaml_guidance(task=task, project_dir=str(project_dir))
    assert guided["ok"] is True
    prebuild = haxaml_prebuild(
        task=task,
        description=description,
        project_dir=str(project_dir),
    )
    assert prebuild["ok"] is True
    session_id = prebuild["data"]["session_id"]
    assert session_id
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

    def test_prebuild_requires_about_first(self, tmp_path):
        init = haxaml_init(str(tmp_path))
        assert init["ok"] is True
        result = haxaml_prebuild(
            task="update lifecycle guidance docs",
            description="refresh workflow text",
            project_dir=str(tmp_path),
        )
        assert result["ok"] is False
        assert result["error"]["code"] == "about_required"

    def test_about_allows_multiple_prebuild_sessions_in_same_runtime(self, tmp_path):
        init = haxaml_init(str(tmp_path))
        assert init["ok"] is True
        assert haxaml_about(str(tmp_path))["ok"] is True

        first_id = _start_governed_session(
            tmp_path,
            task="update lifecycle guidance docs",
            description="workflow note",
        )
        verify_first = haxaml_session_verify(
            task="update lifecycle guidance docs",
            project_dir=str(tmp_path),
            session_id=first_id,
            inspected_context=[".haxaml/facts.yaml", ".haxaml/rules.yaml", ".haxaml/acts.yaml"],
            changed_files=["docs/lifecycle.md"],
            summary="Updated lifecycle guidance.",
        )
        assert verify_first["ok"] is True
        record_first = haxaml_session_record(
            task="update lifecycle guidance docs",
            result="success",
            session_id=first_id,
            project_dir=str(tmp_path),
            changes="Updated lifecycle docs",
        )
        assert record_first["ok"] is True
        synced = haxaml_expect_sync(project_dir=str(tmp_path))
        assert synced["ok"] is True

        guided_second = haxaml_guidance(task="update prebuild docs", project_dir=str(tmp_path))
        assert guided_second["ok"] is True
        second = haxaml_prebuild(
            task="update prebuild docs",
            description="document canonical flow",
            project_dir=str(tmp_path),
        )
        assert second["ok"] is True
        assert second["data"]["session_id"]


class TestLifecycle:
    def test_guidance_classifies_and_scores_risk(self, governed_project):
        result = haxaml_guidance(task="migrate auth database", project_dir=str(governed_project))
        assert result["ok"] is True
        assert result["data"]["task_type"] in ("implementation", "debug", "design", "strategy", "outcome")
        assert result["data"]["risk_level"] in ("low", "medium", "high")

    def test_prebuild_rejects_utility_mode_tasks(self, governed_project):
        guided = haxaml_guidance(task="sort files in this folder", project_dir=str(governed_project))
        assert guided["ok"] is True
        assert guided["data"]["execution_mode"] == "utility"
        assert guided["data"]["next_step"] == "run_outside_governed_flow"

        result = haxaml_prebuild(
            task="sort files in this folder",
            description="side task",
            project_dir=str(governed_project),
        )
        assert result["ok"] is True
        assert result["data"]["readiness_status"] == "utility_mode"

    def test_governed_flow_prebuild_context_verify_record(self, governed_project):
        session_id = _start_governed_session(
            governed_project,
            task="update lifecycle guidance docs",
            description="workflow note",
        )

        verify = haxaml_session_verify(
            task="update lifecycle guidance docs",
            project_dir=str(governed_project),
            session_id=session_id,
            inspected_context=[".haxaml/facts.yaml", ".haxaml/rules.yaml"],
            changed_files=["docs/lifecycle.md"],
            summary="Updated lifecycle guidance and validation notes.",
        )
        assert verify["ok"] is True
        assert verify["data"]["verification_id"].startswith("verify-")
        assert verify["data"]["verdict"] in ("pass", "pass_with_risks")

        record = haxaml_session_record(
            task="update lifecycle guidance docs",
            result="success",
            session_id=session_id,
            project_dir=str(governed_project),
            changes="Updated lifecycle docs",
            decisions="Kept canonical flow wording",
            risks="Need one more pass on examples",
        )
        assert record["ok"] is True
        assert record["data"]["run_id"].startswith("run-")
        assert "last_pack_tokens" in record["data"]
        assert "last_context_window_usage" in record["data"]

    def test_context_pack_repeat_requires_refresh_reason(self, governed_project):
        session_id = _start_governed_session(
            governed_project,
            task="update lifecycle guidance docs",
            description="workflow note",
        )

        second = haxaml_context_pack(
            task="update lifecycle guidance docs",
            project_dir=str(governed_project),
            pack="balanced",
            include_state=True,
            session_id=session_id,
        )
        assert second["ok"] is False
        assert second["error"]["code"] == "context_pack_refresh_reason_required"

        vague = haxaml_context_pack(
            task="update lifecycle guidance docs",
            project_dir=str(governed_project),
            pack="balanced",
            include_state=True,
            session_id=session_id,
            refresh_reason="again",
        )
        assert vague["ok"] is False
        assert vague["error"]["code"] == "context_pack_refresh_reason_too_vague"

        third = haxaml_context_pack(
            task="update lifecycle guidance docs",
            project_dir=str(governed_project),
            pack="balanced",
            include_state=True,
            session_id=session_id,
            refresh_reason="context stale after updated tests",
        )
        assert third["ok"] is True
        assert third["data"]["refresh_reason_category"] == "stale_context"

    def test_prebuild_short_response_is_compact(self, governed_project):
        assert haxaml_about(str(governed_project))["ok"] is True
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

        assert haxaml_about(str(governed_project))["ok"] is True
        assert haxaml_guidance(task="update lifecycle guidance docs", project_dir=str(governed_project))["ok"] is True

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
        task = "update lifecycle guidance docs"
        session_id = _start_governed_session(governed_project, task=task, description="workflow note")

        record = haxaml_session_record(
            task=task,
            result="success",
            session_id=session_id,
            project_dir=str(governed_project),
            changes="Updated lifecycle guidance docs",
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

        session_id = _start_governed_session(
            governed_project,
            task="update governance notes",
            description="document workflow changes",
        )
        verify = haxaml_session_verify(
            task="update governance notes",
            project_dir=str(governed_project),
            session_id=session_id,
            inspected_context=[".haxaml/facts.yaml", ".haxaml/rules.yaml"],
            changed_files=["docs/governance.md"],
            summary="Updated governance notes and validation checks.",
        )
        assert verify["ok"] is True

        record = haxaml_session_record(
            task="update governance notes",
            result="success",
            session_id=session_id,
            project_dir=str(governed_project),
            changes="Updated governance notes",
            decisions="Kept canonical session flow",
            risks="Need one more wording review",
        )
        assert record["ok"] is False
        assert record["error"]["code"] == "derivation_conflicts"

    def test_record_sets_expect_sync_and_validate_blocks_until_synced(self, governed_project):
        session_id = _start_governed_session(
            governed_project,
            task="update governance notes",
            description="document workflow changes",
        )
        verify = haxaml_session_verify(
            task="update governance notes",
            project_dir=str(governed_project),
            session_id=session_id,
            inspected_context=[".haxaml/facts.yaml", ".haxaml/rules.yaml"],
            changed_files=["docs/governance.md"],
            summary="Updated governance flow.",
        )
        assert verify["ok"] is True

        record = haxaml_session_record(
            task="update governance notes",
            result="success",
            session_id=session_id,
            project_dir=str(governed_project),
            changes="Updated governance notes",
            decisions="Kept sync flow explicit",
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
            task="update governance notes",
            description="document workflow changes",
        )
        verify = haxaml_session_verify(
            task="update governance notes",
            project_dir=str(governed_project),
            session_id=session_id,
            inspected_context=[".haxaml/facts.yaml", ".haxaml/rules.yaml"],
            changed_files=["docs/governance.md"],
            summary="Updated governance flow.",
        )
        assert verify["ok"] is True
        record = haxaml_session_record(
            task="update governance notes",
            result="success",
            session_id=session_id,
            project_dir=str(governed_project),
            changes="Updated governance notes",
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

    def test_guidance_blocks_until_expect_sync_is_complete(self, governed_project):
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

        synced = haxaml_expect_sync(project_dir=str(governed_project))
        assert synced["ok"] is True

        guided_after_sync = haxaml_guidance(task="task two", project_dir=str(governed_project))
        assert guided_after_sync["ok"] is True

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
            task="update governance notes",
            description="document workflow changes",
        )

        denied = haxaml_session_record(
            task="update governance notes",
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
            task="update governance notes",
            result="failed",
            session_id=session_id,
            project_dir=str(governed_project),
            changes="Stopped due to derivation conflict",
            decisions="Reconcile required before continuing",
            risks="map mismatch unresolved",
        )
        assert allowed["ok"] is True
