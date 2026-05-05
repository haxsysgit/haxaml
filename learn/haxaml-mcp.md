# MCP: Haxaml Operator + Architecture Guide (0.6.x)

Haxaml is MCP-first and agent-first.

This file merges:
- the original MCP operator contract and lifecycle usage guide, and
- a plain-language mapping to official MCP architecture primitives.

Official architecture reference:
https://modelcontextprotocol.io/docs/learn/architecture

## Why This Matters

Haxaml being "new" to many models is expected.

MCP is runtime integration, not training-time dependency. The model does not need prior training on Haxaml internals if:

1. the host actually connects to the Haxaml MCP server, and
2. Haxaml hard-fails when lifecycle contract is violated.

Haxaml 0.5.2 tightened those hard gates. Haxaml 0.6 adds `haxaml_prebuild` for task classification and semantic validation before build, and makes it the recommended entrypoint for the preparation phase.

## Architecture Mapping (Official MCP -> Haxaml)

### Participants

- **Host**: Codex CLI, Claude Code, Cursor, Windsurf, etc.
- **MCP client**: host-side MCP connector that discovers/calls tools.
- **MCP server**: `haxaml-mcp` (`haxaml.mcp_server:main`).
- **Data/state**: repo + `.haxaml/*` FRAME files.

### Layers

- **Transport layer**: usually stdio for local Haxaml (`uvx haxaml-mcp`).
- **Data layer**: JSON-RPC capability discovery + tool/resource calls.

Haxaml governance logic lives in tool contracts and state transitions at the data layer.

### MCP Primitives and Haxaml Decisions

- **Tools**: primary governance surface in Haxaml.
- **Resources**: optional read surfaces (`haxaml://frame/*`, `haxaml://context`).
- **Prompts**: supported by MCP generally, but not a required Haxaml governance control surface.

Why Haxaml is tool-first (not prompt-primitive-first):
- governance needs deterministic state transitions
- governance needs structured, machine-checkable failure codes
- governance needs hard blocking when sequence is wrong

Prompt primitives are useful instruction surfaces but are advisory; they are not deterministic lifecycle gates.

Why Haxaml does not depend on elicitation as a required primitive:
- host support is uneven
- many runs are headless or autonomous
- mandatory human-interrupt loops reduce cross-client reliability

Haxaml instead encodes clarification and next actions in deterministic tool payloads (`required_questions`, `expected_next`, `retry_after`).

## Agent-First Rule

Audience: human operators and integrators configuring runtime.

Execution is agent-first:
- agents call lifecycle tools,
- agents maintain governed state through tool contracts,
- humans mainly configure MCP availability and review outcomes.

Avoid manual FRAME surgery as a default workflow. Prefer agent-governed reconcile/validate loops.

## Response Envelope

Every tool returns:

- `ok`: boolean
- `tool`: tool name
- `data`: structured payload
- `warnings`: non-fatal warnings
- `error`: `{ code, message, details }` when `ok=false`

Every tool also accepts:

- `detail`: `short` or `full`
- default is `short` (token-lean success payloads)
- failures still return rich `error.details`

For full payloads on a specific call, pass `detail="full"`.

## Core Tools (0.6.x)

- `haxaml_about` (mandatory once per active agent/MCP session)
- `haxaml_guidance`
- `haxaml_prebuild` (new in 0.6 — task classification, semantic validation, readiness check)
- `haxaml_session_start`
- `haxaml_session_plan`
- `haxaml_context_pack`
- `haxaml_session_verify`
- `haxaml_session_record`
- `haxaml_expect_sync`
- `haxaml_validate`
- `haxaml_reconcile`
- `haxaml_adopt_plan`

