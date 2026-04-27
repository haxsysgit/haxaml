"""Tests for token efficiency benchmarks."""

import os

import pytest
import yaml

from haxaml.benchmarks import (
    benchmark_format_tokens,
    benchmark_parse_speed,
    simulate_state_growth,
    measure_context_budget,
    format_benchmark_report,
)


def _make_facts(tmp_path):
    facts = {
        "identity": {"name": "bench-project", "version": "0.1.0",
                      "description": "Benchmark test project"},
        "goal": {"purpose": "Test token efficiency across formats",
                 "scope": "benchmarks only"},
        "stack": {"language": "python", "backend": "fastapi"},
        "architecture": {"pattern": "layered",
                         "reasoning": "Simple and testable"},
        "database": {"type": "postgres",
                     "connection": "postgresql://localhost/bench"},
        "constraints": ["No guessing", "Minimal context"],
        "success_criteria": ["Benchmarks complete", "Results are measurable"],
    }
    path = str(tmp_path / "facts.yaml")
    with open(path, "w") as f:
        yaml.dump(facts, f, default_flow_style=False, sort_keys=False)
    return path


class TestFormatComparison:

    def test_compares_formats(self, tmp_path):
        facts_path = _make_facts(tmp_path)
        result = benchmark_format_tokens(facts_path)

        assert "yaml" in result
        assert "json_pretty" in result
        assert "json_compact" in result
        assert result["winner"] in ("yaml", "json_pretty", "json_compact")

        for fmt in ("yaml", "json_pretty", "json_compact"):
            assert result[fmt]["tokens"] > 0
            assert result[fmt]["chars"] > 0
            assert result[fmt]["bytes"] > 0

    def test_compact_json_fewer_tokens_than_pretty(self, tmp_path):
        facts_path = _make_facts(tmp_path)
        result = benchmark_format_tokens(facts_path)
        assert result["json_compact"]["tokens"] <= result["json_pretty"]["tokens"]


class TestParseSpeed:

    def test_measures_speed(self, tmp_path):
        facts_path = _make_facts(tmp_path)
        result = benchmark_parse_speed(facts_path, iterations=10)

        assert result["yaml_ms"] > 0
        assert result["json_ms"] > 0
        assert result["ratio"] > 0
        assert result["iterations"] == 10

    def test_json_faster_than_yaml(self, tmp_path):
        facts_path = _make_facts(tmp_path)
        result = benchmark_parse_speed(facts_path, iterations=50)
        assert result["json_ms"] < result["yaml_ms"]


class TestStateGrowth:

    def test_simulates_growth(self):
        base = {"current_phase": "test", "active_task": {"name": "test"}}
        measurements = simulate_state_growth(base, num_runs=20)

        assert len(measurements) == 20
        assert measurements[0]["run_number"] == 1
        assert measurements[-1]["run_number"] == 20
        assert measurements[-1]["yaml_tokens"] > measurements[0]["yaml_tokens"]

    def test_growth_is_linear(self):
        base = {"current_phase": "test", "active_task": {"name": "test"}}
        measurements = simulate_state_growth(base, num_runs=50)

        first = measurements[0]["yaml_tokens"]
        last = measurements[-1]["yaml_tokens"]
        mid = measurements[24]["yaml_tokens"]

        assert mid < last
        assert first < mid


class TestContextBudget:

    def test_measures_budget(self, tmp_path):
        _make_facts(tmp_path)
        acts = {
            "current_phase": "Phase 1",
            "active_task": {"name": "test"},
        }
        with open(tmp_path / "acts.yaml", "w") as f:
            yaml.dump(acts, f)

        result = measure_context_budget(str(tmp_path))
        assert "facts" in result
        assert "acts" in result
        assert "total" in result
        assert result["total"]["tokens"] > 0
        assert result["total"]["budget_4k_pct"] > 0


class TestReport:

    def test_generates_report(self, tmp_path):
        facts_path = _make_facts(tmp_path)
        report = format_benchmark_report(facts_path)

        assert "Format Comparison" in report
        assert "Parse Speed" in report
        assert "State Growth" in report
        assert "Growth factor" in report

    def test_full_report_with_project(self, tmp_path):
        facts_path = _make_facts(tmp_path)
        acts = {"current_phase": "test", "active_task": {"name": "test"}}
        with open(tmp_path / "acts.yaml", "w") as f:
            yaml.dump(acts, f)

        report = format_benchmark_report(facts_path, str(tmp_path))
        assert "Context Token Budget" in report
        assert "Total:" in report
