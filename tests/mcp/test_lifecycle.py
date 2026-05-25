"""Tests for the public governed lifecycle."""

import yaml

import pytest

from haxaml.acts_archive import ActsArchive
from haxaml.mcp_server import (
    haxaml_about,
    haxaml_context_fetch,
    haxaml_context_pack,
    haxaml_expect_sync,
    haxaml_guidance,
    haxaml_init,
    haxaml_needs,
    haxaml_prebuild,
    haxaml_session_record,
    haxaml_session_verify,
    haxaml_state_compact,
    haxaml_validate,
)

from .helpers import frame as _frame, read_runtime_state, write_runtime_state
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
        assert data["next_step"] == "haxaml_setup"
        assert data["lifecycle"]["preferred_next"] == "haxaml_setup"
        assert data["onboarding"]["status"] == "frame_only"
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

    def test_prebuild_blocks_when_frame_has_blocking_missing_context(self, governed_project):
        facts_path = governed_project / ".haxaml" / "facts.yaml"
        facts = yaml.safe_load(facts_path.read_text())
        facts["unresolved"] = [{"item": "API key", "reason": "not provided", "blocking": True}]
        facts_path.write_text(yaml.dump(facts, default_flow_style=False, sort_keys=False))

        assert haxaml_about(str(governed_project))["ok"] is True
        guidance = haxaml_guidance(task="update lifecycle docs", project_dir=str(governed_project))
        assert guidance["ok"] is True

        result = haxaml_prebuild(
            task="update lifecycle docs",
            description="document current flow",
            project_dir=str(governed_project),
        )

        assert result["ok"] is True
        assert result["data"]["readiness_status"] == "blocked_by_missing_context"
        assert result["data"]["session_id"] == ""

    def test_prebuild_blocks_on_structured_blocking_materials_and_questions(self, governed_project):
        expect_path = governed_project / ".haxaml" / "expect.yaml"
        expect = yaml.safe_load(expect_path.read_text())
        expect["open_questions"] = [{"question": "Which provider is approved?", "blocking": True}]
        expect_path.write_text(yaml.dump(expect, default_flow_style=False, sort_keys=False))

        facts_path = governed_project / ".haxaml" / "facts.yaml"
        facts = yaml.safe_load(facts_path.read_text())
        facts["unresolved"] = [{"item": "API key", "blocking": True, "owner": "owner"}]
        facts_path.write_text(yaml.dump(facts, default_flow_style=False, sort_keys=False))

        assert haxaml_about(str(governed_project))["ok"] is True
        assert haxaml_guidance(task="update lifecycle docs", project_dir=str(governed_project))["ok"] is True
        result = haxaml_prebuild(
            task="update lifecycle docs",
            description="document current flow",
            project_dir=str(governed_project),
            detail="full",
        )

        assert result["ok"] is True
        assert result["data"]["readiness_status"] == "blocked_by_missing_context"
        assert result["data"]["blocking_questions"] == ["Which provider is approved?"]
        assert result["data"]["blocking_materials"] == ["API key"]
        assert "API key" in result["data"]["owner_provided_materials"]

    def test_prebuild_persists_architect_inputs_into_session_state(self, governed_project):
        assert haxaml_about(str(governed_project))["ok"] is True
        guidance = haxaml_guidance(task="fix docs regression", project_dir=str(governed_project))
        assert guidance["ok"] is True

        prebuild = haxaml_prebuild(
            task="fix docs regression",
            description="repair README wording",
            project_dir=str(governed_project),
        )

        assert prebuild["ok"] is True
        session_id = prebuild["data"]["session_id"]
        acts = read_runtime_state(governed_project)
        session = next(item for item in acts["sessions"] if item["id"] == session_id)
        assert session["materials_needed"]
        assert session["done_criteria"]
        assert session["likely_impact"]

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

    def test_context_pack_rechecks_blocking_inputs_before_generation(self, governed_project):
        session_id = _start_governed_session(
            governed_project,
            task="update lifecycle guidance docs",
            description="workflow note",
        )
        facts_path = governed_project / ".haxaml" / "facts.yaml"
        facts = yaml.safe_load(facts_path.read_text())
        facts["unresolved"] = [{"item": "Missing credential", "blocking": True, "owner": "owner"}]
        facts_path.write_text(yaml.dump(facts, default_flow_style=False, sort_keys=False))

        blocked = haxaml_context_pack(
            task="update lifecycle guidance docs",
            project_dir=str(governed_project),
            pack="balanced",
            include_state=True,
            session_id=session_id,
            refresh_reason="new blocker was added",
        )
        assert blocked["ok"] is False
        assert blocked["error"]["code"] == "blocking_inputs_unresolved"

    def test_context_fetch_allows_repeated_query_driven_calls(self, governed_project):
        session_id = _start_governed_session(
            governed_project,
            task="update lifecycle guidance docs",
            description="workflow note",
        )

        first = haxaml_context_fetch(
            task="update lifecycle guidance docs",
            query="lifecycle guidance docs",
            project_dir=str(governed_project),
            session_id=session_id,
        )
        assert first["ok"] is True
        assert first["data"]["context_fetch_calls"] == 1
        assert first["data"]["lifecycle"]["preferred_next"] == "haxaml_session_verify"

        second = haxaml_context_fetch(
            task="update lifecycle guidance docs",
            query="verification rules and touched files",
            project_dir=str(governed_project),
            session_id=session_id,
        )
        assert second["ok"] is True
        assert second["data"]["context_fetch_calls"] == 2

    def test_context_fetch_returns_archived_hits(self, governed_project):
        state = read_runtime_state(governed_project)
        state["runs"] = [
            {"id": f"run-{i}", "task": f"old task {i}", "result": "success", "changes": f"archived docs change {i}", "timestamp": f"2026-01-0{i+1}T00:00:00+00:00"}
            for i in range(7)
        ]
        write_runtime_state(governed_project, state)
        archived = haxaml_state_compact(str(governed_project), keep_recent=2)
        assert archived["ok"] is True

        session_id = _start_governed_session(
            governed_project,
            task="update lifecycle guidance docs",
            description="workflow note",
        )
        fetched = haxaml_context_fetch(
            task="update lifecycle guidance docs",
            query="archived docs change",
            project_dir=str(governed_project),
            session_id=session_id,
        )
        assert fetched["ok"] is True
        assert any(hit["source"] == "archived_acts" for hit in fetched["data"]["hits"])

    def test_context_fetch_loads_only_returned_archived_records(self, governed_project, monkeypatch):
        state = read_runtime_state(governed_project)
        state["runs"] = [
            {
                "id": "run-needle",
                "task": "needle alpha beta",
                "result": "success",
                "changes": "needle alpha beta",
                "timestamp": "2026-01-01T00:00:00+00:00",
            }
        ] + [
            {
                "id": f"run-{i}",
                "task": f"cold record {i}",
                "result": "success",
                "changes": f"misc update {i}",
                "timestamp": f"2026-01-{i+2:02d}T00:00:00+00:00",
            }
            for i in range(8)
        ]
        write_runtime_state(governed_project, state)
        archived = haxaml_state_compact(str(governed_project), keep_recent=2)
        assert archived["ok"] is True

        session_id = _start_governed_session(
            governed_project,
            task="update lifecycle guidance docs",
            description="workflow note",
        )

        requested_record_batches: list[list[tuple[str, str]]] = []
        original_loader = ActsArchive.load_selected_record_details

        def counted_loader(self, records):
            requested_record_batches.append(list(records))
            return original_loader(self, records)

        monkeypatch.setattr(ActsArchive, "load_selected_record_details", counted_loader)

        fetched = haxaml_context_fetch(
            task="update lifecycle guidance docs",
            query="needle alpha beta",
            project_dir=str(governed_project),
            session_id=session_id,
            limit=1,
            sources=["archived_acts"],
            detail="full",
        )

        assert fetched["ok"] is True
        archived_hits = [hit for hit in fetched["data"]["hits"] if hit["source"] == "archived_acts"]
        assert len(archived_hits) == 1
        assert archived_hits[0]["id"] == "run-needle"
        assert archived_hits[0]["details"]["changes"] == "needle alpha beta"
        assert requested_record_batches == [[("run", "run-needle")]]

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
        assert "handoff_summary" in data

    @pytest.mark.skip(reason="handoff pressure from runtime state moves to the FRAME brain slice")
    def test_guidance_and_prebuild_surface_handoff_summary(self, governed_project):
        acts = read_runtime_state(governed_project)
        acts["continuity"] = {
            "recent_decisions": [{"decision": "keep flow scoped", "reasoning": "avoid regressions"}],
            "current_blockers": [{"name": "API key", "reason": "owner missing"}],
            "recent_failures": [{"task": "prior task", "result": "failed", "summary": "missing setup"}],
            "context_pressure": {"status": "tight", "hot_bytes": 1000, "max_hot_bytes": 1200},
        }
        acts["context_compaction"] = {"last_pack_tokens": 4200, "last_window_usage": {"pct_4000": 105.0, "pct_8000": 52.5}}
        write_runtime_state(governed_project, acts)

        about = haxaml_about(str(governed_project))
        assert about["ok"] is True
        guidance = haxaml_guidance(task="update lifecycle guidance docs", project_dir=str(governed_project))
        assert guidance["ok"] is True
        assert guidance["data"]["handoff_summary"]["current_blockers"]

        prebuild = haxaml_prebuild(
            task="update lifecycle guidance docs",
            description="workflow note",
            project_dir=str(governed_project),
            detail="full",
        )
        assert prebuild["ok"] is True
        assert "Recent context pack" in prebuild["data"]["handoff_summary"]["context_pressure_summary"]

    def test_lifecycle_tools_point_to_next_step(self, governed_project):
        about = haxaml_about(str(governed_project))
        assert about["ok"] is True
        assert about["data"]["lifecycle"]["preferred_next"] == "haxaml_setup"

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

    @pytest.mark.skip(reason="0.8.0 frontmatter slice has no expect runbook dependency body yet")
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

    @pytest.mark.skip(reason="map/expect body derivation checks resume after body schemas are reintroduced")
    def test_session_record_blocks_success_when_derivation_conflicts_exist(self, governed_project):
        map_data = {
            "frame": _frame("map", "repo_context_map"),
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

    @pytest.mark.skip(reason="expect-sync validation moves to runtime brain work after the 0.8.0 frontmatter slice")
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

    @pytest.mark.skip(reason="0.8.0 frontmatter slice has no expect runbook body yet")
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

    @pytest.mark.skip(reason="0.8.0 frontmatter slice has no expect runbook body yet")
    def test_expect_sync_success_auto_appends_next_run_when_runbook_ends(self, governed_project):
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
        assert record_first["data"]["run_id"].startswith("run-")
        sync_first = haxaml_expect_sync(project_dir=str(governed_project))
        assert sync_first["ok"] is True
        assert sync_first["data"]["run"] == 1
        assert sync_first["data"]["appended_run"] == 2

        expect = yaml.safe_load((governed_project / ".haxaml" / "expect.yaml").read_text())
        runbook = {item["run"]: item for item in expect["runbook"]}
        assert runbook[1]["status"] == "done"
        assert runbook[2]["status"] == "active"

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
        record_second = haxaml_session_record(
            task="task two",
            result="success",
            session_id=second_id,
            project_dir=str(governed_project),
            changes="Second run done",
        )
        assert record_second["ok"] is True
        sync_second = haxaml_expect_sync(project_dir=str(governed_project))
        assert sync_second["ok"] is True
        assert sync_second["data"]["run"] == 2
        assert sync_second["data"]["appended_run"] == 3

    def test_expect_sync_partial_keeps_same_run_active(self, governed_project):
        session_id = _start_governed_session(governed_project, task="task partial", description="partial slice")
        verify = haxaml_session_verify(
            task="task partial",
            project_dir=str(governed_project),
            session_id=session_id,
            inspected_context=[".haxaml/facts.yaml", ".haxaml/rules.yaml"],
            changed_files=["src/partial.py"],
            summary="Partial progress verified.",
        )
        assert verify["ok"] is True
        record = haxaml_session_record(
            task="task partial",
            result="partial",
            session_id=session_id,
            project_dir=str(governed_project),
            changes="Partial progress",
        )
        assert record["ok"] is True

        sync = haxaml_expect_sync(project_dir=str(governed_project))
        assert sync["ok"] is True
        assert sync["data"]["run"] == 1
        assert sync["data"]["applied_status"] == "active"
        assert sync["data"]["appended_run"] == 0
        expect = yaml.safe_load((governed_project / ".haxaml" / "expect.yaml").read_text())
        assert len(expect["runbook"]) == 1
        assert expect["runbook"][0]["status"] == "active"

    def test_expect_sync_failed_blocks_current_run_without_append(self, governed_project):
        session_id = _start_governed_session(governed_project, task="task blocked", description="blocked slice")
        record = haxaml_session_record(
            task="task blocked",
            result="failed",
            session_id=session_id,
            project_dir=str(governed_project),
            changes="Stopped before implementation",
            risks="Missing required material",
        )
        assert record["ok"] is True

        sync = haxaml_expect_sync(project_dir=str(governed_project))
        assert sync["ok"] is True
        assert sync["data"]["run"] == 1
        assert sync["data"]["applied_status"] == "blocked"
        assert sync["data"]["appended_run"] == 0
        expect = yaml.safe_load((governed_project / ".haxaml" / "expect.yaml").read_text())
        assert len(expect["runbook"]) == 1
        assert expect["runbook"][0]["status"] == "blocked"

    @pytest.mark.skip(reason="0.8.0 frontmatter slice has no expect runbook body yet")
    def test_expect_sync_prefers_stored_run_number_before_active_inference(self, governed_project):
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

        sync = haxaml_expect_sync(project_dir=str(governed_project))
        assert sync["ok"] is True
        assert sync["data"]["run"] == 1
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

    @pytest.mark.skip(reason="0.8.0 frontmatter slice has no expect runbook body yet")
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

    @pytest.mark.skip(reason="map/expect body derivation checks resume after body schemas are reintroduced")
    def test_session_record_failed_requires_explicit_conflict_reason(self, governed_project):
        map_data = {
            "frame": _frame("map", "repo_context_map"),
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
