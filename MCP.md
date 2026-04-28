# MCP: Haxaml Operator Guide (0.4.x)

Haxaml is MCP-first.
Use MCP tools for lifecycle, adoption, and reconciliation gates.
CLI commands mirror MCP tools as thin wrappers.
Audience: human operators and integrators. Agents should primarily rely on tool contracts and a short startup prompt, not by loading this full doc into routine context.

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

## Core Tools (0.4.x)

- `haxaml_guidance`
- `haxaml_session_start`
- `haxaml_session_plan`
- `haxaml_context_pack`
- `haxaml_session_verify`
- `haxaml_session_record`
- `haxaml_validate`
- `haxaml_reconcile`
- `haxaml_adopt_plan`

Compatibility wrappers (deprecated in 0.4.x):

- `haxaml_run` -> `haxaml_session_start`
- `haxaml_done` -> `haxaml_session_verify` + `haxaml_session_record`
- `haxaml_context` -> `haxaml_context_pack`

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

1. `haxaml_guidance(task=..., project_dir='.')`
2. `haxaml_session_start(task=..., description=..., project_dir='.')`
3. `haxaml_session_plan(session_id=..., project_dir='.')`
4. `haxaml_context_pack(task=..., project_dir='.', pack='balanced', include_state=True)`
5. `haxaml_session_verify(task=..., project_dir='.', session_id=..., inspected_context=[...], changed_files=[...], summary=...)`
6. `haxaml_session_record(task=..., result='success'|'partial'|'failed', project_dir='.', session_id=..., changes=..., decisions=..., risks=...)`
7. `haxaml_reconcile(project_dir='.')` when boundary/derivation risk appears (or before retrying blocked record/validate).

Expected signals:

- Step 1: `data.status`, `data.required_questions`, `data.recommended_packs`.
- Step 2: `data.session_id`, `data.required_reads`.
- Step 3: `data.plan`, `data.verification_expectations`.
- Step 4 (short default): `data.tokens`, `data.context_window_usage`, `data.included_sections`, `data.omitted_sections`, `data.omitted_context`.
- Step 4 (full): `data.context_pack` is included.
- Step 5: `data.verdict` should be `pass` or `pass_with_risks` before recording `success`/`partial`.
- Step 6: `data.run_id` on success; gate failures return `error.code`.
- Step 7: confirm `severity_totals.blocking == 0` before expecting record/validate success.

## Demo Walkthrough

### Happy Path

Request:

- "Add parser tests for empty-input handling."

Flow and expected response signals:

1. `haxaml_guidance(task="Add parser tests for empty-input handling.", project_dir=".")`
- signal: `ok=true`; use `data.required_questions` if present.
2. `haxaml_session_start(task="Add parser tests for empty-input handling.", description="Add tests only.", project_dir=".")`
- signal: `ok=true`; capture `data.session_id`.
3. `haxaml_session_plan(session_id="<session_id>", project_dir=".")`
- signal: `ok=true`; non-empty `data.plan`.
4. `haxaml_context_pack(task="Add parser tests for empty-input handling.", pack="standard", include_state=True, project_dir=".")`
- signal: `ok=true`; short mode returns context text + `tokens` + included/omitted metadata. (`standard` resolves to `balanced`)
5. `haxaml_session_verify(task="Add parser tests for empty-input handling.", session_id="<session_id>", inspected_context=[".haxaml/facts.yaml",".haxaml/rules.yaml"], changed_files=["tests/test_parser.py"], summary="Added empty-input test coverage.", project_dir=".")`
- signal: `ok=true`; `data.verdict` is `pass` or `pass_with_risks`.
6. `haxaml_session_record(task="Add parser tests for empty-input handling.", result="success", session_id="<session_id>", changes="Added parser empty-input tests.", decisions="Reuse existing test fixtures.", risks="None.", project_dir=".")`
- signal: `ok=true`; `data.run_id` starts with `run-`.

