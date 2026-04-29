"""Tests for FRAME/core MCP tools."""

import yaml

from haxaml.mcp_server import (
    haxaml_context,
    haxaml_context_pack,
    haxaml_doctor,
    haxaml_guidance,
    haxaml_health,
    haxaml_init,
    haxaml_validate,
)
from haxaml.versioning import get_version

from .helpers import msg as _msg


class TestInit:
    def test_creates_frame_files(self, tmp_path):
        result = haxaml_init(str(tmp_path))
        assert result["ok"] is True
        assert "Initialized FRAME" in _msg(result)
        assert (tmp_path / ".haxaml" / "facts.yaml").exists()
        assert (tmp_path / ".haxaml" / "rules.yaml").exists()
        assert (tmp_path / ".haxaml" / "acts.yaml").exists()
        assert (tmp_path / ".haxaml" / "expect.yaml").exists()

    def test_does_not_overwrite_existing(self, fresh_project):
        result = haxaml_init(str(fresh_project))
        assert result["ok"] is True
        assert "already exists" in _msg(result)

    def test_syncs_rules_governance_version_for_existing_project(self, fresh_project):
        rules_path = fresh_project / ".haxaml" / "rules.yaml"
        rules = yaml.safe_load(rules_path.read_text())
        rules["governance"]["version"] = "0.0.1"
        rules_path.write_text(yaml.dump(rules, default_flow_style=False, sort_keys=False))

        result = haxaml_init(str(fresh_project))
        assert result["ok"] is True
        assert "already exists" in _msg(result)
        assert "Synced .haxaml/rules.yaml governance.version" in _msg(result)

        synced = yaml.safe_load(rules_path.read_text())
        assert synced["governance"]["version"] == get_version()

    def test_scaffolds_validate(self, fresh_project):
        result = haxaml_validate(str(fresh_project))
        assert result["ok"] is True
        assert "facts.yaml is valid" in _msg(result)


class TestValidate:
    def test_all_valid(self, governed_project):
        result = haxaml_validate(str(governed_project))
        text = _msg(result)
        assert result["ok"] is True
        assert "All FRAME files valid" in text
        assert "facts.yaml is valid" in text
        assert "rules.yaml is valid" in text
        assert "acts.yaml is valid" in text
        assert "expect.yaml is valid" in text

    def test_missing_facts_fails(self, tmp_path):
        result = haxaml_validate(str(tmp_path))
        assert result["ok"] is False
        assert "facts.yaml not found" in result["error"]["details"]["message"]

    def test_invalid_facts_reports_errors(self, governed_project):
        (governed_project / ".haxaml" / "facts.yaml").write_text("bad: true\n")
        result = haxaml_validate(str(governed_project))
        assert result["ok"] is False
        assert "facts.yaml" in result["error"]["details"]["message"]

    def test_fails_when_complexity_requires_map_but_map_missing(self, governed_project):
        rules_path = governed_project / ".haxaml" / "rules.yaml"
        rules = yaml.safe_load(rules_path.read_text())
        rules["boundaries"]["modules"] = {
            "api": {"touches": ["auth", "db"]},
            "auth": {"touches": ["db"]},
            "db": {"touches": []},
        }
        rules_path.write_text(yaml.dump(rules, default_flow_style=False, sort_keys=False))

        expect_path = governed_project / ".haxaml" / "expect.yaml"
        expect = yaml.safe_load(expect_path.read_text())
        expect["planning"]["map_required"] = False
        expect["map_policy"]["module_threshold"] = 3
        expect_path.write_text(yaml.dump(expect, default_flow_style=False, sort_keys=False))

        result = haxaml_validate(str(governed_project))
        details = result["error"]["details"]["message"]
        assert result["ok"] is False
        assert "map policy: map.yaml is required" in details
        assert "Validation failed" in details

    def test_fails_on_blocking_derivation_conflicts(self, governed_project):
        map_data = {
            "modules": [
                {"name": "auth", "purpose": "Auth", "files": ["src/auth/"]},
                {"name": "api", "purpose": "API", "files": ["src/api/"]},
            ],
            "dependencies": [{"from": "api", "to": "auth", "reason": "auth middleware"}],
            "impact": [{"when": "auth", "check": ["api tests"]}],
        }
        (governed_project / ".haxaml" / "map.yaml").write_text(
            yaml.dump(map_data, default_flow_style=False, sort_keys=False)
        )

        result = haxaml_validate(str(governed_project))
        assert result["ok"] is False
        assert result["error"]["code"] == "derivation_conflicts"
        assert result["error"]["details"]["reconcile"]["severity_totals"]["blocking"] > 0


