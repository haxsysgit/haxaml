"""Tests for the 0.8.0 FRAME frontmatter base slice."""

from __future__ import annotations

from pathlib import Path

import yaml

from haxaml.frame_model import FrameModel
from haxaml.mcp_server import haxaml_init
from haxaml.setup.templates import render_frame_templates
from haxaml.validator import (
    validate_acts,
    validate_expect,
    validate_facts,
    validate_map,
    validate_rules,
)


EXPECTED_FRONTMATTER = {
    "facts.yaml": ("facts", "stable_project_truth", validate_facts),
    "rules.yaml": ("rules", "project_constraints", validate_rules),
    "acts.yaml": ("acts", "checked_activity_record", validate_acts),
    "expect.yaml": ("expect", "planned_direction", validate_expect),
    "map.yaml": ("map", "repo_context_map", validate_map),
}


def _frame(file: str, role: str, *, status: str = "draft") -> dict:
    return {
        "file": file,
        "schema_version": "0.8.0",
        "role": role,
        "status": status,
        "last_reviewed": None,
        "updated_by": None,
        "update_reason": None,
    }


def _write_yaml(path: Path, data: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False), encoding="utf-8")
    return path


def test_frontmatter_only_is_valid_for_all_frame_files(tmp_path):
    for filename, (file, role, validator) in EXPECTED_FRONTMATTER.items():
        path = _write_yaml(tmp_path / filename, {"frame": _frame(file, role)})

        assert validator(str(path)) == []


def test_frontmatter_rejects_wrong_file_role_and_version(tmp_path):
    bad_cases = [
        ("facts.yaml", {"frame": _frame("rules", "stable_project_truth")}, validate_facts, "facts"),
        ("rules.yaml", {"frame": _frame("rules", "repo_context_map")}, validate_rules, "project_constraints"),
        (
            "acts.yaml",
            {"frame": {**_frame("acts", "checked_activity_record"), "schema_version": "0.7.7"}},
            validate_acts,
            "0.8.0",
        ),
        ("expect.yaml", {"frame": {**_frame("expect", "planned_direction"), "status": "unknown"}}, validate_expect, "status"),
    ]

    for filename, data, validator, expected_text in bad_cases:
        path = _write_yaml(tmp_path / filename, data)
        errors = validator(str(path))

        assert errors
        assert any(expected_text in item for item in errors)


def test_frontmatter_slice_rejects_undefined_body_fields(tmp_path):
    cases = [
        ("facts.yaml", {"frame": _frame("facts", "stable_project_truth"), "identity": {"name": "demo"}}, validate_facts, "identity"),
        ("rules.yaml", {"frame": _frame("rules", "project_constraints"), "before_task": {}}, validate_rules, "before_task"),
        ("acts.yaml", {"frame": _frame("acts", "checked_activity_record"), "runs": []}, validate_acts, "runs"),
        ("expect.yaml", {"frame": _frame("expect", "planned_direction"), "runbook": []}, validate_expect, "runbook"),
        ("map.yaml", {"frame": _frame("map", "repo_context_map"), "modules": []}, validate_map, "modules"),
    ]

    for filename, data, validator, rejected_key in cases:
        path = _write_yaml(tmp_path / filename, data)
        errors = validator(str(path))

        assert any("Additional properties" in item and rejected_key in item for item in errors)


def test_setup_templates_emit_frontmatter_only_core_files():
    templates = render_frame_templates()

    for filename, (file, role, _) in EXPECTED_FRONTMATTER.items():
        if filename == "map.yaml":
            continue

        data = yaml.safe_load(templates[filename])

        assert data == {"frame": _frame(file, role)}


def test_frame_model_exposes_brain_frontmatter_without_body_fields(tmp_path):
    haxaml_dir = tmp_path / ".haxaml"
    for filename, (file, role, _) in EXPECTED_FRONTMATTER.items():
        if filename == "map.yaml":
            continue
        _write_yaml(haxaml_dir / filename, {"frame": _frame(file, role, status="active")})

    frame = FrameModel.load(tmp_path)
    summary = frame.frontmatter_summary()

    assert summary == {
        "facts": {
            "file": "facts",
            "schema_version": "0.8.0",
            "role": "stable_project_truth",
            "status": "active",
            "last_reviewed": None,
        },
        "rules": {
            "file": "rules",
            "schema_version": "0.8.0",
            "role": "project_constraints",
            "status": "active",
            "last_reviewed": None,
        },
        "acts": {
            "file": "acts",
            "schema_version": "0.8.0",
            "role": "checked_activity_record",
            "status": "active",
            "last_reviewed": None,
        },
        "expect": {
            "file": "expect",
            "schema_version": "0.8.0",
            "role": "planned_direction",
            "status": "active",
            "last_reviewed": None,
        },
    }
    assert frame.minimal_signal()["frontmatter"] == summary
    assert frame.health_summary()["frontmatter"] == summary


def test_frame_model_ignores_missing_or_malformed_frontmatter(tmp_path):
    haxaml_dir = tmp_path / ".haxaml"
    _write_yaml(haxaml_dir / "facts.yaml", {"frame": _frame("facts", "stable_project_truth")})
    _write_yaml(haxaml_dir / "rules.yaml", {"not_frame": True})
    _write_yaml(haxaml_dir / "acts.yaml", {"frame": []})

    frame = FrameModel.load(tmp_path)

    assert frame.frontmatter("facts")["role"] == "stable_project_truth"
    assert frame.frontmatter("rules") == {}
    assert frame.frontmatter("acts") == {}
    assert set(frame.frontmatter_summary()) == {"facts"}


def test_haxaml_init_creates_brain_frontmatter(tmp_path):
    result = haxaml_init(str(tmp_path))

    assert result["ok"] is True
    frame = FrameModel.load(tmp_path)
    summary = frame.frontmatter_summary()

    assert set(summary) == {"facts", "rules", "acts", "expect"}
    assert summary["facts"]["role"] == "stable_project_truth"
    assert summary["rules"]["role"] == "project_constraints"
    assert summary["acts"]["role"] == "checked_activity_record"
    assert summary["expect"]["role"] == "planned_direction"
    assert all(item["schema_version"] == "0.8.0" for item in summary.values())
