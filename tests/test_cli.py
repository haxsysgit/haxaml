"""Tests for the Haxaml CLI surface."""

import builtins
import json
import os
import sys

from click.testing import CliRunner
import yaml

from haxaml.cli import cli
from haxaml.export_engine import AGENT_CONFIGS
from haxaml.setup.registry import get_target, list_targets

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


def test_setup_registry_covers_documented_targets_and_capabilities():
    targets = list_targets()
    assert any(target.target_id == "generic" for target in targets)
    for target in targets:
        if target.target_id != "generic":
            assert target.docs_urls
        assert set(target.project_capabilities) == {"instructions", "skills", "agents", "mcp"}
        assert set(target.user_capabilities) == {"instructions", "skills", "agents", "mcp"}

    claude = get_target("claude")
    assert any(surface.path == ".claude/skills/haxaml/SKILL.md" for surface in claude.surfaces_for("project"))

    gemini = get_target("gemini")
    project_surfaces = gemini.surfaces_for("project")
    assert any(surface.path == ".gemini/skills/haxaml/SKILL.md" for surface in project_surfaces)
    assert any(surface.path == ".gemini/settings.json" for surface in project_surfaces)


def test_setup_clean_repo_creates_frame_generic_agents_and_skill():
    runner = CliRunner()

    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["setup"])

        assert result.exit_code == 0, result.output
        assert os.path.exists(".haxaml/facts.yaml")
        assert os.path.exists("AGENTS.md")
        assert os.path.exists(".agents/skills/haxaml/SKILL.md")
        assert os.path.exists(".haxaml/setup/manifest.yaml")

        with open(".haxaml/facts.yaml", "r") as f:
            facts = yaml.safe_load(f)
        assert facts["origin"]["mode"] == "fresh"
        assert facts["origin"]["managed_by"] == "haxaml-setup"

        with open("AGENTS.md", "r") as f:
            agents = f.read()
        assert "HAXAML:FILE" in agents
        assert "Lifecycle Checklist" in agents
        assert "Fallback Path" in agents


def test_setup_dry_run_and_print_match_json_without_writing():
    runner = CliRunner()

    with runner.isolated_filesystem():
        dry_run = runner.invoke(cli, ["setup", "--dry-run", "--format", "json"])
        printed = runner.invoke(cli, ["setup", "print", "--format", "json"])

        assert dry_run.exit_code == 0, dry_run.output
        assert printed.exit_code == 0, printed.output

        dry_plan = json.loads(dry_run.output)
        print_plan = json.loads(printed.output)
        assert dry_plan["planned_files"] == print_plan["planned_files"]
        assert os.path.exists(".haxaml") is False


def test_setup_adopt_auto_preserves_native_files_and_writes_adoption_state():
    runner = CliRunner()

    with runner.isolated_filesystem():
        with open("CLAUDE.md", "w") as f:
            f.write("Existing Claude instructions.\n")
        with open("GEMINI.md", "w") as f:
            f.write("Existing Gemini instructions.\n")
        with open("README.md", "w") as f:
            f.write("# Existing Project\n")

        result = runner.invoke(cli, ["setup", "--adopt", "auto"])

        assert result.exit_code == 0, result.output
        assert os.path.exists(".haxaml/adoption/adoption.yaml")
        assert os.path.exists(".haxaml/adoption/ADOPTION.md")
        assert os.path.exists(".haxaml/setup/targets/claude.md")
        assert os.path.exists(".haxaml/setup/targets/gemini.md")

        with open(".haxaml/facts.yaml", "r") as f:
            facts = yaml.safe_load(f)
        assert facts["origin"]["mode"] == "adopted"
        assert facts["origin"]["managed_by"] == "haxaml-setup"

        with open("CLAUDE.md", "r") as f:
            claude = f.read()
        assert "Existing Claude instructions." in claude
        assert "HAXAML:MANAGED START" in claude

        with open(".haxaml/adoption/adoption.yaml", "r") as f:
            adoption = yaml.safe_load(f)
        assert "claude" in adoption["detected_targets"]
        assert "gemini" in adoption["detected_targets"]
        assert adoption["mode"] == "adopted"

        with open(".haxaml/adoption/ADOPTION.md", "r") as f:
            report = f.read()
        assert "Detected Targets" in report
        assert "Managed Sidecars" in report


def test_setup_prompt_can_choose_fresh_without_touching_existing_native_files():
    runner = CliRunner()

    with runner.isolated_filesystem():
        with open("CLAUDE.md", "w") as f:
            f.write("Existing Claude instructions.\n")

        result = runner.invoke(cli, ["setup"], input="fresh\n")

        assert result.exit_code == 0, result.output
        assert os.path.exists(".haxaml/adoption/adoption.yaml") is False
        assert os.path.exists("AGENTS.md")
        with open("CLAUDE.md", "r") as f:
            claude = f.read()
        assert "HAXAML:MANAGED START" not in claude


def test_setup_user_scope_writes_only_home_surfaces(monkeypatch):
    runner = CliRunner()

    with runner.isolated_filesystem():
        home = os.path.abspath("home")
        os.makedirs(home, exist_ok=True)
        monkeypatch.setenv("HOME", home)

        result = runner.invoke(cli, ["setup", "--scope", "user", "--target", "codex"])

        assert result.exit_code == 0, result.output
        assert os.path.exists(".haxaml") is False
        assert os.path.exists("AGENTS.md") is False
        assert os.path.exists(os.path.join(home, ".codex", "AGENTS.md"))
        assert os.path.exists(os.path.join(home, ".codex", "config.toml"))
        assert os.path.exists(os.path.join(home, ".agents", "skills", "haxaml", "SKILL.md"))


def test_setup_doctor_reports_missing_managed_file():
    runner = CliRunner()

    with runner.isolated_filesystem():
        setup_result = runner.invoke(cli, ["setup"])
        assert setup_result.exit_code == 0, setup_result.output

        os.remove(".agents/skills/haxaml/SKILL.md")
        doctor = runner.invoke(cli, ["setup", "doctor"])

        assert doctor.exit_code == 0, doctor.output
        assert "Missing:" in doctor.output
        assert ".agents/skills/haxaml/SKILL.md" in doctor.output


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


def test_cli_prints_install_guidance_when_mcp_runtime_is_missing(monkeypatch):
    runner = CliRunner()
    import haxaml

    if hasattr(haxaml, "mcp_server"):
        delattr(haxaml, "mcp_server")

    for module_name in list(sys.modules):
        if (
            module_name == "haxaml.mcp_server"
            or module_name.startswith("haxaml.mcp")
            or module_name == "mcp"
            or module_name.startswith("mcp.")
        ):
            sys.modules.pop(module_name, None)

    real_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "mcp" or name.startswith("mcp."):
            raise ModuleNotFoundError("No module named 'mcp'")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    result = runner.invoke(cli, ["validate", "--dir", "."])

    assert result.exit_code == 1
    assert "pip install -U haxaml" in result.output


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
