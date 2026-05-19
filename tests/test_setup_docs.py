"""Tests for setup-release documentation alignment."""

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent


def test_roadmaps_and_changelog_align_on_setup_release_story():
    roadmap_07 = (REPO_ROOT / "0.7.x_Roadmap.md").read_text(encoding="utf-8")
    roadmap_v1 = (REPO_ROOT / "v1.0_Roadmap.md").read_text(encoding="utf-8")
    changelog = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")

    assert "## `0.7.4` - Interactive Setup And Skill Overhaul" in roadmap_07
    assert "## `0.7.5` - Materials, Context Discipline, And Handoff Quality" in roadmap_07
    assert "## `0.7.6` - Setup TUI Correction And Release Hardening" in roadmap_07
    assert "`0.7.4`: interactive setup, provider-aware skills, safe config merges, and preview-first onboarding output" in roadmap_v1
    assert "`0.7.6`: real setup TUI correction, setup trust cleanup, and release-pipeline hardening." in roadmap_v1
    assert "## 0.7.4 - 2026-05-15" in changelog
    assert "## 0.7.6 - 2026-05-19" in changelog
    assert "interactive by default in a real TTY" in changelog
    assert "grouped scaffold summary after apply" in changelog


def test_operator_docs_and_example_flow_match_current_governed_lifecycle():
    example = (REPO_ROOT / "examples" / "minimal-governed-flow" / "README.md").read_text(encoding="utf-8")
    mcp_guide = (REPO_ROOT / "learn" / "haxaml-mcp.md").read_text(encoding="utf-8")
    tool_ref = (REPO_ROOT / "docs" / "mcp-tool-reference.md").read_text(encoding="utf-8")

    assert "haxaml_prebuild" in example
    assert "haxaml_session_start" not in example
    assert 'command = "uvx"' in mcp_guide
    assert 'args = ["haxaml-mcp"]' in mcp_guide
    assert "supported Haxaml MCP surface in `0.7.x`" in tool_ref
