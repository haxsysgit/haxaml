# MCP: Haxaml Agent Contract (0.4.0)

Haxaml is MCP first.
Use MCP tools for lifecycle, adoption, and reconciliation gates.
CLI mirrors these MCP tools as thin wrappers.

## Response Envelope

Every tool returns:

- `ok`: boolean
- `tool`: tool name
- `data`: structured payload
- `warnings`: non-fatal warnings
- `error`: `{ code, message, details }` when `ok=false`

## Core 0.4.0 Tools

- `haxaml_guidance`
- `haxaml_session_start`
- `haxaml_session_plan`
- `haxaml_context_pack`
- `haxaml_session_verify`
- `haxaml_session_record`
- `haxaml_validate`
- `haxaml_reconcile` (new)
- `haxaml_adopt_plan` (new)

Compatibility wrappers (deprecated, still available in 0.4.0):

- `haxaml_run` -> `haxaml_session_start`
- `haxaml_done` -> `haxaml_session_verify` + `haxaml_session_record`
- `haxaml_context` -> `haxaml_context_pack`

Wrapper payloads now include explicit deprecation metadata and removal target.

## Derivation Boundary Model

Canonical rule:

- when `.haxaml/map.yaml` exists, `map.modules`, `map.dependencies`, and `map.impact` are canonical.

No-map rule:

- if `map.yaml` is absent and map policy marks map optional, map-canonical checks are deferred.

Conflict model:

- conflicts are structured objects with `canonical_path`, `derived_path`, `severity`, and `suggested_fix_action`.
- unresolved `blocking` conflicts are gate blockers.

Reconcile payload includes:

- `conflict_counts`
- `warning_counts`
- `severity_totals`
- `gate_reasons`
- `human_summary`

## Gate Behavior

`haxaml_validate`:

- schema + map policy + reconcile checks.
- fails with `error.code=derivation_conflicts` when blocking reconcile conflicts exist.

`haxaml_session_record`:

- `success` and `partial` require verification pass/pass_with_risks.
- `success` and `partial` are blocked if blocking derivation conflicts exist.
- `failed` is allowed with conflicts only when conflict stop reason is explicitly recorded.

## Adoption Flow (Non-Destructive First)

Recommended sequence:

1. `haxaml_adopt_plan(project_dir='.')`
2. `haxaml_reconcile(project_dir='.')`
3. edit FRAME files
4. `haxaml_validate(project_dir='.')`
5. optional `haxaml_adopt(write=True)` and export

`haxaml_adopt_plan` never writes files.
`haxaml_adopt` preserves existing files unless forced.

## Example Responses

`haxaml_reconcile` success:

```json
{
  "ok": true,
  "tool": "haxaml_reconcile",
  "data": {
    "human_summary": "No derivation conflicts detected. Map-canonical boundaries are consistent.",
    "severity_totals": {"blocking": 0, "warning": 0},
    "conflict_counts": {"total": 0, "blocking": 0},
    "warning_counts": {"total": 0},
    "gate_reasons": []
  }
}
```

`haxaml_reconcile` conflict:

```json
{
  "ok": false,
  "tool": "haxaml_reconcile",
  "error": {
    "code": "derivation_conflicts",
    "message": "Found 2 blocking and 1 warning derivation conflict(s).",
    "details": {
      "severity_totals": {"blocking": 2, "warning": 1},
      "gate_reasons": ["Map module 'api' is missing in rules.boundaries.modules."]
    }
  }
}
```
