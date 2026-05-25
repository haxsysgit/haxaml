"""Tests for MCP resource endpoints."""

from haxaml.mcp_server import (
    resource_acts,
    resource_expect,
    resource_facts,
    resource_map,
    resource_rules,
)


class TestResources:
    def test_facts_resource(self, governed_project, monkeypatch):
        monkeypatch.setenv("HAXAML_PROJECT_DIR", str(governed_project))
        content = resource_facts()
        assert "stable_project_truth" in content

    def test_rules_resource(self, governed_project, monkeypatch):
        monkeypatch.setenv("HAXAML_PROJECT_DIR", str(governed_project))
        content = resource_rules()
        assert "project_constraints" in content

    def test_acts_resource(self, governed_project, monkeypatch):
        monkeypatch.setenv("HAXAML_PROJECT_DIR", str(governed_project))
        content = resource_acts()
        assert "checked_activity_record" in content

    def test_expect_resource(self, governed_project, monkeypatch):
        monkeypatch.setenv("HAXAML_PROJECT_DIR", str(governed_project))
        content = resource_expect()
        assert "planned_direction" in content

    def test_map_resource_missing(self, governed_project, monkeypatch):
        monkeypatch.setenv("HAXAML_PROJECT_DIR", str(governed_project))
        content = resource_map()
        assert "not found" in content
