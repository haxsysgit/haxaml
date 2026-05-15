"""Tests for the Haxaml CLI integration point."""

import builtins
import json
import os
import sys

from click.testing import CliRunner
import yaml

from haxaml.cli import cli
from haxaml.export_engine import AGENT_CONFIGS
from haxaml.setup import WORKFLOW_TARGET_IDS
from haxaml.setup.interactive import run_setup_wizard
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
        assert set(target.project_capabilities) == {"instructions", "skills", "agents", "mcp", "workflow"}
        assert set(target.user_capabilities) == {"instructions", "skills", "agents", "mcp", "workflow"}

    claude = get_target("claude")
    assert any(item.path == ".claude/skills/haxaml/SKILL.md" for item in claude.integration_points_for("project"))
    assert claude.project_capabilities["workflow"] is True

    gemini = get_target("gemini")
    project_integration_points = gemini.integration_points_for("project")
    assert any(item.path == ".gemini/skills/haxaml/SKILL.md" for item in project_integration_points)
    assert any(item.path == ".gemini/settings.json" for item in project_integration_points)

    windsurf = get_target("windsurf")
    windsurf_points = windsurf.integration_points_for("project")
    assert any(item.path == ".windsurf/skills/haxaml/SKILL.md" for item in windsurf_points)
    assert set(WORKFLOW_TARGET_IDS) == {"claude", "codex", "gemini", "cursor", "copilot", "opencode", "junie"}


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

        with open(".agents/skills/haxaml/SKILL.md", "r") as f:
            skill = f.read()
        assert skill.startswith("---\n")
        assert "<!-- HAXAML:FILE" not in skill
        assert "metadata:" in skill
        assert "Use When" in skill
        assert "Success Criteria" in skill
        assert "Fallback Path" in skill


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
        assert any(item["preview"] for item in dry_plan["planned_files"])


def test_setup_auto_with_multiple_strong_candidates_does_not_guess():
    runner = CliRunner()

    with runner.isolated_filesystem():
        with open("CLAUDE.md", "w") as f:
            f.write("Existing Claude instructions.\n")
        with open("GEMINI.md", "w") as f:
            f.write("Existing Gemini instructions.\n")
        with open("README.md", "w") as f:
            f.write("# Existing Project\n")

        result = runner.invoke(cli, ["setup"])

        assert result.exit_code == 0, result.output
        assert os.path.exists(".haxaml/adoption/adoption.yaml") is False
        assert os.path.exists(".haxaml/adoption/ADOPTION.md") is False
        assert os.path.exists(".haxaml/setup/targets/claude.md") is False
        assert os.path.exists(".haxaml/setup/targets/gemini.md") is False

        with open(".haxaml/facts.yaml", "r") as f:
            facts = yaml.safe_load(f)
        assert facts["origin"]["mode"] == "fresh"
        assert facts["origin"]["managed_by"] == "haxaml-setup"

        with open("CLAUDE.md", "r") as f:
            claude = f.read()
        assert "Existing Claude instructions." in claude
        assert "HAXAML:MANAGED START" not in claude
        assert "multiple strong provider candidates" in result.output


def test_setup_auto_with_shared_agents_signal_stays_generic_and_fresh():
    runner = CliRunner()

    with runner.isolated_filesystem():
        with open("AGENTS.md", "w") as f:
            f.write("Existing shared agent file.\n")

        result = runner.invoke(cli, ["setup"])

        assert result.exit_code == 0, result.output
        assert os.path.exists(".haxaml/adoption/adoption.yaml") is False
        with open(".haxaml/facts.yaml", "r") as f:
            facts = yaml.safe_load(f)
        assert facts["origin"]["mode"] == "fresh"
        assert "only weak shared signals" in result.output
        assert "Codex" in result.output or "OpenAI Codex" in result.output


def test_setup_auto_with_single_strong_candidate_adopts_that_target():
    runner = CliRunner()

    with runner.isolated_filesystem():
        os.makedirs(".codex", exist_ok=True)
        with open(".codex/config.toml", "w") as f:
            f.write('model = "gpt-5"\n')

        result = runner.invoke(cli, ["setup"])

        assert result.exit_code == 0, result.output
        assert os.path.exists(".haxaml/adoption/adoption.yaml")
        with open(".haxaml/adoption/adoption.yaml", "r") as f:
            adoption = yaml.safe_load(f)
        assert adoption["mode"] == "adopted"
        assert adoption["selected_targets"] == ["codex"]