### Gate-Failure Branch (Derivation Conflict)

Scenario:

- `haxaml_session_record(..., result="success")` returns `error.code="derivation_conflicts"`.
- `haxaml_validate(project_dir=".")` also fails with `error.code="derivation_conflicts"`.

Recovery path:

1. Run `haxaml_reconcile(project_dir=".")`.
2. Use reconcile conflict metadata (`canonical_path`, `derived_path`, `suggested_fix_action`, `gate_reasons`) to update FRAME files.
3. Re-run `haxaml_reconcile(project_dir=".")` until blocking conflicts are zero.
4. Re-run `haxaml_validate(project_dir=".")` and confirm `ok=true`.
5. Retry `haxaml_session_record(..., result="success"|"partial")`.

Note:

- If you intentionally stop and must record `result="failed"` while conflicts remain, include explicit conflict stop reason in `changes`/`decisions`/`risks`, or `error.code="conflict_reason_required"` is returned.

## Bad/Good Usage Pairs (Compact)

1. Verify gate
- Bad: `haxaml_guidance -> haxaml_session_start -> haxaml_session_record(result="success")`
- Result: `error.code="verification_required"`
- Good: `haxaml_guidance -> haxaml_session_start -> haxaml_session_plan -> haxaml_context_pack -> haxaml_session_verify(verdict=pass|pass_with_risks) -> haxaml_session_record`

2. Reconcile gate
- Bad: `haxaml_session_verify -> haxaml_session_record(result="success")` while blocking map/rules conflicts exist
- Result: `error.code="derivation_conflicts"`
- Good: `haxaml_reconcile -> fix suggested conflicts -> haxaml_validate -> haxaml_session_record`

3. Context scope
- Bad: `haxaml_context(include_state=True)` for every task
- Result: oversized context and weak task focus
- Good: `haxaml_context_pack(task=..., pack="minimal"|"balanced")` per task, then verify/record

## Top 5 Troubleshooting

1. Symptom: `error.code="missing_facts"` on guidance/start/context tools.
- Fix: run `haxaml_init(project_dir='.')` or create `.haxaml/facts.yaml`, then `haxaml_validate(project_dir='.')`.

2. Symptom: `error.code="unknown_session"` on `haxaml_session_plan`.
- Fix: use a current `session_id` from `haxaml_session_start`; then retry plan.

3. Symptom: `error.code="verification_required"` on `haxaml_session_record(result="success"|"partial")`.
- Fix: run `haxaml_session_verify` first and ensure verdict is `pass` or `pass_with_risks`.

4. Symptom: `error.code="derivation_conflicts"` on `haxaml_validate` or `haxaml_session_record`.
- Fix: run `haxaml_reconcile`, apply suggested fixes, and retry when blocking conflicts are zero.

5. Symptom: `error.code="conflict_reason_required"` on `haxaml_session_record(result="failed")`.
- Fix: explicitly document unresolved conflict as stop reason in `changes`, `decisions`, or `risks`, or resolve conflicts before recording.

## Detail Mode Quick Examples

- Default short:
  - `haxaml_context_pack(task="implement auth module", pack="balanced", include_state=True)`
- Token/window tracking:
  - `data.tokens` gives pack token count.
  - `data.context_window_usage` gives percentage usage for `4k`, `8k`, `32k`, and `128k` windows.
- Full for one call:
  - `haxaml_context_pack(task="implement auth module", pack="balanced", include_state=True, detail="full")`
- Invalid value:
  - returns `error.code="invalid_detail"`

## Adoption Flow (Non-Destructive First)

Recommended sequence:

1. `haxaml_adopt_plan(project_dir='.')`
2. `haxaml_reconcile(project_dir='.')`
3. edit FRAME files
4. `haxaml_validate(project_dir='.')`
5. optional `haxaml_adopt(write=True)` and export

`haxaml_adopt_plan` never writes files.
`haxaml_adopt` preserves existing files unless forced.
