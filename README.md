# Haxaml

Haxaml is a deterministic project-governance layer for AI coding agents.

It gives tools like Claude Code, Codex, Cursor, Copilot, Windsurf, and Gemini a shared project brain called **FRAME**: facts, rules, work history, architecture map, and expected next steps.

The short version: Haxaml helps agents stop rediscovering your project from scratch every session.

## Why This Exists

AI coding agents are useful, but projects can get messy fast:

- one agent follows `AGENTS.md`, another follows `CLAUDE.md`
- old decisions live in random markdown files
- every session rereads the same repo context
- bug fixes accidentally break unrelated features
- switching tools slowly turns one project into five slightly different memories

Haxaml does not replace your agent. It gives your agents a stable operating layer.

You still decide what gets built. The LLM still reasons and writes code. Haxaml stores, validates, compacts, and exports the project state so every agent starts from the same truth.

## What Haxaml Is

Haxaml is:

- a CLI for creating and validating FRAME project files
- an MCP server that agents can call directly
- a deterministic exporter for agent-native instruction files
- a project diary for runs, decisions, risks, and completed work
- a lightweight context builder for reducing repeated prompt setup

Haxaml is not:

- an LLM
- a code generator
- a prompt marketplace
- a magic benchmark claim machine
- another agent pretending to be the boss

## FRAME

FRAME is the project model Haxaml implements.

| Letter | File | Meaning |
| --- | --- | --- |
| F | `.haxaml/facts.yaml` | What is true about the project |
| R | `.haxaml/rules.yaml` | How agents should work |
| A | `.haxaml/acts.yaml` | What happened, changed, or was decided |
| M | `.haxaml/map.yaml` | What modules exist and what affects what |
| E | `.haxaml/expect.yaml` | What should happen next |

The files are plain YAML. Humans can read them. Machines can validate them. Agents can use them without being handed a huge wall of context every time.

## Install

With pip:

```bash
pip install haxaml
```

With uv:

```bash
uv tool install haxaml
```

For local development:

```bash
git clone https://github.com/haxsysgit/haxaml.git
cd haxaml
uv sync --all-extras
uv run haxaml --help
```

## Quick Start

Create FRAME files in an existing project:

```bash
haxaml init
```

Validate them:

```bash
haxaml validate
```

Generate compact context for an agent:

```bash
haxaml context --tokens
```

Export agent-native instruction files:

```bash
haxaml export --all
```

Start and complete a governed task:

```bash
haxaml run --task "add checkout flow" --description "Implement checkout state and validation"
haxaml done --task "add checkout flow" --result success --changes "Added checkout state and tests"
```

## MCP Setup

Haxaml also runs as an MCP server, which is the nicest workflow if your editor or agent supports MCP.

The easiest setup is `uvx`. No global install and no virtualenv ceremony.

Use this as the default MCP config:

```json
{
  "mcpServers": {
    "haxaml": {
      "command": "uvx",
      "args": ["--from", "haxaml", "haxaml-mcp"],
      "env": {
        "HAXAML_PROJECT_DIR": "/path/to/your/project"
      }
    }
  }
}
```

The MCP server exposes tools for init, validation, context, run tracking, state compaction, exports, adoption, needs checks, impact checks, and benchmarks.

Why the `--from haxaml` bit matters: the package is named `haxaml`, while `haxaml-mcp` is the command installed by that package.

If you prefer a stable local install, use:

```bash
uv tool install haxaml
```

Then configure MCP with:

```json
{
  "mcpServers": {
    "haxaml": {
      "command": "haxaml-mcp",
      "env": {
        "HAXAML_PROJECT_DIR": "/path/to/your/project"
      }
    }
  }
}
```

## Agent Exports

FRAME is the source of truth. Agent files are generated views.

| Agent/tool | Export command | Output file |
| --- | --- | --- |
| Claude Code | `haxaml export --agent claude` | `CLAUDE.md` |
| Codex | `haxaml export --agent codex` | `AGENTS.md` |
| GitHub Copilot | `haxaml export --agent copilot` | `.github/copilot-instructions.md` |
| Cursor | `haxaml export --agent cursor` | `.cursor/rules/haxaml.mdc` |
| Windsurf/Cascade | `haxaml export --agent windsurf` | `.windsurf/rules/haxaml.md` |
| Gemini CLI | `haxaml export --agent gemini` | `GEMINI.md` |

That means you can keep one governed model and still feed each tool the file format it expects.

## Existing Projects

If a repo already has agent files, Haxaml can inventory them and scaffold FRAME from that evidence.

Dry run:

```bash
haxaml adopt --from-native
```

Write adoption notes and missing FRAME files:

```bash
haxaml adopt --from-native --write
```

Haxaml does not invent project truth during adoption. It points at the evidence and leaves unknowns explicit so an agent or human can fill them properly.

## Benchmarks

Haxaml currently includes practical token and state-growth utilities:

```bash
haxaml benchmark --dir .
```

These measure YAML/JSON token counts, parse speed, FRAME context budget, and simulated `acts.yaml` growth.

Important detail: FRAME is not sold as "YAML is always smaller than markdown." Sometimes raw markdown is smaller. The value is deterministic governance: validation, state tracking, compact compiled views, and a source of truth that survives tool switching.

## Development

```bash
uv sync --all-extras
uv run pytest -q
uv build
uv run twine check dist/*
```

The package is managed with `uv`. Release publishing is handled by the GitHub workflow in `.github/workflows/publish.yml` and uses `uv publish`.

## Project Status

Current version: `0.1.0`

Working today:

- FRAME schemas
- CLI commands
- MCP server
- state/run tracking
- native agent exports
- project adoption
- auto re-export
- token benchmark utilities

Still evolving:

- deeper FRAME-vs-long-prompt benchmark suite
- packaging polish
- more examples from real projects

## More Docs

- [advanced.md](advanced.md) for the detailed FRAME model, command reference, MCP tools, export behavior, map policy, and release notes.
- Research files in this repo cover the prompt-format and agent-governance background that led to Haxaml.
