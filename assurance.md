# Haxaml Assurance Check

Scope: answers to questions 1–7.5, with implementation evidence from the current codebase.

## 1) Does Haxaml manage token usage, and how?

Verdict: **Yes (Done)**

Evidence files:
- `haxaml/context.py` (token counting + context window usage metadata)
- `haxaml/mcp/tools_lifecycle.py` (context-pack anti-bloat policy and token metrics in MCP outputs)
- `haxaml/mcp/policy_helpers.py` (repeat/gate policy helpers)
- `haxaml/benchmarks.py` + `haxaml/mcp/tools_benchmark.py` benchmark mode (token budget measurements/guardrails)
- `haxaml/runner.py` (preflight context token warning)

Code blocks:
```python
# haxaml/context.py:198-202
token_count = count_tokens(pack_text)
pack_data["_meta"] = {
    "token_count": token_count,
    "context_window_usage": _token_window_usage(token_count),
    ...
}
```

```python
# haxaml/context.py:510-513, 677-684
def _token_window_usage(tokens: int) -> dict[str, float]:
    budgets = [4000, 8000, 32000, 128000]
    return {f"pct_{size}": round((tokens / size) * 100, 2) for size in budgets}

def count_tokens(text: str, model: str = "cl100k_base") -> int:
    import tiktoken
    enc = tiktoken.get_encoding(model)
    return len(enc.encode(text))
```

```python
# haxaml/mcp/tools_lifecycle.py
if prior_calls >= 1 and not refresh_reason:
    return _err(
        "haxaml_context_pack",
        "context_pack_refresh_reason_required",
        "Context pack already generated for this session. Repeat only when scope changed or context is stale...",
        ...
    )
```

```python
# haxaml/runner.py:123-127
result.context_tokens = count_tokens(ctx)
if result.context_tokens > 8000:
    result.warnings.append(
        f"Context is {result.context_tokens} tokens — consider reducing for smaller models"
    )
```

Brief code explanation:
- Haxaml counts tokens for context outputs, computes window usage percentages, stores them in metadata, exposes token numbers in MCP responses, and applies anti-bloat controls (one context pack per task unless refresh reason is provided).

---

## 2) Does Haxaml have an internal engine that validates FRAME files?

Verdict: **Yes (Done)**

Evidence files:
- `haxaml/validator.py`
- `haxaml/mcp/tools_frame.py` (`haxaml_validate`)

Code blocks:
```python
# haxaml/validator.py:31-37
schema = load_schema("facts.schema.yaml")
data = load_yaml(facts_path)
validator = Draft202012Validator(schema)
for error in sorted(validator.iter_errors(data), key=lambda e: list(e.path)):
    ...
```

```python
# haxaml/mcp/tools_frame.py
checks = [
    ("facts.yaml", "brain.yaml", validate_facts),
    ("rules.yaml", "mind.yaml", validate_rules),
    ("acts.yaml", "state.yaml", validate_acts),
]
```

```python
# haxaml/mcp/tools_frame.py
reconcile = reconcile_derivation(p)
lines.append(f"• Reconcile: {reconcile['human_summary']}")
...
if reconcile["severity_totals"]["blocking"] > 0:
    all_valid = False
```

Brief code explanation:
- Validation is schema-driven (`jsonschema`) for each FRAME file, and then strengthened with map-complexity and derivation-reconcile checks before declaring the project valid.

---

## 3) Does Haxaml export prompt templates from FRAME files that follow an official best prompting structure?

Verdict: **Partial**

Evidence files:
- `haxaml/export_engine.py`
- `tests/test_export_engine.py`

Code blocks:
```python
# haxaml/export_engine.py:790-801
profile = _agent_profile(frame["rules"])
if profile:
    parts.append(_section("Working Profile", _render_agent_persona(frame["rules"])))
    parts.append(_section("Reasoning & Response Style", _render_agent_reasoning_policy(frame["rules"])))
    few_shot = _render_agent_few_shot_examples(frame["rules"], frame["acts"])
    if few_shot:
        parts.append(_section("Reference Examples", few_shot))
```

```python
# tests/test_export_engine.py:84-95
assert "## Working Profile" in content
assert "## Reasoning & Response Style" in content
assert "## Reference Examples" in content
assert content.index("## Working Profile") < content.index("## Reasoning & Response Style")
```

Brief code explanation:
- Haxaml does export structured prompt templates (persona, reasoning policy, output contract, examples) from FRAME.
- But there is no explicit external “official standard validator” (for example, a hard check against OpenAI/Anthropic official prompt schema). So it is structured and deterministic, but not formally certified against an external spec.

---

## 4) Does the export engine have a model/structure to ensure it extracts the right details from FRAME files?

Verdict: **Yes for deterministic structure; No probabilistic model**

Evidence files:
- `haxaml/export_engine.py`
- `tests/test_export_engine.py`

Code blocks:
```python
# haxaml/export_engine.py:74-82
DEFAULT_EXAMPLE_POLICY = {
    "max_examples": 4,
    "max_input_chars": 320,
    "max_output_chars": 420,
    "max_total_chars": 2800,
    "derived_from_acts_max": 4,
    "ordering": "explicit_then_derived",
    "fallback_when_empty": "render_notice",
}
```

```python
# haxaml/export_engine.py:456-517
explicit = _explicit_examples(profile)
derived = _derived_examples_from_acts(acts)[:derived_cap]
pool = explicit + derived
...
if selected and total_chars + candidate_size > max_total_chars:
    omitted_for_budget += 1
    break
...
return selected, notes
```

```python
# tests/test_export_engine.py:98-103
first = export_frame_to_markdown(str(tmp_path), "codex")
second = export_frame_to_markdown(str(tmp_path), "codex")
assert first == second
```

