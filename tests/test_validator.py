"""Tests for facts and acts validation (FRAME model)."""

import os
import tempfile
from pathlib import Path

import pytest
import yaml

from haxaml.validator import (
    detect_missing_facts_fields,
    validate_acts,
    validate_facts,
    validate_rules,
)


FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _write_yaml(tmp_dir: str, filename: str, data: dict) -> str:
    path = os.path.join(tmp_dir, filename)
    with open(path, "w") as f:
        yaml.dump(data, f)
    return path


class TestFactsValidation:

    def test_valid_minimal_facts(self, tmp_path):
        facts = {
            "identity": {"name": "test", "version": "0.1.0"},
            "goal": {"purpose": "Test project"},
            "stack": {"language": "python"},
            "architecture": {"pattern": "layered", "reasoning": "simplicity"},
            "database": {"type": "none", "connection": "none"},
            "constraints": ["no guessing"],
            "success_criteria": ["it works"],
        }
        path = _write_yaml(str(tmp_path), "facts.yaml", facts)
        errors = validate_facts(path)
        assert errors == [], f"Expected no errors, got: {errors}"

    def test_missing_required_fields(self, tmp_path):
        facts = {"identity": {"name": "test"}}
        path = _write_yaml(str(tmp_path), "facts.yaml", facts)
        errors = validate_facts(path)
        assert len(errors) > 0
        error_text = " ".join(errors)
        assert "goal" in error_text or "required" in error_text.lower()

    def test_missing_identity_version(self, tmp_path):
        facts = {
            "identity": {"name": "test"},  # missing version
            "goal": {"purpose": "Test"},
            "stack": {"language": "python"},
            "architecture": {"pattern": "layered", "reasoning": "test"},
            "database": {"type": "none", "connection": "none"},
            "constraints": ["rule"],
            "success_criteria": ["works"],
        }
        path = _write_yaml(str(tmp_path), "facts.yaml", facts)
        errors = validate_facts(path)
        assert any("version" in e for e in errors)

    def test_empty_constraints_rejected(self, tmp_path):
        facts = {
            "identity": {"name": "test", "version": "0.1.0"},
            "goal": {"purpose": "Test"},
            "stack": {"language": "python"},
            "architecture": {"pattern": "layered", "reasoning": "test"},
            "database": {"type": "none", "connection": "none"},
            "constraints": [],
            "success_criteria": ["works"],
        }
        path = _write_yaml(str(tmp_path), "facts.yaml", facts)
        errors = validate_facts(path)
        assert any("constraints" in e.lower() for e in errors)


class TestActsValidation:

    def test_valid_minimal_acts(self, tmp_path):
        acts = {
            "current_phase": "Phase 1",
            "active_task": {"name": "test task"},
        }
        path = _write_yaml(str(tmp_path), "acts.yaml", acts)
        errors = validate_acts(path)
        assert errors == [], f"Expected no errors, got: {errors}"

    def test_missing_required_fields(self, tmp_path):
        acts = {}
        path = _write_yaml(str(tmp_path), "acts.yaml", acts)
        errors = validate_acts(path)
        assert len(errors) > 0


class TestFactsDoctor:

    def test_detects_missing_recommended_fields(self, tmp_path):
        facts = {
            "identity": {"name": "test", "version": "0.1.0"},
            "goal": {"purpose": "Test"},
            "stack": {"language": "python"},
            "architecture": {"pattern": "layered", "reasoning": "test"},
            "database": {"type": "none", "connection": "none"},
            "constraints": ["rule"],
            "success_criteria": ["works"],
        }
        path = _write_yaml(str(tmp_path), "facts.yaml", facts)
        missing = detect_missing_facts_fields(path)
        assert len(missing) > 0
        fields_text = " ".join(missing)
        assert "description" in fields_text or "tools" in fields_text

    def test_detects_blocking_unresolved(self, tmp_path):
        facts = {
            "identity": {"name": "test", "version": "0.1.0"},
            "goal": {"purpose": "Test", "scope": "all", "out_of_scope": []},
            "stack": {"language": "python"},
            "architecture": {"pattern": "layered", "reasoning": "test"},
            "database": {"type": "none", "connection": "none"},
            "constraints": ["rule"],
            "success_criteria": ["works"],
            "tools": {"testing": "pytest"},
            "services": [{"name": "api", "purpose": "test"}],
            "roles": [{"name": "dev", "responsibility": "build"}],
            "features": [{"name": "core", "status": "planned"}],
            "unresolved": [
                {"item": "DB URI", "reason": "not provided", "blocking": True}
            ],
        }
        path = _write_yaml(str(tmp_path), "facts.yaml", facts)
        missing = detect_missing_facts_fields(path)
        assert any("BLOCKING" in m for m in missing)