Strict lifecycle contract (0.6.x):
- Governed calls are hard-gated by order.
- Recommended order: `about -> guidance -> prebuild -> context_pack -> session_verify -> session_record -> expect_sync`.
- Advanced/manual order remains available: `about -> guidance -> session_start -> session_plan -> context_pack -> session_verify -> session_record -> expect_sync`.
- `haxaml_prebuild` opens the governed session internally and advances the contract to `haxaml_context_pack`.
- Out-of-order governed calls fail with `error.code="lifecycle_contract_violation"`.

Deprecated compatibility wrappers (not part of the recommended MCP workflow):

- `haxaml_run` — use `haxaml_guidance` + `haxaml_prebuild`
- `haxaml_done` — use `haxaml_session_verify` + `haxaml_session_record`
- `haxaml_context` — use `haxaml_context_pack`

## Operating Modes

- Governed mode: project work. Use Haxaml lifecycle and FRAME journal updates.
- Utility mode: side task or unrelated request. Do not run governed lifecycle.
- Resume rule: after utility work, return to governed flow with `haxaml_guidance` then `haxaml_prebuild`.

## MCP Client Config Examples (Bootstrap-Aligned)

These snippets match `haxaml_mcp_bootstrap(..., mode='snippets', editors=['generic','claude_code','cursor'])` with `uvx=True`.

| Client | Bootstrap editor key | Write target |
| --- | --- | --- |
| Generic | `generic` | `.mcp.json` |
| Claude Code | `claude_code` | `.mcp.json` |
| Cursor | `cursor` | `.cursor/mcp.json` |

Shared server block for all three:

```json
{
  "mcpServers": {
    "haxaml": {
      "type": "stdio",
      "command": "uvx",
      "args": ["haxaml-mcp"],
      "env": {
        "HAXAML_PROJECT_DIR": "/absolute/path/to/project"
      }
    }
  }
}
```

Quick generator command:

```bash
haxaml mcp-bootstrap --mode snippets --editor generic --editor claude_code --editor cursor
```

## Quick Start MCP Flow

Use this call order for governed execution:

If the task is utility/off-topic, skip this flow and keep `.haxaml/*` unchanged.

1. `haxaml_about(project_dir='.')`
2. `haxaml_guidance(task=..., project_dir='.')`
3. `haxaml_prebuild(task=..., project_dir='.')`
4. `haxaml_context_pack(task=..., project_dir='.', pack='balanced', include_state=True, session_id=...)`
5. `haxaml_session_verify(task=..., project_dir='.', session_id=..., inspected_context=[...], changed_files=[...], summary=...)`
6. `haxaml_session_record(task=..., result='success'|'partial'|'failed', project_dir='.', session_id=..., changes=..., decisions=..., risks=...)`
7. `haxaml_expect_sync(project_dir='.', run=<optional>)`
8. `haxaml_reconcile(project_dir='.')` when boundary/derivation risk appears (or before retrying blocked record/validate).

Expected signals:

- Step 1: `data.recommended_workflow`, `data.call_budgets`.
- Step 2: `data.status`, `data.call_budget`, `data.visibility_calls_optional`.
- Step 3 (prebuild): `data.readiness_status`, `data.task_type`, `data.guidance_type`, `data.frame_health`, `data.session_id`.
- Step 4 (short default): `data.tokens`, `data.context_window_usage`, `data.included_sections`, `data.omitted_sections`, `data.omitted_context`.
- Step 4 policy: one context-pack call per session/task by default; repeats require `refresh_reason`.
- Step 4 (full): `data.context_pack` is included.
- Step 5: `data.verdict` should be `pass` or `pass_with_risks` before recording `success`/`partial`.
- Step 6: `data.run_id` on success; gate failures return `error.code`.
- Step 7: sync acts->expect lifecycle status (`success->done`, `partial->active`, `failed->blocked`).
- Step 8: confirm `severity_totals.blocking == 0` before expecting record/validate success.

