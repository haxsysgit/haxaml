"""Tests for the shared runtime snapshot cache."""

from pathlib import Path

import yaml

from haxaml.mcp_server import haxaml_init
from haxaml.paths import acts_history_path, frame_path
from haxaml.runtime_cache import runtime_cache


def _seed_project(project_dir: Path) -> None:
    result = haxaml_init(str(project_dir))
    assert result["ok"] is True
    haxaml_dir = project_dir / ".haxaml"
    (haxaml_dir / "facts.yaml").write_text(
        yaml.dump(
            {
                "identity": {"name": "cache-project", "version": "0.1.0"},
                "goal": {"purpose": "Cache tests", "scope": "Unit tests"},
                "architecture": {"pattern": "layered", "boundaries": ["api"]},
                "database": {"type": "sqlite"},
                "stack": {"language": "python"},
                "unresolved": [],
            },
            default_flow_style=False,
            sort_keys=False,
        )
    )
    (haxaml_dir / "rules.yaml").write_text(
        yaml.dump(
            {
                "before_task": {"read_first": [".haxaml/facts.yaml"], "check": ["Confirm scope"]},
                "boundaries": {"rules": ["Stay in scope"], "modules": {"api": {"touches": ["db"]}}},
                "after_task": {"verify": ["pytest"]},
                "forbidden": ["Do not guess"],
            },
            default_flow_style=False,
            sort_keys=False,
        )
    )
    (haxaml_dir / "acts.yaml").write_text(
        yaml.dump(
            {
                "current_phase": "Phase 1",
                "active_task": {"name": "none"},
                "decisions": [],
                "unresolved_dependencies": [],
                "runs": [],
                "sessions": [],
                "verifications": [],
            },
            default_flow_style=False,
            sort_keys=False,
        )
    )
    (haxaml_dir / "expect.yaml").write_text(
        yaml.dump(
            {
                "planning": {"goal": "Cache tests", "strategy": "Incremental", "map_required": False},
                "phases": [{"name": "Phase 1", "status": "active"}],
                "runbook": [{"run": 1, "status": "active", "goal": "Test cache"}],
                "open_questions": [],
            },
            default_flow_style=False,
            sort_keys=False,
        )
    )


def test_unchanged_frame_files_are_not_reparsed(monkeypatch, tmp_path):
    _seed_project(tmp_path)
    cache = runtime_cache()
    cache.reset()

    import haxaml.runtime_cache as runtime_cache_module

    calls = {"count": 0}
    original = runtime_cache_module.yaml.safe_load

    def counted_safe_load(stream):
        calls["count"] += 1
        return original(stream)

    monkeypatch.setattr(runtime_cache_module.yaml, "safe_load", counted_safe_load)

    cache.get_frame_bundle(str(tmp_path))
    assert calls["count"] == 4

    cache.get_frame_bundle(str(tmp_path))
    assert calls["count"] == 4

    facts_path = frame_path(tmp_path, "facts.yaml")
    facts = original(facts_path.read_text())
    facts["goal"]["scope"] = "Changed scope"
    facts_path.write_text(yaml.dump(facts, default_flow_style=False, sort_keys=False))

    cache.get_frame_bundle(str(tmp_path))
    assert calls["count"] == 5


def test_changing_one_file_invalidates_only_that_snapshot(tmp_path):
    _seed_project(tmp_path)
    cache = runtime_cache()
    cache.reset()

    first = cache.get_project_snapshot(str(tmp_path))
    first_facts = first.files["facts"].data
    first_rules = first.files["rules"].data

    facts_path = frame_path(tmp_path, "facts.yaml")
    facts = yaml.safe_load(facts_path.read_text())
    facts["constraints"] = ["One new constraint"]
    facts_path.write_text(yaml.dump(facts, default_flow_style=False, sort_keys=False))

    second = cache.get_project_snapshot(str(tmp_path))
    assert second.files["facts"].data is not first_facts
    assert second.files["rules"].data is first_rules


def test_archive_overview_is_shallow_and_detail_loads_selected_record(monkeypatch, tmp_path):
    _seed_project(tmp_path)
    archive_path = acts_history_path(tmp_path)
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    archive_path.write_text(
        yaml.dump(
            {
                "metadata": {
                    "version": "0.6.7",
                    "managed_by": "haxaml",
                    "archive_mode": "manual",
                    "counts": {"runs": 1, "sessions": 0, "verifications": 0},
                },
                "index": [
                    {
                        "kind": "run",
                        "id": "run-1",
                        "task": "archive test",
                        "summary": "Archived change",
                        "status_or_result": "success",
                    }
                ],
                "history": {
                    "runs": [{"id": "run-1", "task": "archive test", "changes": "full record body"}],
                    "sessions": [],
                    "verifications": [],
                },
            },
            default_flow_style=False,
            sort_keys=False,
        )
    )

    cache = runtime_cache()
    cache.reset()

    calls = {"count": 0}
    original = cache._load_full_archive_doc

    def counted_loader(path, signature):
        calls["count"] += 1
        return original(path, signature)

    monkeypatch.setattr(cache, "_load_full_archive_doc", counted_loader)

    index_snapshot = cache.get_archive_index(str(tmp_path))
    assert index_snapshot.exists is True
    assert index_snapshot.index[0]["id"] == "run-1"
    assert calls["count"] == 0

    detail = cache.load_selected_archive_details(str(tmp_path), [("run", "run-1")])
    assert calls["count"] == 1
    assert list(detail) == [("run", "run-1")]
    assert detail[("run", "run-1")]["changes"] == "full record body"
