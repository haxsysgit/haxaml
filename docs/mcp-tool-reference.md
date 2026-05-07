# MCP Tool Reference

Compact operator reference for the supported Haxaml MCP surface in `0.6.5`.

## Stable Contracts

- Entrypoint stays `haxaml.mcp_server:main`.
- Public governed flow is `about -> guidance -> prebuild -> context_pack -> verify -> record -> expect_sync`.
- Governed lifecycle order is enforced.
- FRAME is canonical-only: `.haxaml/facts.yaml`, `.haxaml/rules.yaml`, `.haxaml/acts.yaml`, `.haxaml/expect.yaml`, `.haxaml/map.yaml`.

## Tool Groups

### Frame Tools

- `haxaml_init`
- `haxaml_validate`
- `haxaml_health`
- `haxaml_doctor`

### Lifecycle Tools

- `haxaml_about`
- `haxaml_guidance`
- `haxaml_prebuild`
- `haxaml_context_pack`
- `haxaml_session_verify`
- `haxaml_session_record`
- `haxaml_expect_sync`

### Ops Tools

- `haxaml_export`
- `haxaml_upgrade`
- `haxaml_mcp_bootstrap`
- `haxaml_adopt_plan`
- `haxaml_adopt`
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
5. `haxaml_session_verify`
6. `haxaml_session_record`
7. `haxaml_expect_sync`

Use visibility and repair tools such as `haxaml_health`, `haxaml_needs`, and `haxaml_reconcile` only when the governed path surfaces warnings or blockers.

## Contract Notes

- Out-of-order governed calls fail with `lifecycle_contract_violation`.
- `haxaml_prebuild` is the only public governed session-entry tool.
- `session_id` is required for governed `context_pack`, `session_verify`, and `session_record`.
- Repeated `haxaml_context_pack` calls require `refresh_reason`.
- `pack` must be one of `minimal`, `balanced`, or `full`.
- `haxaml_validate` can fail with `governance_evidence_missing`, `lifecycle_drift`, or `derivation_conflicts`.

## Design Note

`haxaml_prebuild` decides whether the task is ready and opens the governed session.

`haxaml_context_pack` stays separate because it decides how much task-scoped context the agent should load. Keeping those steps separate preserves the anti-bloat boundary.