Lean default:
- Keep to `about -> guidance -> prebuild -> context_pack -> verify -> record -> expect_sync`.
- Visibility calls are optional diagnostics: `haxaml_health`, `haxaml_needs`, `haxaml_reconcile`, `haxaml_state_show`.
- Retry rule: if the same gate error appears twice, stop retries, fix root cause, then retry once.
- Contract rule: governed steps out of order are not warnings; they are blocking errors.

## Demo Walkthrough

### Happy Path

Request:

- "Add parser tests for empty-input handling."

Flow and expected response signals:

1. `haxaml_about(project_dir=".")`
- signal: `ok=true`; onboarding prompt and lean workflow are returned.
2. `haxaml_guidance(task="Add parser tests for empty-input handling.", project_dir=".")`
- signal: `ok=true`; use `data.required_questions` if present.
3. `haxaml_prebuild(task="Add parser tests for empty-input handling.", project_dir=".")`
- signal: `ok=true`; capture `data.session_id`, `data.readiness_status`, and `data.plan`.
4. `haxaml_context_pack(task="Add parser tests for empty-input handling.", pack="standard", include_state=True, session_id="<session_id>", project_dir=".")`
- signal: `ok=true`; short mode returns context text + `tokens` + included/omitted metadata. (`standard` resolves to `balanced`)
5. `haxaml_session_verify(task="Add parser tests for empty-input handling.", session_id="<session_id>", inspected_context=[".haxaml/facts.yaml",".haxaml/rules.yaml"], changed_files=["tests/test_parser.py"], summary="Added empty-input test coverage.", project_dir=".")`
- signal: `ok=true`; `data.verdict` is `pass` or `pass_with_risks`.
6. `haxaml_session_record(task="Add parser tests for empty-input handling.", result="success", session_id="<session_id>", changes="Added parser empty-input tests.", decisions="Reuse existing test fixtures.", risks="None.", project_dir=".")`
- signal: `ok=true`; `data.run_id` starts with `run-`.
7. `haxaml_expect_sync(project_dir=".")`
- signal: `ok=true`; lifecycle drift marker clears and runbook status is updated.

### Gate-Failure Branch (Derivation Conflict)

Scenario:

- `haxaml_session_record(..., result="success")` returns `error.code="derivation_conflicts"`.
- `haxaml_validate(project_dir=".")` also fails with `error.code="derivation_conflicts"`.

Recovery path:

1. Run `haxaml_reconcile(project_dir=".")`.
2. Have the agent apply reconcile conflict guidance (`canonical_path`, `derived_path`, `suggested_fix_action`, `gate_reasons`) through a governed task.
3. Re-run `haxaml_reconcile(project_dir=".")` until blocking conflicts are zero.
4. Re-run `haxaml_validate(project_dir=".")` and confirm `ok=true`.
5. Retry `haxaml_session_record(..., result="success"|"partial")`.

Note:

- If you intentionally stop and must record `result="failed"` while conflicts remain, include explicit conflict stop reason in `changes`/`decisions`/`risks`, or `error.code="conflict_reason_required"` is returned.

## Bad/Good Usage Pairs (Compact)

1. Verify gate
- Bad: `haxaml_guidance -> haxaml_session_start -> haxaml_session_record(result="success")`
- Result: `error.code="about_required"` first, then `error.code="verification_required"` if verify is skipped.
- Good: `haxaml_about -> haxaml_guidance -> haxaml_prebuild -> haxaml_context_pack -> haxaml_session_verify(verdict=pass|pass_with_risks) -> haxaml_session_record`

2. Reconcile gate
- Bad: `haxaml_session_verify -> haxaml_session_record(result="success")` while blocking map/rules conflicts exist
- Result: `error.code="derivation_conflicts"`
- Good: `haxaml_reconcile -> fix suggested conflicts -> haxaml_validate -> haxaml_session_record`

3. Context scope
- Bad: calling `haxaml_context_pack` with full state for every task without task focus
- Result: oversized context and weak task focus
- Good: `haxaml_context_pack(task=..., pack="minimal"|"balanced", session_id=...)` once; repeat only with `refresh_reason`