class TestContext:
    def test_returns_context_with_tokens(self, governed_project):
        result = haxaml_context(str(governed_project))
        text = _msg(result)
        assert result["ok"] is True
        assert "Project Facts" in text
        assert "Token count:" in text

    def test_without_state(self, governed_project):
        result = haxaml_context(str(governed_project), include_state=False)
        text = _msg(result)
        assert result["ok"] is True
        assert "Project Facts" in text
        assert "Current Acts" not in text

    def test_context_pack_contains_expected_sections(self, governed_project):
        result = haxaml_context_pack(
            task="implement auth module",
            project_dir=str(governed_project),
            pack="balanced",
            include_state=True,
        )
        assert result["ok"] is True
        data = result["data"]
        assert data["pack"] == "balanced"
        assert data["tokens"] > 0
        assert "included_sections" in data
        assert "omitted_sections" in data
        assert "omitted_context" in data
        assert "context_window_usage" in data
        assert "context_pack" not in data

    def test_context_pack_full_detail_keeps_structured_payload(self, governed_project):
        result = haxaml_context_pack(
            task="implement auth module",
            project_dir=str(governed_project),
            pack="balanced",
            include_state=True,
            detail="full",
        )
        assert result["ok"] is True
        data = result["data"]
        assert data["pack"] == "balanced"
        assert "context_window_usage" in data["context_pack"]["_meta"]
        assert "essential_facts" in data["context_pack"]
        assert "relevant_rules" in data["context_pack"]

    def test_context_pack_accepts_standard_alias(self, governed_project):
        result = haxaml_context_pack(
            task="implement auth module",
            project_dir=str(governed_project),
            pack="standard",
            include_state=True,
            detail="full",
        )
        assert result["ok"] is True
        assert result["data"]["pack"] == "balanced"
        assert result["data"]["context_pack"]["pack"] == "balanced"

    def test_scaffold_context_pack_avoids_blank_rule_entries(self, fresh_project):
        result = haxaml_context_pack(
            task="scaffold smoke check",
            project_dir=str(fresh_project),
            pack="balanced",
            include_state=True,
            detail="full",
        )
        assert result["ok"] is True
        rules = result["data"]["context_pack"]["relevant_rules"]
        for key in ("checks", "boundaries", "forbidden", "after_verify"):
            values = rules.get(key, [])
            assert all(isinstance(v, str) and v.strip() for v in values)


class TestDetailMode:
    def test_invalid_detail_returns_error(self, governed_project):
        result = haxaml_guidance(
            task="implement auth module",
            project_dir=str(governed_project),
            detail="verbose",
        )
        assert result["ok"] is False
        assert result["error"]["code"] == "invalid_detail"

    def test_guidance_full_detail_includes_extended_fields(self, governed_project):
        short_result = haxaml_guidance(task="implement auth module", project_dir=str(governed_project))
        full_result = haxaml_guidance(
            task="implement auth module",
            project_dir=str(governed_project),
            detail="full",
        )
        assert short_result["ok"] is True
        assert full_result["ok"] is True
        assert "missing_context" not in short_result["data"]
        assert "missing_context" in full_result["data"]


class TestHealth:
    def test_healthy_project(self, governed_project):
        result = haxaml_health(str(governed_project))
        text = _msg(result)
        assert result["ok"] is True
        assert "Project:    test-project" in text
        assert "Ready:      " in text
        assert "Facts:      " in text

    def test_missing_project(self, tmp_path):
        result = haxaml_health(str(tmp_path))
        assert result["ok"] is False


class TestDoctor:
    def test_complete_facts(self, governed_project):
        result = haxaml_doctor(str(governed_project))
        text = _msg(result)
        assert result["ok"] is True
        assert "complete" in text or "recommendation" in text

    def test_missing_facts(self, tmp_path):
        result = haxaml_doctor(str(tmp_path))
        assert result["ok"] is False
        assert "not found" in result["error"]["message"]
