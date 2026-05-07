"""Tests for the Haxaml CLI surface."""

import os

from click.testing import CliRunner
import yaml

from haxaml.cli import cli
from haxaml.adoption import scan_native_sources
from haxaml.export_engine import AGENT_CONFIGS

COMMIT_STYLE_DISCIPLINE = "Do not use commit prefixes like fix:, feat:, refactor:, chore:, or docs:."


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

        with open(".haxaml/rules.yaml", "r") as f:
            rules = yaml.safe_load(f)
        discipline = rules.get("while_coding", {}).get("discipline", [])
        assert COMMIT_STYLE_DISCIPLINE in discipline


def test_export_supports_current_native_agent_files():
    assert AGENT_CONFIGS["claude"]["filename"] == "CLAUDE.md"
    assert AGENT_CONFIGS["codex"]["filename"] == "haxaml-agents.md"
    assert AGENT_CONFIGS["codex"]["native_filename"] == "AGENTS.md"
    assert AGENT_CONFIGS["copilot"]["filename"] == ".github/copilot-instructions.md"
    assert AGENT_CONFIGS["cursor"]["filename"] == ".cursor/rules/haxaml.mdc"
    assert AGENT_CONFIGS["windsurf"]["filename"] == ".windsurf/rules/haxaml.md"
    assert AGENT_CONFIGS["gemini"]["filename"] == "GEMINI.md"
    assert AGENT_CONFIGS["generic"]["filename"] == "HAXAML.md"


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

        with open(".haxaml/rules.yaml", "r") as f:
            rules = yaml.safe_load(f)
        discipline = rules.get("while_coding", {}).get("discipline", [])
        assert COMMIT_STYLE_DISCIPLINE in discipline

        with open(".haxaml/ADOPTION.md", "r") as f:
            report = f.read()
        assert "## Instruction Analysis" in report


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


def test_adopt_plan_and_reconcile_commands():
    runner = CliRunner()

    with runner.isolated_filesystem():
        with open("CLAUDE.md", "w") as f:
            f.write("Use tests.\n")
        with open("README.md", "w") as f:
            f.write("# Project\n")

        plan = runner.invoke(cli, ["adopt-plan", "--dir", "."])
        assert plan.exit_code == 0, plan.output
        assert "Inventory complete" in plan.output

        init = runner.invoke(cli, ["init", "."])
        assert init.exit_code == 0, init.output

        reconcile = runner.invoke(cli, ["reconcile", "--dir", "."])
        assert reconcile.exit_code == 0, reconcile.output
        assert "No map.yaml found" in reconcile.output or "No derivation conflicts detected" in reconcile.output


def test_init_auto_reexports_agent_files():
    runner = CliRunner()

    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["init", "."])
        assert result.exit_code == 0, result.output
        assert "↻ Auto-exported" in result.output
        assert os.path.exists("HAXAML.md")
        assert not os.path.exists("CLAUDE.md")
        assert not os.path.exists("AGENTS.md")
        assert not os.path.exists("GEMINI.md")
        assert runner.invoke(cli, ["export", "--quiet"]).exit_code == 0
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


def test_codex_export_defaults_to_haxaml_agents_without_overwriting_native_agents():
    runner = CliRunner()

    with runner.isolated_filesystem():
        init = runner.invoke(cli, ["init", "."])
        assert init.exit_code == 0, init.output

        with open("AGENTS.md", "w") as f:
            f.write("human-written codex instructions\n")

        export = runner.invoke(cli, ["export", "--agent", "codex"])
        assert export.exit_code == 0, export.output
        assert "haxaml-agents.md" in export.output
        assert "human-written codex instructions" in open("AGENTS.md").read()
        assert "Generated by Haxaml from FRAME" in open("haxaml-agents.md").read()


def test_codex_export_override_native_replaces_agents_md():
    runner = CliRunner()

    with runner.isolated_filesystem():
        init = runner.invoke(cli, ["init", "."])
        assert init.exit_code == 0, init.output

        with open("AGENTS.md", "w") as f:
            f.write("human-written codex instructions\n")

        export = runner.invoke(cli, ["export", "--agent", "codex", "--override-native"])
        assert export.exit_code == 0, export.output
        assert "AGENTS.md" in export.output
        assert "Generated by Haxaml from FRAME" in open("AGENTS.md").read()


def test_export_target_alias_writes_custom_file():
    runner = CliRunner()

    with runner.isolated_filesystem():
        init = runner.invoke(cli, ["init", "."])
        assert init.exit_code == 0, init.output

        export = runner.invoke(cli, ["export", "--target", "TEAM_GUIDE.md"])
        assert export.exit_code == 0, export.output
        assert os.path.exists("TEAM_GUIDE.md")
        assert "Generated by Haxaml from FRAME" in open("TEAM_GUIDE.md").read()


