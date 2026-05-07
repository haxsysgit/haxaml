"""Tests for benchmark MCP tool wrapper behavior."""

from haxaml.mcp_server import haxaml_benchmark


class TestBenchmarkTool:
    def test_workflow_mode_returns_profiles_and_guardrails(self, fresh_project):
        result = haxaml_benchmark(str(fresh_project), mode="workflow")
        assert result["ok"] is True
        data = result["data"]
        assert data["mode"] == "workflow"
        assert "profiles" in data
        assert "essential_short" in data["profiles"]
        assert "repeat_refresh_short" in data["profiles"]
        assert "guardrails" in data
        assert "results" in data["guardrails"]

    def test_invalid_benchmark_mode_fails(self, fresh_project):
        result = haxaml_benchmark(str(fresh_project), mode="invalid")
        assert result["ok"] is False
        assert result["error"]["code"] == "invalid_mode"
