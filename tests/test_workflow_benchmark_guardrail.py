"""Guardrails for workflow-level token benchmarks used in CI."""

from haxaml.mcp_server import haxaml_benchmark


def test_workflow_token_guardrails():
    result = haxaml_benchmark(mode="workflow")
    assert result["ok"] is True

    data = result["data"]
    profiles = data["profiles"]

    assert profiles["essential_short"]["payload_tokens"] <= 2100
    assert profiles["expanded_short"]["payload_tokens"] <= 2700
    assert profiles["essential_full"]["payload_tokens"] <= 3700
    assert profiles["expanded_short"]["call_count"] > profiles["essential_short"]["call_count"]
    assert profiles["essential_full"]["call_count"] == profiles["essential_short"]["call_count"]
    assert "transport_overhead" in data
    assert "haxaml_about" in {call["tool"] for call in profiles["essential_short"]["calls"]}
