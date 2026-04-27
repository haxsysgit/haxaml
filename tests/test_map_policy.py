"""Tests for map complexity policy checks."""

from pathlib import Path

import yaml

from haxaml.map_policy import evaluate_map_complexity, map_complexity_issues


def _write_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False))


def test_map_optional_for_small_low_complexity_project(tmp_path):
    _write_yaml(
        tmp_path / ".haxaml" / "expect.yaml",
        {
            "planning": {
                "estimated_runs": 3,
                "project_size": "small",
                "map_required": False,
            },
            "runbook": [
                {"run": 1, "status": "planned", "goal": "a", "outcome": "b", "done_when": "c", "touches": ["api"]},
            ],
        },
    )
    _write_yaml(
        tmp_path / ".haxaml" / "rules.yaml",
        {
            "boundaries": {
                "modules": {
                    "api": {"touches": ["service"]},
                    "service": {"touches": []},
                }
            }
        },
    )
    _write_yaml(
        tmp_path / ".haxaml" / "facts.yaml",
        {
            "database": {"type": "none"},
            "architecture": {"boundaries": ["api", "service"]},
        },
    )

    assessment = evaluate_map_complexity(tmp_path)
    errors, warnings = map_complexity_issues(assessment)
    assert assessment.required is False
    assert assessment.has_map is False
    assert errors == []
    assert warnings == []


def test_map_required_when_module_count_crosses_threshold(tmp_path):
    _write_yaml(
        tmp_path / ".haxaml" / "expect.yaml",
        {
            "planning": {
                "estimated_runs": 8,
                "project_size": "medium",
                "map_required": False,
            },
            "map_policy": {
                "module_threshold": 3,
            },
            "runbook": [],
        },
    )
    _write_yaml(
        tmp_path / ".haxaml" / "rules.yaml",
        {
            "boundaries": {
                "modules": {
                    "api": {"touches": []},
                    "service": {"touches": []},
                    "db": {"touches": []},
                }
            }
        },
    )
    _write_yaml(
        tmp_path / ".haxaml" / "facts.yaml",
        {
            "database": {"type": "none"},
            "architecture": {"boundaries": []},
        },
    )

    assessment = evaluate_map_complexity(tmp_path)
    errors, _ = map_complexity_issues(assessment)
    assert assessment.required is True
    assert any("module_count" in reason for reason in assessment.reasons)
    assert any("map.yaml is required" in err for err in errors)
    assert any("map_required=false" in err for err in errors)


def test_map_required_for_cross_impact_runs(tmp_path):
    _write_yaml(
        tmp_path / ".haxaml" / "expect.yaml",
        {
            "planning": {
                "estimated_runs": 6,
                "project_size": "medium",
                "map_required": False,
            },
            "map_policy": {
                "cross_impact_touch_threshold": 3,
                "cross_impact_run_threshold": 2,
            },
            "runbook": [
                {
                    "run": 1,
                    "status": "planned",
                    "goal": "a",
                    "outcome": "b",
                    "done_when": "c",
                    "touches": ["api", "service", "db"],
                },
                {
                    "run": 2,
                    "status": "planned",
                    "goal": "a",
                    "outcome": "b",
                    "done_when": "c",
                    "touches": ["api", "worker", "events"],
                },
            ],
        },
    )
    _write_yaml(tmp_path / ".haxaml" / "rules.yaml", {"boundaries": {"modules": {}}})
    _write_yaml(tmp_path / ".haxaml" / "facts.yaml", {"database": {"type": "none"}})

    assessment = evaluate_map_complexity(tmp_path)
    assert assessment.required is True
    assert assessment.cross_impact_runs == 2
    assert any("cross-impact runs=2" in reason for reason in assessment.reasons)


def test_shared_integration_signal_respected_when_map_exists(tmp_path):
    _write_yaml(
        tmp_path / ".haxaml" / "expect.yaml",
        {
            "planning": {
                "estimated_runs": 4,
                "project_size": "small",
                "map_required": True,
            },
            "map_policy": {
                "shared_integration_module_threshold": 2,
            },
            "runbook": [],
        },
    )
    _write_yaml(tmp_path / ".haxaml" / "rules.yaml", {"boundaries": {"modules": {}}})
    _write_yaml(
        tmp_path / ".haxaml" / "facts.yaml",
        {"database": {"type": "none"}, "architecture": {"boundaries": []}},
    )
    _write_yaml(
        tmp_path / ".haxaml" / "map.yaml",
        {
            "modules": [
                {"name": "api", "purpose": "x", "files": ["api.py"]},
                {"name": "worker", "purpose": "y", "files": ["worker.py"]},
            ],
            "external": [
                {
                    "name": "queue",
                    "type": "message_queue",
                    "used_by": ["api", "worker"],
                }
            ],
        },
    )

    assessment = evaluate_map_complexity(tmp_path)
    errors, warnings = map_complexity_issues(assessment)
    assert assessment.required is True
    assert assessment.has_map is True
    assert assessment.shared_integrations == 1
    assert errors == []
    assert warnings == []
