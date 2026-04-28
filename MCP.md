# MCP: Haxaml Agent Contract

Haxaml is MCP first.
Use MCP tools as the primary interface for agent sessions.
CLI commands are wrappers.

## Response envelope

Every MCP tool returns:

- `ok`: boolean
- `tool`: tool name
- `data`: structured payload
- `warnings`: non-fatal warnings
- `error`: `{ code, message, details }` when `ok=false`

## Session lifecycle (recommended)

1. `haxaml_guidance`
2. `haxaml_session_start`
3. `haxaml_session_plan`
4. `haxaml_context_pack`
5. implementation work
6. `haxaml_session_verify`
7. `haxaml_session_record`
8. `haxaml_export` (if needed)

Compatibility wrappers:

- `haxaml_run` -> `haxaml_session_start`
- `haxaml_done` -> `haxaml_session_verify` + `haxaml_session_record`
- `haxaml_context` -> context-pack composition

## Tool contracts

### `haxaml_guidance(task, project_dir='.')`

Returns:

- `status`: `proceed` or `action_required`
- `task_type`: `outcome | design | implementation | debug | strategy`
- `risk_level`: `low | medium | high`
- `missing_context`, `assumptions`
- `required_questions`, `suggested_questions`
- `safer_path`, `recommended_packs`

### `haxaml_session_start(task, description='', project_dir='.')`

Returns:

- `session_id`
- `status`, `risk_level`, `task_type`
- `required_questions`
- `required_reads`
- onboarding read policy snapshot

### `haxaml_session_plan(session_id, project_dir='.')`

Returns:

- short deterministic plan
- risk checks
- verification expectations

### `haxaml_context_pack(task, project_dir='.', pack='balanced', include_state=True)`

Returns compact sections:

- `essential_facts`
- `relevant_rules`
- `recent_decisions`
- `affected_modules`
- `expectations`
- `unresolved`
- `task_risks`
- `_meta` with token counts and compaction notes

### `haxaml_session_verify(...)`

Reflective verification report for:

- task understanding
- context inspection
- changed-file appropriateness
- risky/unrelated touches
- rule compliance
- journal update path
- unresolved assumptions/questions
- change explanation quality

Returns:

- `verification_id`
- `verdict`: `pass | pass_with_risks | fail | needs_clarification`
- `checks[]` (name/passed/details)
- `evidence_refs`
- `follow_ups`

### `haxaml_session_record(task, result, ...)`

Verification gate:

- `success` and `partial` require latest verify verdict `pass` or `pass_with_risks`.

Returns:

- `run_id`
- `verification_id`
- `verification_verdict`
- `token_count`
- auto-export details

## Clarification enforcement default

Risk-gated soft block:

- high-risk or blocked-context tasks return `action_required`
- safe obvious tasks return `proceed`

## Context-efficiency default

- first onboarding sessions can require full FRAME reads
- later sessions should use context packs by default
- compaction metadata is tracked in `acts.context_compaction`
