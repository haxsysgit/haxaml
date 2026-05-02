"""Tests for export rendering behavior."""

from pathlib import Path

import yaml

from haxaml.export_engine import (
    PromptRecipe,
    RecipeSection,
    build_recipe,
    _render_recipe,
    export_frame_to_markdown,
    export_to_file,
)
from haxaml.frame_model import FrameModel


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

    assert "## Working Profile" in content
    assert "## Reasoning & Response Style" in content
    assert "## Reference Examples" in content
    assert "## Rules & Conventions" in content

    assert content.index("## Working Profile") < content.index("## Reasoning & Response Style")
    assert content.index("## Reasoning & Response Style") < content.index("## Reference Examples")
    assert content.index("## Reference Examples") < content.index("## Rules & Conventions")


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
    assert "## Reference Examples" in content
    assert "No few-shot examples available." in content

    rules["agent_profile"]["example_policy"]["fallback_when_empty"] = "omit_section"
    _write_frame(tmp_path, rules, {"current_phase": "x", "active_task": {"name": "none"}})
    content = export_frame_to_markdown(str(tmp_path), "codex")
    assert "## Reference Examples" not in content


def test_non_codex_exports_also_include_profile_sections_when_defined(tmp_path):
    _write_frame(tmp_path, _base_rules(), _base_acts())
    content = export_frame_to_markdown(str(tmp_path), "claude")

    assert "## Working Profile" in content
    assert "## Reasoning & Response Style" in content
    assert "## Reference Examples" in content


def test_export_to_file_refuses_to_overwrite_non_haxaml_file_by_default(tmp_path):
    _write_frame(tmp_path, _base_rules(), _base_acts())
    native = tmp_path / "AGENTS.md"
    native.write_text("hand-written file\n", encoding="utf-8")

    try:
        export_to_file(str(tmp_path), "codex", output_path=str(native))
        assert False, "expected FileExistsError"
    except FileExistsError as exc:
        assert "Refusing to overwrite existing non-Haxaml file" in str(exc)


def test_export_to_file_override_native_writes_agents_md(tmp_path):
    _write_frame(tmp_path, _base_rules(), _base_acts())
    native = tmp_path / "AGENTS.md"
    native.write_text("hand-written file\n", encoding="utf-8")

    path = export_to_file(str(tmp_path), "codex", override_native=True)
    assert path.endswith("AGENTS.md")
    assert "Generated by Haxaml from FRAME" in native.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# PromptRecipe pipeline golden tests
# ---------------------------------------------------------------------------

def _build_recipe_for(tmp_path: Path, agent: str = "generic") -> PromptRecipe:
    _write_frame(tmp_path, _base_rules(), _base_acts())
    frame = FrameModel.load(str(tmp_path))
    return build_recipe(frame, agent)


class TestPromptRecipe:
    def test_recipe_has_expected_section_keys(self, tmp_path):
        recipe = _build_recipe_for(tmp_path)
        keys = [s.key for s in recipe.sections]
        assert "facts" in keys
        assert "rules" in keys

    def test_recipe_sections_ordered_facts_before_rules(self, tmp_path):
        recipe = _build_recipe_for(tmp_path)
        keys = [s.key for s in recipe.sections]
        assert keys.index("facts") < keys.index("rules")

    def test_recipe_profile_sections_present_with_agent_profile(self, tmp_path):
        recipe = _build_recipe_for(tmp_path, "codex")
        keys = [s.key for s in recipe.sections]
        assert "persona" in keys
        assert "reasoning" in keys

    def test_recipe_persona_before_rules(self, tmp_path):
        recipe = _build_recipe_for(tmp_path, "codex")
        keys = [s.key for s in recipe.sections]
        assert keys.index("persona") < keys.index("rules")

    def test_recipe_get_returns_section(self, tmp_path):
        recipe = _build_recipe_for(tmp_path)
        section = recipe.get("facts")
        assert section is not None
        assert section.key == "facts"
        assert section.included is True

    def test_recipe_get_returns_none_for_missing(self, tmp_path):
        recipe = _build_recipe_for(tmp_path)
        assert recipe.get("nonexistent") is None

    def test_recipe_exclude_removes_section(self, tmp_path):
        recipe = _build_recipe_for(tmp_path)
        trimmed = recipe.exclude("rules")
        assert trimmed.get("rules") is None
        assert trimmed.get("facts") is not None

    def test_recipe_exclude_does_not_mutate_original(self, tmp_path):
        recipe = _build_recipe_for(tmp_path)
        _ = recipe.exclude("rules")
        assert recipe.get("rules") is not None

    def test_render_recipe_produces_headers_and_footers(self, tmp_path):
        recipe = _build_recipe_for(tmp_path)
        output = _render_recipe(recipe)
        assert recipe.header in output
        assert recipe.footer in output

    def test_render_recipe_sections_in_order(self, tmp_path):
        recipe = _build_recipe_for(tmp_path)
        output = _render_recipe(recipe)
        assert output.index("Project Facts") < output.index("Rules & Conventions")

    def test_render_recipe_excluded_section_absent(self, tmp_path):
        recipe = _build_recipe_for(tmp_path)
        trimmed = recipe.exclude("rules")
        output = _render_recipe(trimmed)
        assert "## Rules & Conventions" not in output
        assert "## Project Facts" in output

    def test_build_recipe_missing_acts_omits_acts_section(self, tmp_path):
        frame_dir = tmp_path / ".haxaml"
        _write_yaml(frame_dir / "facts.yaml", _base_facts())
        _write_yaml(frame_dir / "rules.yaml", _base_rules())
        frame = FrameModel.load(str(tmp_path))
        recipe = build_recipe(frame, "generic")
        keys = [s.key for s in recipe.sections]
        assert "acts" not in keys

    def test_recipe_renders_same_as_export_frame_to_markdown(self, tmp_path):
        _write_frame(tmp_path, _base_rules(), _base_acts())
        via_pipeline = _render_recipe(_build_recipe_for(tmp_path, "generic"))
        via_direct = export_frame_to_markdown(str(tmp_path), "generic")
        assert via_pipeline == via_direct

    def test_recipe_is_deterministic(self, tmp_path):
        recipe1 = _build_recipe_for(tmp_path)
        recipe2 = _build_recipe_for(tmp_path)
        assert _render_recipe(recipe1) == _render_recipe(recipe2)

    def test_recipe_unknown_agent_raises(self, tmp_path):
        frame = FrameModel.load(str(tmp_path))
        try:
            build_recipe(frame, "unknown-agent-xyz")
            assert False, "should have raised ValueError"
        except ValueError as exc:
            assert "Unknown agent" in str(exc)

    def test_recipe_section_included_flag_excludes_from_render(self, tmp_path):
        recipe = _build_recipe_for(tmp_path)
        facts_section = recipe.get("facts")
        assert facts_section is not None
        facts_section.included = False
        output = _render_recipe(recipe)
        assert "## Project Facts" not in output