class TestRulesValidation:

    def test_rules_agent_profile_valid(self, tmp_path):
        rules = {
            "before_task": {"read_first": [".haxaml/facts.yaml"]},
            "boundaries": {"rules": ["Stay within scope"]},
            "after_task": {"report": ["what changed"], "update": [".haxaml/acts.yaml"]},
            "forbidden": ["Do not guess missing project facts"],
            "agent_profile": {
                "persona": {
                    "role": "Codex implementation agent",
                    "tone": ["direct", "concise"],
                    "constraints": ["deterministic output only"],
                },
                "reasoning_policy": {
                    "private_reasoning": "Keep internal reasoning private.",
                    "public_rationale": "Give concise, checkable rationale.",
                    "checklist": ["summarize", "show checks", "list risks"],
                    "prohibit_cot_transcript": True,
                },
                "output_contract": {
                    "required_sections": ["Summary", "Verification", "Risks"],
                    "format_notes": ["Use concise bullet points."],
                },
                "few_shot_examples": [
                    {"input": "Task request", "output": "Concise task response"}
                ],
                "example_policy": {
                    "max_examples": 3,
                    "max_input_chars": 200,
                    "max_output_chars": 250,
                    "max_total_chars": 900,
                    "derived_from_acts_max": 2,
                    "ordering": "explicit_then_derived",
                    "fallback_when_empty": "render_notice",
                },
            },
        }
        path = _write_yaml(str(tmp_path), "rules.yaml", rules)
        errors = validate_rules(path)
        assert errors == [], f"Expected no errors, got: {errors}"

    def test_rules_agent_profile_invalid_fields_report_paths(self, tmp_path):
        rules = {
            "before_task": {"read_first": [".haxaml/facts.yaml"]},
            "boundaries": {"rules": ["Stay within scope"]},
            "after_task": {"report": ["what changed"], "update": [".haxaml/acts.yaml"]},
            "forbidden": ["Do not guess missing project facts"],
            "agent_profile": {
                "persona": {
                    "tone": ["direct"],
                    "constraints": ["deterministic output only"],
                },
                "reasoning_policy": {
                    "private_reasoning": "Keep private.",
                    "public_rationale": "Brief rationale only.",
                    "checklist": ["summary"],
                    "prohibit_cot_transcript": False,
                },
                "output_contract": {"required_sections": ["Summary"]},
                "example_policy": {"fallback_when_empty": "bad_value"},
            },
        }
        path = _write_yaml(str(tmp_path), "rules.yaml", rules)
        errors = validate_rules(path)
        assert errors
        assert any("[agent_profile.persona]" in err and "required property" in err for err in errors)
        assert any("[agent_profile.reasoning_policy.prohibit_cot_transcript]" in err for err in errors)
        assert any("[agent_profile.example_policy.fallback_when_empty]" in err for err in errors)

    def test_rules_without_agent_profile_remains_valid(self, tmp_path):
        rules = {
            "before_task": {"read_first": [".haxaml/facts.yaml"]},
            "boundaries": {"rules": ["Stay within scope"]},
            "after_task": {"report": ["what changed"], "update": [".haxaml/acts.yaml"]},
            "forbidden": ["Do not guess missing project facts"],
        }
        path = _write_yaml(str(tmp_path), "rules.yaml", rules)
        errors = validate_rules(path)
        assert errors == [], f"Expected no errors, got: {errors}"
