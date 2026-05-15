"""Tests for facts and acts validation (FRAME model)."""

import os
import tempfile
from types import SimpleNamespace
from pathlib import Path

import pytest
import yaml

from haxaml.validator import (
    detect_missing_facts_fields,
    frame_consistency_report,
    semantic_validate,
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


class TestConsistencyReport:
    def _frame(self, *, facts=None, rules=None, acts=None, expect=None):
        return SimpleNamespace(
            load_errors=[],
            facts=facts or {},
            rules=rules or {},
            acts=acts or {},
            expect=expect or {},
            map={},
        )

    def test_progress_summary_reports_sync_pending(self):
        frame = self._frame(
            acts={
                "active_task": {"name": "implement auth"},
                "runs": [{"id": "run-1", "task": "implement auth", "result": "success"}],
                "expect_sync": {
                    "required": True,
                    "pending_run_id": "run-1",
                    "pending_task": "implement auth",
                    "pending_result": "success",
                },
            },
            expect={"phases": [], "runbook": []},
        )
        report = frame_consistency_report(frame)
        assert report["status"] == "sync_pending"
        assert report["pending_expect_sync"] is True

    def test_progress_summary_reports_blocked_for_unmet_active_run_dependencies(self):
        frame = self._frame(
            acts={"active_task": {"name": "implement auth"}},
            expect={
                "phases": [{"name": "Phase 1", "status": "active"}],
                "runbook": [
                    {
                        "run": 2,
                        "phase": "Phase 1",
                        "status": "active",
                        "goal": "Build auth",
                        "outcome": "Auth shipped",
                        "depends_on": [1],
                        "verify": ["tests"],
                    }
                ],
            },
        )
        report = frame_consistency_report(frame)
        assert report["status"] == "blocked"
        assert any(item["code"] == "active_run_unmet_dependencies" for item in report["findings"])

    def test_progress_summary_reports_stale_state_for_active_task_session_mismatch(self):
        frame = self._frame(
            acts={
                "active_task": {"name": "implement auth"},
                "sessions": [{"id": "session-1", "task": "update docs", "status": "acting", "started": "2026-01-01T00:00:00+00:00"}],
            },
            expect={"phases": [], "runbook": []},
        )
        report = frame_consistency_report(frame)
        assert report["status"] == "stale_state"
        assert any(item["code"] == "active_task_session_mismatch" for item in report["findings"])

    def test_semantic_validate_keeps_consistency_findings_advisory(self):
        frame = self._frame(
            acts={"runs": [{"id": "run-1", "task": "task", "result": "success"}]},
            rules={"after_task": {"verify": ["Run tests"]}},
            expect={
                "phases": [{"name": "Phase 1", "status": "done"}],
                "runbook": [
                    {
                        "run": 1,
                        "phase": "Phase 1",
                        "status": "active",
                        "goal": "Ship auth",
                        "outcome": "Auth shipped",
                        "depends_on": [],
                        "verify": ["tests"],
                    }
                ],
            },
        )
        result = semantic_validate(frame)
        assert result.blocking == [
            "facts.identity section is absent — add identity.name and identity.version",
            "facts.goal section is absent — add goal.purpose and goal.scope",
        ]
        assert any("Phase 'phase 1' is marked done" in warning or "phase 'phase 1'" in warning.lower() for warning in result.warnings)
        assert any("verification discipline" in warning.lower() for warning in result.warnings)

    def test_semantic_validate_does_not_use_removed_expect_runs_key(self):
        frame = self._frame(
            acts={"runs": [{"id": "run-1", "task": "task", "result": "success"}]},
            expect={
                "phases": [{"name": "Phase 1", "status": "active"}],
                "runbook": [
                    {
                        "run": 1,
                        "phase": "Phase 1",
                        "status": "active",
                        "goal": "Ship auth",
                        "outcome": "Auth shipped",
                        "depends_on": [],
                        "verify": ["tests"],
                    }
                ],
            },
        )

        result = semantic_validate(frame)
        assert not any("has no matching acts record" in item for item in result.blocking)

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

    def test_rules_lifecycle_and_policy_extensions_validate(self, tmp_path):
        rules = {
            "before_task": {"read_first": [".haxaml/facts.yaml"]},
            "boundaries": {"rules": ["Stay within scope"]},
            "after_task": {"report": ["what changed"], "update": [".haxaml/acts.yaml"]},
            "forbidden": ["Do not guess missing project facts"],
            "lifecycle": {
                "onboarding_full_reads": 5,
                "enforce_verify_before_record": True,
                "phases": ["start", "plan", "act", "verify", "record", "export"],
            },
            "context_policy": {
                "default_pack": "balanced",
                "max_items_per_section": 6,
                "max_chars_per_item": 280,
            },
            "clarification_policy": {
                "mode": "risk_gated_soft_block",
                "min_task_chars": 16,
                "high_risk_keywords": ["migrate", "delete", "auth"],
            },
            "verification_policy": {
                "require_checks": [
                    "understood_task",
                    "inspected_context",
                    "changed_right_files",
                    "risky_or_unrelated_touch",
                    "followed_rules",
                    "updated_journal",
                    "unresolved_logged",
                    "explained_changes",
                ],
                "allow_pass_with_risks": True,
            },
            "guidance_policy": {
                "task_type_hints": {"debug": ["bug", "fix"]},
                "safer_path_templates": ["Ask for rollout constraints first."],
            },
        }
        path = _write_yaml(str(tmp_path), "rules.yaml", rules)
        errors = validate_rules(path)
        assert errors == [], f"Expected no errors, got: {errors}"

    def test_rules_invalid_policy_values_are_reported(self, tmp_path):
        rules = {
            "before_task": {"read_first": [".haxaml/facts.yaml"]},
            "boundaries": {"rules": ["Stay within scope"]},
            "after_task": {"report": ["what changed"], "update": [".haxaml/acts.yaml"]},
            "forbidden": ["Do not guess missing project facts"],
            "clarification_policy": {"mode": "bad_mode"},
            "context_policy": {"default_pack": "super_full"},
        }
        path = _write_yaml(str(tmp_path), "rules.yaml", rules)
        errors = validate_rules(path)
        assert errors
        assert any("[clarification_policy.mode]" in err for err in errors)
        assert any("[context_policy.default_pack]" in err for err in errors)


class TestActsLifecycleValidation:

    def test_acts_session_and_verification_extensions_validate(self, tmp_path):
        acts = {
            "current_phase": "Phase 1",
            "active_task": {"name": "session task"},
            "sessions": [
                {
                    "id": "session-abc",
                    "task": "implement auth",
                    "status": "started",
                    "phase": "start",
                    "risk_level": "high",
                    "guidance_status": "action_required",
                    "started": "2026-04-28T12:00:00Z",
                    "updated": "2026-04-28T12:01:00Z",
                }
            ],
            "verifications": [
                {
                    "id": "verify-abc",
                    "session_id": "session-abc",
                    "task": "implement auth",
                    "verdict": "pass_with_risks",
                    "checks": [{"name": "understood_task", "passed": True}],
                    "evidence_refs": [".haxaml/facts.yaml", "src/auth.py"],
                    "timestamp": "2026-04-28T12:02:00Z",
                }
            ],
            "context_compaction": {
                "sessions_started": 3,
                "full_reads_completed": 2,
                "default_pack": "balanced",
                "last_pack_tokens": 640,
            },
        }
        path = _write_yaml(str(tmp_path), "acts.yaml", acts)
        errors = validate_acts(path)
        assert errors == [], f"Expected no errors, got: {errors}"
