"""Tests for incremental context pack refresh behavior."""

import yaml

from haxaml.mcp_server import haxaml_context_pack, haxaml_guidance, haxaml_prebuild


def _start_session(project_dir, task: str) -> str:
    guidance = haxaml_guidance(task=task, project_dir=str(project_dir))
    assert guidance["ok"] is True
    prebuild = haxaml_prebuild(task=task, description="refresh test", project_dir=str(project_dir))
    assert prebuild["ok"] is True
    return prebuild["data"]["session_id"]


def test_first_context_pack_is_full(governed_project):
    session_id = _start_session(governed_project, "refresh baseline")

    result = haxaml_context_pack(
        task="refresh baseline",
        project_dir=str(governed_project),
        pack="balanced",
        include_state=True,
        session_id=session_id,
        detail="full",
    )
    assert result["ok"] is True
    data = result["data"]
    assert data["refresh_mode"] == "full"
    assert data["refresh_summary"] == "Initial full context pack."
    assert data["context_pack"]["_meta"]["refresh_mode"] == "full"


def test_repeat_context_pack_returns_delta_only_for_changed_sections(governed_project):
    session_id = _start_session(governed_project, "refresh decisions")

    first = haxaml_context_pack(
        task="refresh decisions",
        project_dir=str(governed_project),
        pack="balanced",
        include_state=True,
        session_id=session_id,
        detail="full",
    )
    assert first["ok"] is True

    acts_path = governed_project / ".haxaml" / "acts.yaml"
    acts = yaml.safe_load(acts_path.read_text())
    acts["decisions"].append(
        {
            "decision": "Keep refresh delta narrow",
            "reasoning": "Only recent decisions changed between reads.",
            "date": "2026-05-07T00:00:00+00:00",
            "reversible": True,
        }
    )
    acts_path.write_text(yaml.dump(acts, default_flow_style=False, sort_keys=False))

    second = haxaml_context_pack(
        task="refresh decisions",
        project_dir=str(governed_project),
        pack="balanced",
        include_state=True,
        session_id=session_id,
        refresh_reason="context stale after updated decisions",
        detail="full",
    )
    assert second["ok"] is True
    data = second["data"]
    assert data["refresh_mode"] == "delta"
    assert "recent_decisions" in data["changed_sections"]
    assert "essential_facts" in data["unchanged_sections"]
    assert "recent_decisions" in data["context_pack"]["_meta"]["included_sections"]
    assert "essential_facts" not in data["context_pack"]["_meta"]["included_sections"]
    assert data["tokens"] < first["data"]["tokens"]
    assert data["refresh_summary"].startswith("Refreshed")


def test_repeat_context_pack_reports_no_change_when_markers_match(governed_project):
    session_id = _start_session(governed_project, "refresh no change")

    first = haxaml_context_pack(
        task="refresh no change",
        project_dir=str(governed_project),
        pack="balanced",
        include_state=True,
        session_id=session_id,
        detail="full",
    )
    assert first["ok"] is True

    second = haxaml_context_pack(
        task="refresh no change",
        project_dir=str(governed_project),
        pack="balanced",
        include_state=True,
        session_id=session_id,
        refresh_reason="context stale after checking again",
        detail="full",
    )
    assert second["ok"] is True
    data = second["data"]
    assert data["refresh_mode"] == "no_change"
    assert data["changed_sections"] == []
    assert data["token_delta"] == 0
    assert data["context_pack"]["_meta"]["included_sections"] == []
    assert data["tokens"] < first["data"]["tokens"]
