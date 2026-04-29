# Architecture

This repository is organized around two goals:
1. Keep FRAME governance deterministic for agents.
2. Keep MCP server behavior backward-compatible for users.

## Top-Level Structure

```text
haxaml/
  mcp_server.py              # stable compatibility entrypoint (haxaml.mcp_server:main)
  mcp/
    __init__.py
    base.py                  # compatibility import surface for MCP internals
    app_core.py              # MCP app object + core constants/caches
    response_helpers.py      # response envelopes, detail modes, compaction
    policy_helpers.py        # mode gating, retry policy, about gate, call budgets
    lifecycle_helpers.py     # guidance/session/state helper functions
    export_helpers.py        # export/bootstrap helper functions
    adoption_helpers.py      # adoption inventory helper functions
    tools_frame.py           # init/validate/context/health/doctor
    tools_lifecycle.py       # about/guidance/start/plan/context/verify/record/run/done
    tools_ops.py             # export/upgrade/bootstrap/adopt/reconcile/needs/impact/state
    tools_benchmark.py       # benchmark tool and workflow profiling helpers
    tools.py                 # compatibility re-export of all tool modules
    resources.py             # MCP resources (haxaml://...)
  context.py                 # context assembly and token counting
  validator.py               # FRAME schema validation
  reconcile.py               # derivation conflict detection
  export_engine.py           # FRAME -> agent-native file generation
  state_manager.py           # state read/write + compaction
  runner.py                  # run lifecycle preflight/start/finish

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
  test_*.py                  # non-MCP unit tests
```

## Compatibility Rules

- Tool names are stable: no renames in this refactor.
- MCP payload contracts are stable: no response-shape changes in this refactor.
- Legacy entrypoint stays stable: `haxaml.mcp_server:main` remains valid.

## MCP Layering

- `haxaml.mcp_server`
  - public/legacy import surface
  - entrypoint used by `haxaml-mcp`

- `haxaml.mcp.tools_*`
  - callable MCP tools registered on `mcp_app`
  - split by domain for maintainability

- `haxaml.mcp.*_helpers`
  - pure helper logic extracted from old monolith
  - internal support for tool modules

- `haxaml.mcp.base`
  - compatibility barrel
  - preserves wildcard import surface used by `tools_*` and `resources`

## Testing Strategy

- MCP behavior is mirrored by module in `tests/mcp/`.
- Non-MCP units stay in `tests/test_*.py`.
- Keep full-suite pass (`pytest -q`) required before merge.
