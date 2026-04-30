# MCP Tool Reference

This file is a compact operator reference for Haxaml MCP tools.

## Stable Contracts

- Tool names are stable in 0.5.x.
- Payload shape is stable in 0.5.x.
- Entry path remains `haxaml.mcp_server:main`.

## Tool Groups

### Frame Tools (`tools_frame.py`)

- `haxaml_init`
- `haxaml_validate`
- `haxaml_context`
- `haxaml_health`
- `haxaml_doctor`

### Lifecycle Tools (`tools_lifecycle.py`)

- `haxaml_about`
- `haxaml_guidance`
- `haxaml_session_start`
- `haxaml_session_plan`
- `haxaml_context_pack`
- `haxaml_session_verify`
- `haxaml_session_record`
- `haxaml_expect_sync`
- `haxaml_run` (wrapper)
- `haxaml_done` (wrapper)

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
3. `haxaml_session_start`
4. `haxaml_session_plan`
5. `haxaml_context_pack`
6. `haxaml_session_verify`
7. `haxaml_session_record`
8. `haxaml_expect_sync`

Use `haxaml_reconcile` when conflicts or derivation warnings appear.
