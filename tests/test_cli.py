"""Tests for the Haxaml CLI surface."""

from click.testing import CliRunner
import yaml

from haxaml.cli import cli
from haxaml.adoption import scan_native_sources
from haxaml.export_engine import AGENT_CONFIGS


def test_init_scaffolds_full_frame():
    runner = CliRunner()

    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["init", "."])

        assert result.exit_code == 0, result.output
        assert ".haxaml/facts.yaml — fill in project truth" in result.output
        assert ".haxaml/rules.yaml — define agent rules" in result.output
        assert ".haxaml/acts.yaml — diary starts here" in result.output
        assert ".haxaml/expect.yaml — plan your runs" in result.output

        validate = runner.invoke(cli, ["validate", "--dir", "."])

        assert validate.exit_code == 0, validate.output
        assert "facts.yaml is valid" in validate.output
        assert "rules.yaml is valid" in validate.output
        assert "acts.yaml is valid" in validate.output
        assert "expect.yaml is valid" in validate.output


def test_export_supports_current_native_agent_files():
    assert AGENT_CONFIGS["claude"]["filename"] == "CLAUDE.md"
    assert AGENT_CONFIGS["codex"]["filename"] == "AGENTS.md"
    assert AGENT_CONFIGS["copilot"]["filename"] == ".github/copilot-instructions.md"
    assert AGENT_CONFIGS["cursor"]["filename"] == ".cursor/rules/haxaml.mdc"
    assert AGENT_CONFIGS["windsurf"]["filename"] == ".windsurf/rules/haxaml.md"
    assert AGENT_CONFIGS["gemini"]["filename"] == "GEMINI.md"


def test_adopt_dry_run_scans_native_agent_files_without_writing():
    runner = CliRunner()

    with runner.isolated_filesystem():
        with open("CLAUDE.md", "w") as f:
            f.write("Use pytest.\n")
        with open("AGENTS.md", "w") as f:
            f.write("Follow repo rules.\n")
        with open("README.md", "w") as f:
            f.write("# Existing Project\n")

        result = runner.invoke(cli, ["adopt", "--from-native"])

        assert result.exit_code == 0, result.output
        assert "Claude Code: `CLAUDE.md`" in result.output
        assert "OpenAI Codex: `AGENTS.md`" in result.output
        assert "`README.md`" in result.output
        assert "Dry run. Call with write=True to create files." in result.output

        assert scan_native_sources(".").native_files
        assert runner.invoke(cli, ["validate", "--dir", "."]).exit_code != 0


def test_adopt_write_creates_valid_frame_scaffold_and_report():
    runner = CliRunner()

    with runner.isolated_filesystem():
        with open("CLAUDE.md", "w") as f:
            f.write("Existing Claude instructions.\n")
        with open("GEMINI.md", "w") as f:
            f.write("Existing Gemini instructions.\n")
        with open("README.md", "w") as f:
            f.write("# Existing Project\n")

        result = runner.invoke(cli, ["adopt", "--from-native", "--write"])

        assert result.exit_code == 0, result.output
        assert "wrote .haxaml/ADOPTION.md" in result.output
        assert "wrote .haxaml/facts.yaml" in result.output
        assert "wrote .haxaml/rules.yaml" in result.output
        assert "wrote .haxaml/acts.yaml" in result.output
        assert "wrote .haxaml/expect.yaml" in result.output

        validate = runner.invoke(cli, ["validate", "--dir", "."])
        assert validate.exit_code == 0, validate.output

        with open(".haxaml/facts.yaml") as f:
            facts = yaml.safe_load(f)
        assert facts["unresolved"][0]["blocking"] is True
        assert "CLAUDE.md" in facts["tools"]["other"]
        assert "GEMINI.md" in facts["tools"]["other"]


def test_adopt_write_preserves_existing_frame_without_force():
    runner = CliRunner()

    with runner.isolated_filesystem():
        with open("CLAUDE.md", "w") as f:
            f.write("Existing Claude instructions.\n")

        runner.invoke(cli, ["init", "."])
        with open(".haxaml/facts.yaml", "r") as f:
            original_facts = f.read()

        result = runner.invoke(cli, ["adopt", "--from-native", "--write"])

        assert result.exit_code == 0, result.output
        assert "Preserved existing:" in result.output
        with open(".haxaml/facts.yaml", "r") as f:
            assert f.read() == original_facts


def test_init_auto_reexports_agent_files():
    runner = CliRunner()

    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["init", "."])
        assert result.exit_code == 0, result.output
        assert "↻ Auto-exported" in result.output
        assert runner.invoke(cli, ["validate", "--dir", "."]).exit_code == 0
        assert runner.invoke(cli, ["export", "--all", "--quiet"]).output == ""


def test_cli_needs_and_impact_commands():
    runner = CliRunner()

    with runner.isolated_filesystem():
        init = runner.invoke(cli, ["init", "."])
        assert init.exit_code == 0, init.output

        needs = runner.invoke(cli, ["needs", "--dir", "."])
        assert needs.exit_code == 0, needs.output
        assert "Active run requirements" in needs.output

        impact = runner.invoke(cli, ["impact", "auth", "--dir", "."])
        assert impact.exit_code == 0, impact.output
        assert "map.yaml not found" in impact.output