4. Prebuild skipping for complex tasks
- Bad: going straight to `haxaml_session_start` on a refactor or migration task when you want the high-level governed path
- Result: you lose the consolidated readiness report, task classification, and prebuild-owned session creation
- Good: `haxaml_prebuild(task=..., project_dir='.')` for the standard high-level flow

## Troubleshooting

1. Symptom: `error.code="missing_facts"` on guidance/start/context tools.
- Fix: run `haxaml_init(project_dir='.')`, then `haxaml_validate(project_dir='.')`.

2. Symptom: `error.code="about_required"` on `haxaml_session_start`.
- Fix: call `haxaml_about(project_dir='.')` once in the active agent/MCP session, then retry.

3. Symptom: `error.code="unknown_session"` on `haxaml_session_plan`.
- Fix: use a current `session_id` from `haxaml_session_start`; then retry plan.

4. Symptom: `error.code="verification_required"` on `haxaml_session_record(result="success"|"partial")`.
- Fix: run `haxaml_session_verify` first and ensure verdict is `pass` or `pass_with_risks`.

5. Symptom: `error.code="expect_sync_required"` on `haxaml_session_record` or `error.code="lifecycle_drift"` on `haxaml_validate`.
- Fix: call `haxaml_expect_sync(project_dir='.')`, then retry.

6. Symptom: `error.code="derivation_conflicts"` on `haxaml_validate` or `haxaml_session_record`.
- Fix: run `haxaml_reconcile`, apply suggested fixes, and retry when blocking conflicts are zero.

7. Symptom: `error.code="lifecycle_contract_violation"` on governed tools.
- Fix: run the tool(s) listed in `error.details.expected_next`, then retry the blocked call.

8. Symptom: `error.code="governance_evidence_missing"` on `haxaml_validate`.
- Meaning: code/config changed but no governed lifecycle evidence exists in `acts.yaml`.
- Fix: execute the governed flow and record+sync before validating again.

9. Symptom: `error.code="utility_mode_task"` on lifecycle tools.
- Fix: treat the request as utility mode (no governed lifecycle calls). Resume governed flow only when back to project work.

10. Symptom: `error.code="retry_policy_blocked"`.
- Fix: stop looped retries, resolve root cause, then retry once.

11. Symptom: `error.code="context_pack_refresh_reason_required"` on repeated `haxaml_context_pack`.
- Fix: pass `refresh_reason` only when scope changed or context became stale.

## Detail Mode Quick Examples

- Default short:
  - `haxaml_context_pack(task="implement auth module", pack="balanced", include_state=True, session_id="<session_id>")`
- Token/window tracking:
  - `data.tokens` gives pack token count.
  - `data.context_window_usage` gives percentage usage for `4k`, `8k`, `32k`, and `128k` windows.
- Full for one call:
  - `haxaml_context_pack(task="implement auth module", pack="balanced", include_state=True, session_id="<session_id>", detail="full")`
- Invalid value:
  - returns `error.code="invalid_detail"`

## Workflow Benchmark Mode

- Use `haxaml_benchmark(project_dir='.', mode='workflow')` for workflow-level profiling.
- It returns profile totals for:
  - `essential_short` (lean default)
  - `expanded_short` (lean + visibility calls)
  - `essential_full` (full detail payloads)
- It also returns:
  - `transport_overhead` (serialized envelope token estimates)
  - `guardrails` (ceiling checks for CI drift detection)

## Adoption Flow (Non-Destructive First)

Recommended sequence:

1. `haxaml_adopt_plan(project_dir='.')`
2. `haxaml_reconcile(project_dir='.')`
3. have the agent apply required FRAME adjustments
4. `haxaml_validate(project_dir='.')`
5. optional `haxaml_adopt(write=True)` and export

`haxaml_adopt_plan` never writes files.
`haxaml_adopt` preserves existing files unless forced.
