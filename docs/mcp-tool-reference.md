# MCP Tool Reference

Compact operator reference for the public Haxaml MCP surface in `0.6.x`.

## Stable Contracts

- Entry path remains `haxaml.mcp_server:main`.
- Tool names and response envelopes are stable in `0.6.x`.
- The recommended governed flow is `about -> guidance -> prebuild -> context_pack -> verify -> record -> expect_sync`.
- Lower-level `session_start` and `session_plan` remain available for advanced/manual flows.

## Tool Groups

### Frame Tools (`tools_frame.py`)

- `haxaml_init`
- `haxaml_validate`
- `haxaml_health`
- `haxaml_doctor`

### Lifecycle Tools (`tools_lifecycle.py`, `tools_prebuild.py`)

- `haxaml_about`
- `haxaml_guidance`
- `haxaml_prebuild`
- `haxaml_session_start`
- `haxaml_session_plan`
- `haxaml_context_pack`
- `haxaml_session_verify`
- `haxaml_session_record`
- `haxaml_expect_sync`

### Compatibility Wrappers (not part of the recommended MCP flow)

- `haxaml_context` (compatibility wrapper, deprecated)
- `haxaml_run` (compatibility wrapper, deprecated)
- `haxaml_done` (compatibility wrapper, deprecated)

### Ops Tools (`tools_ops.py`)

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

### Benchmark Tools (`tools_benchmark.py`)

- `haxaml_benchmark`

## Resource Endpoints (`resources.py`)

- `haxaml://frame/facts`
- `haxaml://frame/rules`
- `haxaml://frame/acts`
- `haxaml://frame/expect`
- `haxaml://frame/map`
- `haxaml://context`

## Recommended Governed Order

1. `haxaml_about`
2. `haxaml_guidance`
3. `haxaml_prebuild`
4. `haxaml_context_pack`
5. `haxaml_session_verify`
6. `haxaml_session_record`
7. `haxaml_expect_sync`

Use `haxaml_reconcile` when conflicts or derivation warnings appear.

## Advanced Manual Order

Use this only when you intentionally need low-level control over session creation and planning.

1. `haxaml_about`
2. `haxaml_guidance`
3. `haxaml_session_start`
4. `haxaml_session_plan`
5. `haxaml_context_pack`
6. `haxaml_session_verify`
7. `haxaml_session_record`
8. `haxaml_expect_sync`

## Contract Notes

- Governed lifecycle order is hard-enforced.
- Out-of-order governed calls fail with `lifecycle_contract_violation`.
- `haxaml_prebuild` is the recommended consolidation point for task classification, semantic validation, readiness checks, and governed session creation.
- `haxaml_session_start` and `haxaml_session_plan` remain available for advanced/manual flows when you intentionally need lower-level control over session creation and planning.
- `session_id` is required for governed `context_pack`, `session_verify`, and `session_record`.
- `haxaml_validate` can fail with `governance_evidence_missing` when code changes exist without governed evidence in `acts.yaml`.
- Repeated `haxaml_context_pack` calls require `refresh_reason`.

## Design Note: Why `context_pack` Stays Separate

`haxaml_prebuild` already replaces the recommended use of `session_start` plus `session_plan`.

`haxaml_context_pack` stays separate because it does a different job:

- `prebuild` decides whether the task is ready and opens the governed session.
- `context_pack` decides how much state and scope the agent should actually load.

Keeping them separate preserves the anti-context-bloat boundary. If they were merged by default, every prebuild call would be tempted to load context too early or too broadly.
