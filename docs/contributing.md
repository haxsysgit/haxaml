# Contributing (Detailed Notes)

Use [CONTRIBUTING.md](../CONTRIBUTING.md) as the main contributor guide.

This page adds module-level routing for contributors who are already implementing changes.

## Module Routing

- FRAME/core tools: `haxaml/mcp/tools_frame.py`
- Lifecycle tools: `haxaml/mcp/tools_lifecycle.py`
- Ops tools: `haxaml/mcp/tools_ops.py`
- Benchmark tool: `haxaml/mcp/tools_benchmark.py`
- Resource endpoints: `haxaml/mcp/resources.py`
- Shared MCP helpers: `haxaml/mcp/*_helpers.py`
- Compatibility surfaces: `haxaml/mcp/base.py`, `haxaml/mcp_server.py`

## Test Routing

- MCP tests: `tests/mcp/`
- Non-MCP unit tests: `tests/test_*.py`

## Required Policy

- Keep MCP tool names stable.
- Keep MCP payload contract stable.
- Keep `haxaml.mcp_server:main` working.

Any planned break must be explicitly versioned and documented before implementation.
