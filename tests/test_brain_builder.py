"""Tests for facts builder — guided construction and intent derivation."""

import os

import pytest
import yaml

from haxaml.brain_builder import (
    is_placeholder,
    validate_answer,
    build_brain_from_answers,
    derive_facts_from_intent,
    write_facts,
    interactive_build,
)
from haxaml.validator import validate_facts


class TestPlaceholderDetection:

    @pytest.mark.parametrize("value", [
        "", "TODO", "TBD", "tbd", "placeholder", "fill in",
        "xxx", "xxxx", "we'll decide later", "assume default",
        "FIXME", "default config",
    ])
    def test_detects_placeholders(self, value):
        assert is_placeholder(value) is True

    @pytest.mark.parametrize("value", [
        "python", "Build an ATS system", "layered",
        "postgres", "separation of concerns",
    ])
    def test_allows_real_values(self, value):
        assert is_placeholder(value) is False


class TestAnswerValidation:

    def test_required_empty_rejected(self):
        q = {"field": "name", "required": True}
        assert validate_answer(q, "") is not None

    def test_required_filled_accepted(self):
        q = {"field": "name", "required": True}
        assert validate_answer(q, "my-project-name") is None

    def test_min_length_enforced(self):
        q = {"field": "purpose", "required": True, "min_length": 15}
        assert validate_answer(q, "short") is not None
        assert validate_answer(q, "This is a real purpose for the project") is None

    def test_reject_pattern_enforced(self):
        q = {"field": "language", "required": True,
             "reject_pattern": r"^(any|tbd|TBD|TODO|none)$",
             "reject_msg": "Pick a real language"}
        assert validate_answer(q, "TBD") is not None
        assert validate_answer(q, "python") is None

    def test_placeholder_rejected(self):
        q = {"field": "name", "required": True}
        assert validate_answer(q, "TODO") is not None

    def test_optional_empty_accepted(self):
        q = {"field": "frontend", "required": False}
        assert validate_answer(q, "") is None


class TestFactsFromAnswers:

    def test_builds_valid_facts(self, tmp_path):
        answers = {
            "identity": {"name": "test-project", "version": "0.1.0",
                         "description": "A test project for validation"},
            "goal": {"purpose": "Test the brain builder system thoroughly",
                     "scope": "Unit tests and integration", "out_of_scope": "deployment,monitoring"},
            "stack": {"language": "python", "backend": "fastapi"},
            "architecture": {"pattern": "layered", "reasoning": "Simple and clean separation"},
            "database": {"type": "postgres", "connection": "postgresql://localhost/test"},
            "constraints": {"_list": ["No guessing", "No placeholders"]},
            "success_criteria": {"_list": ["Tests pass", "Brain validates"]},
        }

        brain = build_brain_from_answers(answers)
        assert brain["identity"]["name"] == "test-project"
        assert brain["stack"]["language"] == "python"
        assert len(brain["constraints"]) == 2
        assert len(brain["success_criteria"]) == 2

        output = str(tmp_path / "facts.yaml")
        write_facts(brain, output)
        errors = validate_facts(output)
        assert errors == [], f"Facts should validate: {errors}"


class TestIntentDerivation:

    def test_derives_python_from_intent(self):
        brain = derive_facts_from_intent("Build a FastAPI REST API with PostgreSQL")
        assert brain["stack"]["language"] == "python"
        assert brain["database"]["type"] == "postgres"
        assert brain["stack"].get("backend") == "fastapi"

    def test_derives_typescript_from_intent(self):
        brain = derive_facts_from_intent("Create a React app with Express backend")
        assert brain["stack"]["language"] == "typescript"
        assert brain["stack"].get("backend") == "express"

    def test_marks_unknowns_as_blocking(self):
        brain = derive_facts_from_intent("Build a simple calculator app")
        blocking = [u for u in brain["unresolved"] if u.get("blocking")]
        item_names = [u["item"] for u in blocking]
        assert "Programming language" in item_names
        assert "Project name" in item_names

    def test_always_marks_name_and_criteria_as_blocking(self):
        brain = derive_facts_from_intent("Build a Python FastAPI with MongoDB")
        blocking_items = [u["item"] for u in brain["unresolved"] if u.get("blocking")]
        assert "Project name" in blocking_items
        assert "Success criteria" in blocking_items
        assert "Constraints" in blocking_items

    def test_purpose_contains_intent(self):
        intent = "Build an ATS that scores job fit"
        brain = derive_facts_from_intent(intent)
        assert brain["goal"]["purpose"] == intent


class TestInteractiveBuild:

    def test_interactive_build_with_mocked_input(self, tmp_path):
        """Test the full interactive build flow with simulated inputs."""
        output = str(tmp_path / "facts.yaml")
        inputs = iter([
            "ats-assistant",           # name
            "0.1.0",                   # version
            "AI-powered applicant tracking system",  # description
            "Help job seekers improve their applications",  # purpose
            "MVP scoring engine",      # scope
            "mobile,payments",         # out_of_scope
            "python",                  # language
            "fastapi",                 # backend
            "",                        # frontend (optional)
            "python 3.11+",            # runtime
            "pip",                     # package_manager
            "layered",                 # architecture pattern
            "Clean separation of concerns for maintainability",  # reasoning
            "api,services,models",     # boundaries
            "postgres",                # database type
            "postgresql://localhost/ats",  # connection
            "alembic",                 # migrations
            "No guessing infrastructure",  # constraint 1
            "All routes must have tests",  # constraint 2
            "",                        # end constraints
            "Scores are consistent",   # criterion 1
            "Agent understands project from brain alone",  # criterion 2
            "",                        # end criteria
            "n",                       # skip optional tools
            "n",                       # skip optional roles
        ])

        messages = []

        brain = interactive_build(
            output_path=output,
            input_fn=lambda prompt: next(inputs),
            print_fn=lambda msg: messages.append(msg),
        )

        assert brain["identity"]["name"] == "ats-assistant"
        assert brain["stack"]["language"] == "python"
        assert len(brain["constraints"]) == 2
        assert os.path.exists(output)

        errors = validate_facts(output)
        assert errors == [], f"Interactive facts should validate: {errors}"
