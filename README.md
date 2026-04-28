# Haxaml

[![PyPI version](https://img.shields.io/pypi/v/haxaml.svg)](https://pypi.org/project/haxaml/)

Haxaml is a deterministic project-governance framework for AI coding workflows.

MCP first.
CLI second.

It gives agents one shared source of truth called **FRAME** so context does not drift across tools.

## What it does

- keeps project truth in structured FRAME files
- validates that structure before work starts
- tracks runs, decisions, risks, and completed work
- exports clean agent-ready prompt files from FRAME
- exposes MCP tools so IDE agents can call governance directly

## FRAME at a glance

| File | Purpose |
| --- | --- |
| `.haxaml/facts.yaml` | project truth |
| `.haxaml/rules.yaml` | how agents should work |
| `.haxaml/acts.yaml` | task diary and decisions |
| `.haxaml/expect.yaml` | expected next runs |
| `.haxaml/map.yaml` | optional module ownership + impact map |

## Install

```bash
pip install haxaml
```

or with uv tools:

```bash
uv tool install haxaml
uv tool install haxaml-mcp
```

## Quick start

```bash
haxaml init
haxaml validate
haxaml context --tokens
haxaml export
```

Default export writes `HAXAML.md`.

Optional agent-specific exports:

```bash
haxaml export --agent claude
haxaml export --agent codex
haxaml export --agent copilot
haxaml export --agent cursor
haxaml export --agent windsurf
haxaml export --agent gemini
```

Safe preview before writing:

```bash
haxaml export --dry-run --diff-preview --target CLAUDE.md
```

## MCP setup (recommended)

Use `uvx` in your MCP client config:

```json
{
  "mcpServers": {
    "haxaml": {
      "command": "uvx",
      "args": ["haxaml-mcp"],
      "env": {
        "HAXAML_PROJECT_DIR": "/path/to/project"
      }
    }
  }
}
```

You can also generate project-local bootstrap config with:

```bash
haxaml mcp-bootstrap --mode write --editor generic
```

## Upgrade

```bash
haxaml upgrade
```

Pin a specific version:

```bash
haxaml upgrade --to 0.2.0
```

## Why FRAME even when markdown can be smaller?

In some fixtures, raw markdown is smaller than YAML.
That is normal.

Haxaml is not only about raw token count.
The value is deterministic governance:

- validation gates
- compact compiled exports
- explicit decisions and risks
- stable multi-agent handoff

## Docs

- [ADVANCED.md](ADVANCED.md) for full command reference, MCP tool contract, export behavior, and roadmap notes.
