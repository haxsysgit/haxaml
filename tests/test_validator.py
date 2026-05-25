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


def _frame(file: str, role: str) -> dict:
    return {
        "file": file,
        "schema_version": "0.8.0",
        "role": role,
        "status": "draft",
        "last_reviewed": None,
        "updated_by": None,
        "update_reason": None,
    }


class TestFactsValidation:

    def test_valid_minimal_facts(self, tmp_path):
        facts = {
            "frame": _frame("facts", "stable_project_truth"),
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
        assert "frame" in error_text or "Additional properties" in error_text

    def test_facts_body_is_rejected_until_a_schema_slice_adds_it(self, tmp_path):
        facts = {
            "frame": _frame("facts", "stable_project_truth"),
            "identity": {"name": "test"},
        }
        path = _write_yaml(str(tmp_path), "facts.yaml", facts)
        errors = validate_facts(path)
        assert any("Additional properties" in error and "identity" in error for error in errors)


class TestActsValidation:

    def test_valid_minimal_acts(self, tmp_path):
        acts = {
            "frame": _frame("acts", "checked_activity_record"),
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

    def test_no_body_completeness_checks_exist_in_frontmatter_slice(self, tmp_path):
        facts = {
            "frame": _frame("facts", "stable_project_truth"),
        }
        path = _write_yaml(str(tmp_path), "facts.yaml", facts)
        missing = detect_missing_facts_fields(path)
        assert missing == []


class TestRulesValidation:

    def test_rules_agent_profile_valid(self, tmp_path):
        rules = {
            "frame": _frame("rules", "project_constraints"),
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
        assert result.blocking == []
        assert any("Phase 'phase 1' is marked done" in warning or "phase 'phase 1'" in warning.lower() for warning in result.warnings)

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

    def test_rules_profile_body_is_rejected_until_a_schema_slice_adds_it(self, tmp_path):
        rules = {
            "frame": _frame("rules", "project_constraints"),
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
        assert any("Additional properties" in error and "agent_profile" in error for error in errors)

    def test_rules_without_agent_profile_remains_valid(self, tmp_path):
        rules = {
            "frame": _frame("rules", "project_constraints"),
        }
        path = _write_yaml(str(tmp_path), "rules.yaml", rules)
        errors = validate_rules(path)
        assert errors == [], f"Expected no errors, got: {errors}"

    def test_rules_lifecycle_and_policy_extensions_validate(self, tmp_path):
        rules = {
            "frame": _frame("rules", "project_constraints"),
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
        assert any("Additional properties" in error for error in errors)

    def test_rules_policy_body_is_rejected_until_a_schema_slice_adds_it(self, tmp_path):
        rules = {
            "frame": _frame("rules", "project_constraints"),
            "before_task": {"read_first": [".haxaml/facts.yaml"]},
            "boundaries": {"rules": ["Stay within scope"]},
            "after_task": {"report": ["what changed"], "update": [".haxaml/acts.yaml"]},
            "forbidden": ["Do not guess missing project facts"],
            "clarification_policy": {"mode": "bad_mode"},
            "context_policy": {"default_pack": "super_full"},
        }
        path = _write_yaml(str(tmp_path), "rules.yaml", rules)
        errors = validate_rules(path)
        assert any("Additional properties" in error and "clarification_policy" in error for error in errors)


class TestActsLifecycleValidation:

    def test_acts_session_and_verification_extensions_validate(self, tmp_path):
        acts = {
            "frame": _frame("acts", "checked_activity_record"),
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
        assert any("Additional properties" in error for error in errors)
