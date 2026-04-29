# Contributing to Haxaml

Thanks for helping improve Haxaml. This guide is for open-source contributors who want to submit useful, reviewable changes quickly.

## What We Value

- Deterministic behavior over clever behavior.
- Backward compatibility for public MCP surfaces.
- Small, focused pull requests with clear intent.
- Tests and docs shipped with behavior changes.

## Ways to Contribute

- Report bugs with reproduction steps.
- Propose improvements through issues.
- Improve documentation and examples.
- Add or refine tests.
- Fix bugs or implement approved features.

## Before You Start

1. Check existing issues and PRs to avoid duplicate work.
2. Open an issue for non-trivial changes before coding.
3. Confirm scope and expected behavior in that issue.

## Local Setup

Option A (`pip` + venv):

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

Option B (`uv`):

```bash
uv venv
source .venv/bin/activate
uv pip install -e .[dev]
```

## Project Map

- MCP entrypoint compatibility: `haxaml/mcp_server.py`
- MCP tools by domain:
- `haxaml/mcp/tools_frame.py`
- `haxaml/mcp/tools_lifecycle.py`
- `haxaml/mcp/tools_ops.py`
- `haxaml/mcp/tools_benchmark.py`
- MCP resources: `haxaml/mcp/resources.py`
- MCP shared internals: `haxaml/mcp/*_helpers.py`, `haxaml/mcp/base.py`
- Core engine modules: `haxaml/context.py`, `haxaml/validator.py`, `haxaml/reconcile.py`, `haxaml/export_engine.py`
- Tests: `tests/` and `tests/mcp/`

Architecture reference: `docs/architecture.md`
Tool reference: `docs/mcp-tool-reference.md`

## MCP Compatibility Contract

These are strict for normal PRs:

- Do not rename MCP tools.
- Do not change MCP payload contracts.
- Keep compatibility entrypoint working: `haxaml.mcp_server:main`.

If a breaking change is necessary:

1. Open an issue describing the break.
2. Document migration impact.
3. Target a planned breaking release (not a patch release).

## Development Workflow

1. Fork and create a branch.
2. Write or update tests first when possible.
3. Implement the smallest viable change.
4. Run tests locally.
5. Update docs for any user-visible behavior change.
6. Submit PR with context and evidence.

## Run Tests

Full suite:

```bash
.venv/bin/pytest -q
```

MCP-focused suite:

```bash
.venv/bin/pytest -q tests/mcp
```

Targeted examples:

```bash
.venv/bin/pytest -q tests/mcp/test_lifecycle.py
.venv/bin/pytest -q tests/test_export_engine.py
```

## Pull Request Checklist

- [ ] Problem and solution are clearly described.
- [ ] Scope is focused and avoids unrelated changes.
- [ ] Tests were added/updated and pass locally.
- [ ] Docs were updated for behavior/tool changes.
- [ ] MCP compatibility contract is preserved, or break is explicitly approved.
- [ ] Changelog impact is noted when relevant.

## Review Expectations

Maintainers may request:

- Reproduction details for bug fixes.
- Additional edge-case tests.
- Clearer naming or smaller patch scope.
- Documentation updates before merge.

## Documentation Changes

When you change behavior, update the matching docs:

- `MCP.md` for operator flow and usage patterns.
- `docs/mcp-tool-reference.md` for tool inventory changes.
- `docs/architecture.md` if module boundaries moved.
- `README.md` for user-facing setup/entry changes.

## Need Help?

Open an issue with:

- what you tried
- expected behavior
- actual behavior
- relevant logs or output

That gives maintainers enough context to help quickly.
