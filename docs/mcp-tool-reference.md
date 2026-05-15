# MCP Tool Reference

Compact operator reference for the supported Haxaml MCP surface in `0.7.x`.

## Stable Contracts

- Entrypoint stays `haxaml.mcp_server:main`.
- Public governed flow is `about -> guidance -> prebuild -> context_pack -> [context_fetch]* -> verify -> record -> expect_sync`.
- Governed lifecycle order is enforced.
- FRAME is canonical-only: `.haxaml/facts.yaml`, `.haxaml/rules.yaml`, `.haxaml/acts.yaml`, `.haxaml/expect.yaml`, `.haxaml/map.yaml`.

## Tool Groups

### Frame Tools

- `haxaml_init`
- `haxaml_setup`
- `haxaml_validate`
- `haxaml_health`
- `haxaml_doctor`

### Lifecycle Tools

- `haxaml_about`
- `haxaml_guidance`
- `haxaml_prebuild`
- `haxaml_context_pack`
- `haxaml_context_fetch`
- `haxaml_session_verify`
- `haxaml_session_record`
- `haxaml_expect_sync`

### Ops Tools

- `haxaml_export`
- `haxaml_upgrade`
- `haxaml_reconcile`
- `haxaml_needs`
- `haxaml_impact`
- `haxaml_state_show`
- `haxaml_state_compact`

### Benchmark Tools

- `haxaml_benchmark`

## Resource Endpoints

- `haxaml://frame/facts`
- `haxaml://frame/rules`
- `haxaml://frame/acts`
- `haxaml://frame/expect`
- `haxaml://frame/map`

## Governed Order

1. `haxaml_about`
2. `haxaml_guidance`
3. `haxaml_prebuild`
4. `haxaml_context_pack`
5. `haxaml_context_fetch` as needed
6. `haxaml_session_verify`
7. `haxaml_session_record`
8. `haxaml_expect_sync`

Use visibility and repair tools such as `haxaml_health`, `haxaml_needs`, and `haxaml_reconcile` only when the governed path surfaces warnings or blockers.

## Contract Notes

- `haxaml_setup` is the only MCP onboarding tool. It applies changes; it does not have a separate dry-run/bootstrap surface.
- `haxaml_setup(..., with_workflow=True)` installs workflow adaptation files for supported targets.
- `haxaml_init` is a minimal FRAME scaffold helper. It does not export or adopt agent-native files.
- Out-of-order governed calls fail with `lifecycle_contract_violation`.
- `haxaml_prebuild` is the only public governed session-entry tool.
- `session_id` is required for governed `context_pack`, `context_fetch`, `session_verify`, and `session_record`.
- Repeated `haxaml_context_pack` calls require `refresh_reason`.
- Repeated `haxaml_context_pack` calls now return refresh metadata describing whether the second call was a full pack, a delta, or a no-change refresh.
- Repeated `haxaml_context_fetch` calls are allowed because each call is query-driven.
- `pack` must be one of `minimal`, `balanced`, or `full`.
- `haxaml_state_compact` archives older runs, sessions, and verifications into `.haxaml/archive/acts-history.yaml`; it does not summarize them away.
- `haxaml_validate` can fail with `governance_evidence_missing`, `lifecycle_drift`, or `derivation_conflicts`.

## Design Note

`haxaml_prebuild` decides whether the task is ready and opens the governed session.

`haxaml_context_pack` stays separate because it decides how much task-scoped context the agent should load first.

`haxaml_context_fetch` exists so the agent can ask for more governed memory later without rerunning the whole first-pass context step. That keeps the default path lean while still allowing archive-backed follow-up retrieval.

Repeated `context_pack` calls use runtime snapshots keyed by `(project_dir, session_id)` so unchanged governed sections can stay out of the second payload.