def test_export_rejects_both_output_and_target():
    runner = CliRunner()

    with runner.isolated_filesystem():
        init = runner.invoke(cli, ["init", "."])
        assert init.exit_code == 0, init.output

        export = runner.invoke(
            cli,
            ["export", "--output", "one.md", "--target", "two.md"],
        )
        assert export.exit_code != 0
        assert "Use only one of --output or --target." in export.output


def test_export_dry_run_with_diff_preview_does_not_write_target():
    runner = CliRunner()

    with runner.isolated_filesystem():
        init = runner.invoke(cli, ["init", "."])
        assert init.exit_code == 0, init.output

        export = runner.invoke(
            cli,
            ["export", "--dry-run", "--diff-preview", "--target", "CLAUDE.md"],
        )
        assert export.exit_code == 0, export.output
        assert os.path.exists("CLAUDE.md") is False
        assert "Dry run complete" in export.output


def test_dashboard_prints_install_guidance_when_ui_extra_is_missing(monkeypatch):
    runner = CliRunner()

    with runner.isolated_filesystem():
        os.mkdir(".haxaml")

        import haxaml.cli as cli_module

        original_find_spec = cli_module.importlib.util.find_spec

        def fake_find_spec(name):
            if name == "starlette":
                return None
            return original_find_spec(name)

        monkeypatch.setattr(cli_module.importlib.util, "find_spec", fake_find_spec)
        result = runner.invoke(cli, ["dashboard", "--project-dir", ".", "--no-open"])

        assert result.exit_code == 1
        assert 'pip install "haxaml[ui]"' in result.output


def test_dashboard_resolves_project_root_and_passes_launcher_flags(monkeypatch):
    runner = CliRunner()
    captured = {}

    with runner.isolated_filesystem():
        os.mkdir(".haxaml")
        os.mkdir("nested")

        import haxaml.cli as cli_module

        def fake_runner(**kwargs):
            captured.update(kwargs)
            return "http://127.0.0.1:9001/"

        monkeypatch.setattr(cli_module, "_load_dashboard_runtime", lambda: fake_runner)
        cwd = os.getcwd()
        try:
            os.chdir("nested")
            result = runner.invoke(cli, ["dashboard", "--project-dir", ".", "--host", "127.0.0.1", "--port", "9001", "--no-open"])
        finally:
            os.chdir(cwd)

        assert result.exit_code == 0, result.output
        assert "http://127.0.0.1:9001/" in result.output
        assert captured["project_dir"].endswith(os.sep + os.path.basename(cwd))
        assert captured["host"] == "127.0.0.1"
        assert captured["port"] == 9001
        assert captured["open_browser"] is False
        assert captured["read_only"] is True


def test_upgrade_dry_run_prints_uv_command():
    runner = CliRunner()

    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["upgrade", "--dry-run", "--to", "1.2.3"])
        assert result.exit_code == 0, result.output
        assert "uv tool upgrade haxaml==1.2.3 haxaml-mcp==1.2.3" in result.output


def test_mcp_bootstrap_write_creates_project_config():
    runner = CliRunner()

    with runner.isolated_filesystem():
        result = runner.invoke(
            cli,
            ["mcp-bootstrap", "--mode", "write", "--editor", "generic"],
        )
        assert result.exit_code == 0, result.output
        assert os.path.exists(".mcp.json")


def test_cli_about_and_workflow_benchmark_mode():
    runner = CliRunner()

    with runner.isolated_filesystem():
        init = runner.invoke(cli, ["init", "."])
        assert init.exit_code == 0, init.output

        about = runner.invoke(cli, ["about", "--dir", "."])
        assert about.exit_code == 0, about.output
        assert "Haxaml is the governance layer." in about.output
        assert "Next: haxaml_guidance." in about.output

        benchmark = runner.invoke(cli, ["benchmark", "--mode", "workflow", "--dir", "."])
        assert benchmark.exit_code == 0, benchmark.output
        assert "Workflow benchmark complete" in benchmark.output


def test_cli_prebuild_command_invokes_mcp_tool(monkeypatch):
    runner = CliRunner()
    calls = {}

    class DummyMcpTools:
        def haxaml_prebuild(self, *, task, description, project_dir):
            calls["task"] = task
            calls["description"] = description
            calls["project_dir"] = project_dir
            return {
                "ok": True,
                "tool": "haxaml_prebuild",
                "data": {
                    "message": "Prebuild complete: ready_to_build",
                },
            }

    monkeypatch.setattr("haxaml.cli._mcp_tools", lambda: DummyMcpTools())

    result = runner.invoke(
        cli,
        ["prebuild", "--dir", ".", "--task", "Refactor auth", "--description", "Tighten token flow"],
    )

    assert result.exit_code == 0, result.output
    assert "Prebuild complete: ready_to_build" in result.output
    assert calls == {
        "task": "Refactor auth",
        "description": "Tighten token flow",
        "project_dir": ".",
    }