Brief code explanation:
- Selection/extraction is rule-based and deterministic (policy caps, precedence, truncation, stable ordering).
- There is no probability/scoring model; correctness comes from explicit structure and deterministic transforms.

---

## 5) Does Haxaml + FRAME ensure cross-agent/IDE workflows, even if model/provider changes?

Verdict: **Partial (process consistency = yes, model-output sameness = no)**

Evidence files:
- `haxaml/export_engine.py`
- `haxaml/mcp/policy_helpers.py`
- `haxaml/mcp/tools_lifecycle.py`

Code blocks:
```python
# haxaml/export_engine.py:27-71
AGENT_CONFIGS = {
  "claude": {...}, "windsurf": {...}, "copilot": {...},
  "codex": {...}, "cursor": {...}, "gemini": {...}, "generic": {...}
}
```

```python
# haxaml/mcp/policy_helpers.py
base["workflow"] = [
    "haxaml_about",
    "haxaml_guidance",
    "haxaml_session_start",
    "haxaml_session_plan",
    "haxaml_context_pack",
    "haxaml_session_verify",
    "haxaml_session_record",
]
```

```python
# haxaml/mcp/tools_lifecycle.py
if result in ("success", "partial") and blocking_conflicts > 0:
    return _gate_error_with_retry_policy(
        "haxaml_session_record", "derivation_conflicts", ...
    )
```

Brief code explanation:
- Same FRAME source can be exported to multiple agent/IDE formats.
- Governed lifecycle and gates enforce a common execution path across providers.
- Different models may still produce different content quality; Haxaml aligns workflow/process, not model internals.

---

## 6) Does Haxaml track task progress and project state?

Verdict: **Yes (Done)**

Evidence files:
- `haxaml/state_manager.py`
- `haxaml/mcp/tools_ops.py` (`haxaml_state_show`, `haxaml_state_compact`)
- `haxaml/mcp/tools_lifecycle.py` (session lifecycle tools)

Code blocks:
```python
# haxaml/state_manager.py:55-81
run_id = f"run-{uuid.uuid4().hex[:8]}"
run_entry = {"id": run_id, "task": task, "result": result, "changes": changes, ...}
state["runs"].append(run_entry)
```

```python
# haxaml/state_manager.py:149-154
"""Compact old runs into a summary.
Keeps the most recent `keep_recent` runs and summarizes the rest.
"""
```

```python
# haxaml/mcp/tools_ops.py
stats = sm.get_stats()
message = (
    f"Phase:      {stats['current_phase']}\n"
    f"Active:     {stats['active_task']}\n"
    ...
)
return _ok("haxaml_state_show", {"message": message, "stats": stats}, ...)
```

Brief code explanation:
- Haxaml records runs, decisions, active tasks, completed tasks, and supports compaction + state stats for long-running projects.

---

## 7) How robust are tests for MCP tool output quality (agent-usable quality)?

Verdict: **Partial-to-Strong**

Evidence files:
- `tests/test_mcp_server.py`
- `tests/mcp/`
- `tests/test_export_engine.py`
- `tests/test_workflow_benchmark_guardrail.py`

Code blocks:
```python
# tests/test_mcp_server.py:485-520
# Full session flow start -> plan -> verify -> record is tested
started = haxaml_session_start(...)
planned = haxaml_session_plan(...)
verify = haxaml_session_verify(...)
record = haxaml_session_record(...)
assert record["ok"] is True
```

```python
# tests/test_mcp_server.py:533-569
# Anti-bloat context-pack retry policy is tested
second = haxaml_context_pack(...)
assert second["error"]["code"] == "context_pack_refresh_reason_required"
```

```python
# tests/test_export_engine.py:98-103
# Deterministic export output is tested
assert first == second
```

```python
# tests/test_workflow_benchmark_guardrail.py:31-34
assert profiles["essential_short"]["total_data_payload_tokens"] <= 2100
assert profiles["expanded_short"]["total_data_payload_tokens"] <= 2600
assert profiles["essential_full"]["total_data_payload_tokens"] <= 3200
```

Brief code explanation:
- Coverage is good for lifecycle behavior, gate enforcement, deterministic export, and token guardrails.
- Gap: no live external-client + real-LLM quality-evaluation suite yet (so “agent-usable quality” is validated structurally, not by real multi-provider output scoring).

---

## 7.5) Does Haxaml currently achieve the “git for agents / central brain” goal, including easier provider switching?

Verdict: **Mostly yes at architecture level; still maturing in proof depth**

Evidence files:
- `haxaml/export_engine.py` (multi-agent output from one FRAME source)
- `haxaml/mcp/tools_lifecycle.py` (governed lifecycle + verification + record gates)
- `haxaml/mcp/tools_frame.py` (validate + reconcile checks)
- `haxaml/state_manager.py` (project memory/journal)

Code blocks:
```python
# haxaml/export_engine.py:765-822
# One FRAME source -> consistent generated guidance files for each agent target
return "\n\n".join(parts)
```

```python
# haxaml/mcp/tools_lifecycle.py
# Record gate requires verification and blocks unresolved derivation conflicts
if enforce_verify and result in ("success", "partial"):
    ... verification_required ...
if result in ("success", "partial") and blocking_conflicts > 0:
    ... derivation_conflicts ...
```

Brief code explanation:
- Haxaml centralizes project truth in FRAME, controls lifecycle via MCP gates, and exports to multiple agent formats.
- This substantially reduces provider-switch burden for workflow consistency.
- Remaining maturity work is mostly around broader real-world validation and cross-client long-run benchmarking depth.