def test_setup_with_workflow_adds_workflow_assets_and_manifest_entries():
    runner = CliRunner()

    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["setup", "--target", "claude", "--with-workflow"])

        assert result.exit_code == 0, result.output
        assert os.path.exists(".haxaml/setup/workflows/claude/README.md")
        assert os.path.exists(".haxaml/setup/workflows/claude/check.sh")
        assert os.path.exists(".claude/settings.json")

        with open(".haxaml/setup/manifest.yaml", "r") as f:
            manifest = yaml.safe_load(f)
        assert manifest["workflow_enabled"] is True
        assert any(item["kind"] == "workflow" and item["path"] == ".claude/settings.json" for item in manifest["managed_files"])


def test_setup_only_workflow_plans_workflow_assets_only():
    runner = CliRunner()

    with runner.isolated_filesystem():
        result = runner.invoke(
            cli,
            ["setup", "--target", "cursor", "--only", "workflow", "--dry-run", "--format", "json"],
        )

        assert result.exit_code == 0, result.output
        plan = json.loads(result.output)
        assert plan["workflow_enabled"] is True
        assert plan["planned_files"]
        non_manifest = [item for item in plan["planned_files"] if item["path"] != ".haxaml/setup/manifest.yaml"]
        assert non_manifest
        assert {item["kind"] for item in non_manifest} == {"workflow"}
        assert any(item["path"] == ".cursor/environment.json" for item in plan["planned_files"])
        assert os.path.exists(".cursor/environment.json") is False


def test_workflow_check_reports_ready_after_workflow_setup():
    runner = CliRunner()

    with runner.isolated_filesystem():
        setup_result = runner.invoke(cli, ["setup", "--target", "copilot", "--with-workflow"])
        assert setup_result.exit_code == 0, setup_result.output

        check = runner.invoke(cli, ["workflow", "check", "--target", "copilot", "--format", "json"])
        assert check.exit_code == 0, check.output

        payload = json.loads(check.output)
        assert payload["ready"] is True
        assert payload["resolved_targets"] == ["copilot"]
        assert os.path.exists(".github/agents/haxaml-governor.md")
        assert os.path.exists(".mcp.json")


def test_workflow_check_strict_fails_when_required_file_is_missing():
    runner = CliRunner()

    with runner.isolated_filesystem():
        setup_result = runner.invoke(cli, ["setup", "--target", "cursor", "--with-workflow"])
        assert setup_result.exit_code == 0, setup_result.output

        os.remove(".cursor/environment.json")
        check = runner.invoke(cli, ["workflow", "check", "--target", "cursor", "--strict"])

        assert check.exit_code == 1
        assert ".cursor/environment.json" in check.output


def test_setup_doctor_reports_claude_hook_labels_for_missing_and_drift():
    runner = CliRunner()

    with runner.isolated_filesystem():
        setup_result = runner.invoke(cli, ["setup", "--target", "claude", "--with-workflow"])
        assert setup_result.exit_code == 0, setup_result.output

        os.remove(".haxaml/setup/workflows/claude/check.sh")
        with open(".claude/settings.json", "w") as f:
            f.write("{}\n")
        doctor = runner.invoke(cli, ["setup", "doctor"])

        assert doctor.exit_code == 0, doctor.output
        assert ".haxaml/setup/workflows/claude/check.sh" in doctor.output
        assert "Claude hook script" in doctor.output
        assert ".claude/settings.json" in doctor.output
        assert "Claude hook config" in doctor.output
        assert "content drift" in doctor.output


def test_setup_doctor_reports_cursor_background_environment_wording():
    runner = CliRunner()

    with runner.isolated_filesystem():
        setup_result = runner.invoke(cli, ["setup", "--target", "cursor", "--with-workflow"])
        assert setup_result.exit_code == 0, setup_result.output

        os.remove(".cursor/environment.json")
        doctor = runner.invoke(cli, ["setup", "doctor"])

        assert doctor.exit_code == 0, doctor.output
        assert ".cursor/environment.json" in doctor.output
        assert "Cursor background environment" in doctor.output


def test_setup_doctor_reports_copilot_custom_agent_wording():
    runner = CliRunner()

    with runner.isolated_filesystem():
        setup_result = runner.invoke(cli, ["setup", "--target", "copilot", "--with-workflow"])
        assert setup_result.exit_code == 0, setup_result.output

        os.remove(".github/agents/haxaml-governor.md")
        doctor = runner.invoke(cli, ["setup", "doctor"])

        assert doctor.exit_code == 0, doctor.output
        assert ".github/agents/haxaml-governor.md" in doctor.output
        assert "Copilot custom agent" in doctor.output


