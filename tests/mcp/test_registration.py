"""Tests for MCP server registration and compatibility entrypoint."""

from haxaml.mcp_server import main, mcp_app


class TestServerRegistration:
    def test_tool_count(self):
        tools = mcp_app._tool_manager._tools
        assert len(tools) >= 25

    def test_expected_tools_registered(self):
        tools = mcp_app._tool_manager._tools
        expected = [
            "haxaml_about",
            "haxaml_init",
            "haxaml_validate",
            "haxaml_context",
            "haxaml_health",
            "haxaml_doctor",
            "haxaml_run",
            "haxaml_done",
            "haxaml_export",
            "haxaml_upgrade",
            "haxaml_mcp_bootstrap",
            "haxaml_adopt_plan",
            "haxaml_reconcile",
            "haxaml_adopt",
            "haxaml_needs",
            "haxaml_impact",
            "haxaml_state_show",
            "haxaml_state_compact",
            "haxaml_benchmark",
            "haxaml_context_pack",
            "haxaml_guidance",
            "haxaml_session_start",
            "haxaml_session_plan",
            "haxaml_session_verify",
            "haxaml_session_record",
        ]
        for name in expected:
            assert name in tools, f"Tool {name} not registered"

    def test_server_name(self):
        assert mcp_app.name == "haxaml"


class TestCompatibilityEntrypoint:
    def test_main_entrypoint_is_importable(self):
        assert callable(main)
