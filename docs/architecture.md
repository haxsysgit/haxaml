# Architecture

Haxaml is organized around two goals:

1. Keep FRAME governance deterministic.
2. Keep agent context lean and canonical.

## Top-Level Structure

```text
haxaml/
  mcp_server.py              # public MCP entrypoint (haxaml.mcp_server:main)
  mcp/
    __init__.py
    base.py                  # shared MCP imports and app wiring
    app_core.py              # MCP app object + core constants/caches
    response_helpers.py      # response envelopes, detail modes, compact short outputs
    policy_helpers.py        # about gate, mode gating, retry policy
    lifecycle_helpers.py     # lifecycle/session/state helper functions
    export_helpers.py        # export/bootstrap helper functions
    adoption_helpers.py      # adoption inventory helper functions
    tools_frame.py           # init/validate/health/doctor
    tools_lifecycle.py       # about/guidance/context/verify/record/sync
    tools_prebuild.py        # prebuild governed entrypoint
    tools_ops.py             # export/upgrade/bootstrap/adopt/reconcile/needs/impact/state
    tools_benchmark.py       # benchmark tool and workflow profiling helpers
    resources.py             # MCP resources (haxaml://frame/*)
  context.py                 # context assembly and token counting
  validator.py               # FRAME schema + semantic validation
  reconcile.py               # derivation conflict detection
  export_engine.py           # FRAME -> agent-native file generation
  state_manager.py           # state read/write + hot/archive acts history control
  runner.py                  # internal run lifecycle helper
  paths.py                   # canonical FRAME path resolution

docs/
  architecture.md
  contributing.md
  mcp-tool-reference.md

examples/
  minimal-governed-flow/
    .haxaml/
      facts.yaml
      rules.yaml
      acts.yaml
      expect.yaml
    README.md

tests/
  mcp/
    conftest.py
    test_frame.py
    test_lifecycle.py
    test_ops.py
    test_resources.py
    test_registration.py
    test_benchmark_tool.py
  test_*.py
```

## Canonical Rules

- Public governed path is `about -> guidance -> prebuild -> context_pack -> [context_fetch]* -> verify -> record -> expect_sync`.
- `.haxaml/*.yaml` is the only supported FRAME location.
- Canonical file names are `facts.yaml`, `rules.yaml`, `acts.yaml`, `expect.yaml`, and `map.yaml`.
- Context packs are task-scoped and preferred over whole-project context dumps.
- Older acts history lives in `.haxaml/archive/acts-history.yaml` and is loaded on demand for guided retrieval.

## MCP Layering

- `haxaml.mcp_server`
  - public import surface
  - stdio entrypoint used by `haxaml-mcp`

- `haxaml.mcp.tools_*`
  - callable MCP tools registered on `mcp_app`
  - split by domain for maintainability

- `haxaml.mcp.*_helpers`
  - shared internal logic
  - lifecycle, policy, export, and adoption support

- `haxaml.mcp.base`
  - shared imports/constants for MCP modules
  - not a public tool surface

## Testing Strategy

- MCP behavior is mirrored by module in `tests/mcp/`.
- Non-MCP units stay in `tests/test_*.py`.
- Full-suite pass remains required before release.
