"""Tests for export rendering behavior."""

from pathlib import Path

import yaml

from haxaml.export_engine import export_frame_to_markdown


def _write_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)


def _base_facts() -> dict:
    return {
        "identity": {"name": "demo", "version": "0.1.0"},
        "goal": {"purpose": "Test export behavior"},
        "stack": {"language": "python"},
        "architecture": {"pattern": "layered", "reasoning": "testability"},
        "database": {"type": "none", "connection": "none"},
        "constraints": ["deterministic output"],
        "success_criteria": ["export remains stable"],
    }


def _base_rules() -> dict:
    return {
        "before_task": {"read_first": [".haxaml/facts.yaml"]},
        "boundaries": {"rules": ["Stay in scope"]},
        "after_task": {"report": ["what changed"], "update": [".haxaml/acts.yaml"]},
        "forbidden": ["Do not guess missing project facts"],
        "agent_profile": {
            "persona": {
                "role": "Codex implementation worker",
                "tone": ["direct", "concise"],
                "constraints": ["deterministic transformations only"],
            },
            "reasoning_policy": {
                "private_reasoning": "Keep private reasoning internal.",
                "public_rationale": "Provide concise, checkable rationale.",
                "checklist": ["summary", "verification", "risks"],
                "prohibit_cot_transcript": True,
            },
            "output_contract": {
                "required_sections": ["Summary", "Changes", "Verification", "Risks"],
                "format_notes": ["Use compact bullets."],
            },
        },
    }


def _base_acts() -> dict:
    return {
        "current_phase": "test phase",
        "active_task": {"name": "none"},
        "decisions": [
            {
                "decision": "Use deterministic formatter",
                "reasoning": "Ensures stable output across runs",
                "date": "2026-04-27T00:00:00Z",
            }
        ],
        "completed_tasks": [
            {
                "name": "Baseline export",
                "result": "success",
                "summary": "Export command writes expected files.",
                "completed": "2026-04-27T00:00:00Z",
            }
        ],
    }


def _write_frame(tmp_path: Path, rules: dict, acts: dict | None = None) -> None:
    frame_dir = tmp_path / ".haxaml"
    _write_yaml(frame_dir / "facts.yaml", _base_facts())
    _write_yaml(frame_dir / "rules.yaml", rules)
    if acts is not None:
        _write_yaml(frame_dir / "acts.yaml", acts)


def test_codex_export_includes_prompt_profile_sections_in_order(tmp_path):
    _write_frame(tmp_path, _base_rules(), _base_acts())
    content = export_frame_to_markdown(str(tmp_path), "codex")

    assert "## Agent Persona" in content
    assert "## Reasoning & Response Policy" in content
    assert "## Few-Shot Examples" in content
    assert "## Rules & Conventions" in content

    assert content.index("## Agent Persona") < content.index("## Reasoning & Response Policy")
    assert content.index("## Reasoning & Response Policy") < content.index("## Few-Shot Examples")
    assert content.index("## Few-Shot Examples") < content.index("## Rules & Conventions")


def test_codex_export_is_deterministic(tmp_path):
    _write_frame(tmp_path, _base_rules(), _base_acts())
    first = export_frame_to_markdown(str(tmp_path), "codex")
    second = export_frame_to_markdown(str(tmp_path), "codex")
    assert first == second


def test_codex_export_applies_deterministic_example_budget_and_truncation(tmp_path):
    rules = _base_rules()
    rules["agent_profile"]["few_shot_examples"] = [
        {
            "title": "Large example 1",
            "input": "A" * 400,
            "output": "B" * 500,
        },
        {
            "title": "Large example 2",
            "input": "C" * 400,
            "output": "D" * 500,
        },
    ]
    rules["agent_profile"]["example_policy"] = {
        "max_examples": 1,
        "max_input_chars": 80,
        "max_output_chars": 90,
        "max_total_chars": 280,
        "derived_from_acts_max": 0,
        "ordering": "explicit_then_derived",
        "fallback_when_empty": "render_notice",
    }
    _write_frame(tmp_path, rules, _base_acts())

    content = export_frame_to_markdown(str(tmp_path), "codex")
    assert "Compaction: showing 1 of" in content
    assert "Truncation: compacted" in content
    assert "### Example 1 (explicit)" in content
    assert "### Example 2" not in content


def test_codex_export_derives_examples_from_acts_when_explicit_missing(tmp_path):
    rules = _base_rules()
    rules["agent_profile"]["example_policy"] = {
        "max_examples": 2,
        "max_input_chars": 200,
        "max_output_chars": 200,
        "max_total_chars": 800,
        "derived_from_acts_max": 2,
        "ordering": "explicit_then_derived",
        "fallback_when_empty": "render_notice",
    }
    _write_frame(tmp_path, rules, _base_acts())

    content = export_frame_to_markdown(str(tmp_path), "codex")
    assert "### Example 1 (derived)" in content
    assert "Use deterministic formatter" in content


def test_codex_export_handles_empty_examples_with_notice_or_omission(tmp_path):
    rules = _base_rules()
    rules["agent_profile"]["example_policy"] = {
        "max_examples": 2,
        "max_input_chars": 200,
        "max_output_chars": 200,
        "max_total_chars": 800,
        "derived_from_acts_max": 0,
        "ordering": "explicit_then_derived",
        "fallback_when_empty": "render_notice",
    }
    _write_frame(tmp_path, rules, {"current_phase": "x", "active_task": {"name": "none"}})

    content = export_frame_to_markdown(str(tmp_path), "codex")
    assert "## Few-Shot Examples" in content
    assert "No few-shot examples available." in content

    rules["agent_profile"]["example_policy"]["fallback_when_empty"] = "omit_section"
    _write_frame(tmp_path, rules, {"current_phase": "x", "active_task": {"name": "none"}})
    content = export_frame_to_markdown(str(tmp_path), "codex")
    assert "## Few-Shot Examples" not in content


def test_non_codex_exports_do_not_include_codex_profile_sections(tmp_path):
    _write_frame(tmp_path, _base_rules(), _base_acts())
    content = export_frame_to_markdown(str(tmp_path), "claude")

    assert "## Agent Persona" not in content
    assert "## Reasoning & Response Policy" not in content
    assert "## Few-Shot Examples" not in content