def test_setup_doctor_reports_workflow_adapter_file_wording():
    runner = CliRunner()

    with runner.isolated_filesystem():
        setup_result = runner.invoke(cli, ["setup", "--target", "gemini", "--with-workflow"])
        assert setup_result.exit_code == 0, setup_result.output

        os.remove(".haxaml/setup/workflows/gemini/README.md")
        doctor = runner.invoke(cli, ["setup", "doctor"])

        assert doctor.exit_code == 0, doctor.output
        assert ".haxaml/setup/workflows/gemini/README.md" in doctor.output
        assert "Gemini adapter file" in doctor.output


def test_setup_doctor_keeps_opencode_manual_follow_up_advisory():
    runner = CliRunner()

    with runner.isolated_filesystem():
        setup_result = runner.invoke(cli, ["setup", "--target", "opencode", "--with-workflow"])
        assert setup_result.exit_code == 0, setup_result.output

        doctor = runner.invoke(cli, ["setup", "doctor"])

        assert doctor.exit_code == 0, doctor.output
        assert "Manual Actions:" in doctor.output
        assert "OpenCode workflow MCP/config entrypoint" in doctor.output
        assert "enable the workflow agent's MCP/tool access" in doctor.output


def test_setup_fresh_mode_preserves_existing_native_files():
    runner = CliRunner()

    with runner.isolated_filesystem():
        with open("CLAUDE.md", "w") as f:
            f.write("Existing Claude instructions.\n")

        result = runner.invoke(cli, ["setup", "--mode", "fresh"])

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


def test_setup_merges_existing_toml_config_without_dropping_other_keys(monkeypatch):
    runner = CliRunner()

    with runner.isolated_filesystem():
        home = os.path.abspath("home")
        os.makedirs(os.path.join(home, ".codex"), exist_ok=True)
        monkeypatch.setenv("HOME", home)
        config_path = os.path.join(home, ".codex", "config.toml")
        with open(config_path, "w") as f:
            f.write('# keep me\nmodel = "gpt-5"\n[profiles.default]\nname = "main"\n')

        result = runner.invoke(cli, ["setup", "--scope", "user", "--target", "codex"])

        assert result.exit_code == 0, result.output
        content = open(config_path).read()
        assert '# keep me' in content
        assert 'model = "gpt-5"' in content
        assert "[profiles.default]" in content
        assert "[mcp_servers.haxaml]" in content
        assert "Merged" in result.output
        assert "mcp_servers.haxaml" in result.output


def test_setup_merges_existing_json_config_without_dropping_other_keys():
    runner = CliRunner()

    with runner.isolated_filesystem():
        os.makedirs(".gemini", exist_ok=True)
        with open(".gemini/settings.json", "w") as f:
            json.dump({"theme": "light", "mcpServers": {"existing": {"command": "node"}}}, f, indent=2)
            f.write("\n")

        result = runner.invoke(cli, ["setup", "--target", "gemini"])

        assert result.exit_code == 0, result.output
        with open(".gemini/settings.json", "r") as f:
            payload = json.load(f)
        assert payload["theme"] == "light"
        assert "existing" in payload["mcpServers"]
        assert "haxaml" in payload["mcpServers"]
        assert "Merged" in result.output
        assert "mcpServers.haxaml" in result.output


def test_setup_conflicting_json_merge_becomes_manual_action():
    runner = CliRunner()

    with runner.isolated_filesystem():
        os.makedirs(".gemini", exist_ok=True)
        with open(".gemini/settings.json", "w") as f:
            json.dump({"mcpServers": []}, f)
            f.write("\n")

        result = runner.invoke(cli, ["setup", "--target", "gemini", "--dry-run", "--format", "json"])

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        manual = next(item for item in payload["manual_actions"] if item["path"] == ".gemini/settings.json")
        assert "unsafe to edit automatically" in manual["action_reason"]
        assert "mcpServers.haxaml" in manual["reason"]
        assert '"mcpServers"' in manual["preview"]


def test_setup_dry_run_text_shows_paths_and_previews():
    runner = CliRunner()

    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["setup", "--dry-run"])

        assert result.exit_code == 0, result.output
        assert "Planned Creates" in result.output
        assert ".haxaml/facts.yaml" in result.output
        assert "preview:" in result.output


