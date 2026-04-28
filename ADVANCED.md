# ADVANCED: Haxaml

This file is the full reference.
README is the fast path.

## Positioning

Haxaml is a deterministic agent-management framework that implements FRAME.

- FRAME is the governance model.
- Haxaml is the engine that validates, tracks, and exports it.
- AI agents provide project intelligence.
- Haxaml does not generate project truth by itself.

## MCP-first architecture

Use MCP whenever possible.
CLI mirrors the same operations locally.

Core MCP tools:

- `haxaml_init`
- `haxaml_validate`
- `haxaml_context`
- `haxaml_health`
- `haxaml_doctor`
- `haxaml_run`
- `haxaml_done`
- `haxaml_export`
- `haxaml_mcp_bootstrap`
- `haxaml_upgrade`
- `haxaml_adopt`
- `haxaml_needs`
- `haxaml_impact`
- `haxaml_state_show`
- `haxaml_state_compact`
- `haxaml_benchmark`

MCP tool responses are structured JSON envelopes:

- `ok`
- `tool`
- `data`
- `warnings`
- `error`

## FRAME files

Default location is `.haxaml/`.

- `facts.yaml`
- `rules.yaml`
- `acts.yaml`
- `expect.yaml`
- `map.yaml` (optional, policy-driven)

Compatibility fallback names still exist for older projects:

- `brain.yaml` -> `facts.yaml`
- `mind.yaml` -> `rules.yaml`
- `state.yaml` -> `acts.yaml`

## Export model

FRAME is source of truth.
Exports are compiled views.

Default export:

- `haxaml export` -> `HAXAML.md`

Explicit exports:

- `--agent claude` -> `CLAUDE.md`
- `--agent codex` -> `haxaml-agents.md`
- `--agent copilot` -> `.github/copilot-instructions.md`
- `--agent cursor` -> `.cursor/rules/haxaml.mdc`
- `--agent windsurf` -> `.windsurf/rules/haxaml.md`
- `--agent gemini` -> `GEMINI.md`

For Codex-native override:

- `haxaml export --agent codex --override-native` writes `AGENTS.md`.

Guardrail:

- existing non-Haxaml files are protected unless explicitly overridden.

Preview mode:

- `--dry-run` generates without writing.
- `--diff-preview` includes unified diff.

## Versioning

Single runtime source of truth is package metadata (`pyproject.toml`).
CLI and runtime version reporting resolve from installed metadata with local fallback.

Upgrade command:

```bash
haxaml upgrade
haxaml upgrade --to 0.2.0
haxaml upgrade --no-include-mcp
```

Under the hood, upgrade uses `uv tool upgrade` and falls back to `uv tool install --upgrade` when needed.

## Benchmark stance

Haxaml includes token and state-growth utilities today.

It does **not** claim a universal "YAML always smaller than markdown" result.
Markdown can be smaller in some fixtures.

FRAME value is deterministic governance and repeatable agent handoff, not guaranteed raw compression.

## Project snapshot

Current release line includes:

- FRAME schemas + validation
- MCP server
- CLI parity for core flows
- deterministic exports
- run/done diary tracking
- adoption from existing agent files
- auto re-export support
- token benchmark utilities

In active evolution:

- deterministic FRAME-vs-prompt benchmark suite
- stronger MCP bootstrap UX in editors
- more real-world migration playbooks

## Release flow

```bash
uv sync --all-extras
uv run pytest -q
uv build
uv run twine check dist/*
uv publish --token "$PYPI_TOKEN"
```

Launcher package release:

```bash
uv build --project packages/haxaml-mcp --out-dir packages/haxaml-mcp/dist
uv run twine check packages/haxaml-mcp/dist/*
uv publish --token "$PYPI_TOKEN" packages/haxaml-mcp/dist/*
```

## Version roadmap (saved context)

### Core rule

- Keep one version authority: package metadata in `pyproject.toml`.
- Runtime and CLI read version dynamically from installed metadata.
- No manual version strings in core code paths.

### Planned release lines

1. `0.3.x` — Reliability and migration UX
- stronger `haxaml adopt` guidance and conflict detection
- richer `haxaml_mcp_bootstrap` outputs for editor onboarding
- improved export readability templates tuned for real agent workflows

2. `0.4.x` — Deterministic benchmark suite
- FRAME-vs-long-prompt benchmark command
- fixture-based repeatable benchmark scenarios
- documented claim boundaries and reproducible reports

3. `0.5.x` — Multi-repo + map maturity
- deeper map policy checks across larger module graphs
- impact analysis quality upgrades for cross-module work
- better runbook-to-map validation links

4. `1.0.0` — Stable public contract
- locked MCP tool envelope contract
- locked export safety defaults and override semantics
- migration guide from pre-1.0 behavior

### Upgrade policy

- keep `haxaml upgrade` as the default update path
- support latest or pinned updates (`--to X.Y.Z`)
- keep launcher package (`haxaml-mcp`) upgradeable in the same flow