def test_setup_wizard_preselects_strong_targets_and_respects_prefilled_flags():
    class FakeBackend:
        def __init__(self):
            self.select_calls = []
            self.checkbox_calls = []
            self.confirm_calls = []
            self._select_results = ["adopted"]
            self._checkbox_results = [["codex"], ["frame", "instructions", "skills", "mcp"]]

        def select(self, *, message, choices, default=None):
            self.select_calls.append({"message": message, "choices": choices, "default": default})
            return self._select_results.pop(0)

        def checkbox(self, *, message, choices, defaults=None):
            self.checkbox_calls.append({"message": message, "choices": choices, "defaults": defaults})
            return self._checkbox_results.pop(0)

        def confirm(self, *, message, default=True):
            self.confirm_calls.append({"message": message, "default": default})
            return True

    runner = CliRunner()
    backend = FakeBackend()

    with runner.isolated_filesystem():
        os.makedirs(".codex", exist_ok=True)
        with open(".codex/config.toml", "w") as f:
            f.write('model = "gpt-5"\n')

        result = run_setup_wizard(
            project_dir=".",
            scope="project",
            target="auto",
            mode="auto",
            only=None,
            with_workflow=True,
            prefilled={"scope", "with_workflow"},
            dry_run=True,
            backend=backend,
        )

        assert result is not None
        assert result.scope == "project"
        assert result.mode == "adopted"
        assert result.targets == ["codex"]
        assert len(backend.select_calls) == 1
        target_call = backend.checkbox_calls[0]
        codex_choice = next(choice for choice in target_call["choices"] if choice["value"] == "codex")
        assert ".codex/config.toml" in codex_choice["name"]
        assert codex_choice["enabled"] is True
        assert len(backend.confirm_calls) == 1


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


def test_setup_doctor_plain_install_keeps_non_workflow_behavior_and_exit_zero():
    runner = CliRunner()

    with runner.isolated_filesystem():
        setup_result = runner.invoke(cli, ["setup"])
        assert setup_result.exit_code == 0, setup_result.output

        doctor = runner.invoke(cli, ["setup", "doctor"])

        assert doctor.exit_code == 0, doctor.output
        assert ".agents/skills/haxaml/SKILL.md" in doctor.output
        assert "workflow" not in doctor.output.lower()


def test_setup_doctor_json_preserves_top_level_shape_and_workflow_metadata():
    runner = CliRunner()

    with runner.isolated_filesystem():
        setup_result = runner.invoke(cli, ["setup", "--target", "claude", "--with-workflow"])
        assert setup_result.exit_code == 0, setup_result.output

        os.remove(".haxaml/setup/workflows/claude/check.sh")
        doctor = runner.invoke(cli, ["setup", "doctor", "--format", "json"])

        assert doctor.exit_code == 0, doctor.output
        report = json.loads(doctor.output)
        assert set(report) == {"installed", "missing", "drifted", "manual_actions", "message"}

        missing_item = next(item for item in report["missing"] if item["path"] == ".haxaml/setup/workflows/claude/check.sh")
        assert missing_item["category"] == "workflow"
        assert missing_item["label"] == "Claude hook script"
        assert "setup --target claude --with-workflow --force" in missing_item["repair_hint"]

        installed_workflow = next(item for item in report["installed"] if item["path"] == ".claude/settings.json")
        assert installed_workflow["category"] == "workflow"
        assert installed_workflow["label"] == "Claude hook config"

        installed_setup = next(item for item in report["installed"] if item["path"] == ".agents/skills/haxaml/SKILL.md")
        assert installed_setup["category"] == "setup"
        assert "label" not in installed_setup
        assert "repair_hint" not in installed_setup


def test_init_does_not_export_agent_files():
    runner = CliRunner()

    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["init", "."])
        assert result.exit_code == 0, result.output
        assert "Run `haxaml setup` or call `haxaml_setup` for onboarding or adoption" in result.output
        assert not os.path.exists("HAXAML.md")
        assert not os.path.exists("CLAUDE.md")
        assert not os.path.exists("AGENTS.md")
        assert not os.path.exists("GEMINI.md")
        assert runner.invoke(cli, ["validate", "--dir", "."]).exit_code == 0


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

        include_ui = runner.invoke(cli, ["upgrade", "--dry-run", "--to", "1.2.3", "--include-ui"])
        assert include_ui.exit_code == 0, include_ui.output
        assert "haxaml-ui==1.2.3" in include_ui.output


def test_cli_about_and_workflow_benchmark_mode():
    runner = CliRunner()

    with runner.isolated_filesystem():
        init = runner.invoke(cli, ["init", "."])
        assert init.exit_code == 0, init.output

        about = runner.invoke(cli, ["about", "--dir", "."])
        assert about.exit_code == 0, about.output
        assert "Haxaml is the governance layer." in about.output
        assert "Run `haxaml setup` or call `haxaml_setup`" in about.output

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


def test_legacy_cli_authoring_and_auto_export_commands_are_removed():
    runner = CliRunner()

    for command in ("build", "derive", "install-hook", "uninstall-hook", "watch"):
        result = runner.invoke(cli, [command])
        assert result.exit_code != 0
        assert "No such command" in result.output
