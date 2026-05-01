# Haxaml

[![PyPI version](https://img.shields.io/pypi/v/haxaml.svg)](https://pypi.org/project/haxaml/)

Haxaml is an LLM-first governance layer for coding agents.

It is an MCP-first project: agents are expected to work through the Haxaml MCP server, with the CLI available mainly for local setup and fallback.

Latest release: `0.5.2`.

Haxaml gives agents a deterministic project memory model called **FRAME**, plus MCP tools that make context, rules, verification, and handoff explicit during real work.

## Why It Exists

Agent instructions are usually scattered across prompt files, chat history, local conventions, and whatever the current model remembers. That works until the project grows, the session rolls over, or a different agent enters the repo.

Haxaml keeps the operational truth in versioned project files and exposes it through a predictable workflow. Agents can ask for the right context, follow project rules, verify before claiming success, and record what changed.

## What Agents Get

- Project facts, rules, history, expectations, and impact maps in `.haxaml/`
- Task-specific context packs instead of giant prompt dumps
- Validation and reconcile checks before state is trusted
- Verify/record gates for governed work
- Export paths for native agent files such as `AGENTS.md`, `CLAUDE.md`, Cursor rules, Copilot instructions, and Gemini guidance

## Install

```bash
uvx haxaml-mcp
```

For persistent local installs:

```bash
uv tool install haxaml-mcp
```

## MCP Start

Configure your MCP client to launch `haxaml-mcp` with `HAXAML_PROJECT_DIR` set to the project root. See [learn/haxaml-mcp.md](https://github.com/haxsysgit/haxaml/blob/main/learn/haxaml-mcp.md) for the full MCP/architecture guide.

Once connected, agents can initialize and validate through MCP tools:

- `haxaml_init`
- `haxaml_validate`

Optional fallback: run `haxaml init` / `haxaml validate` directly when MCP is unavailable.

## MCP Config

Official docs:
- Claude Code MCP docs: https://docs.claude.com/en/docs/claude-code/mcp
- OpenAI Codex MCP docs: https://developers.openai.com/docs/mcp
- MCP architecture: https://modelcontextprotocol.io/docs/learn/architecture

### Project-scoped (recommended)

Place config in the project root. The server uses cwd as the project directory — no env var needed.

**Claude Code** — `.mcp.json` in project root:

```json
{
  "mcpServers": {
    "haxaml": {
      "command": "uvx",
      "args": ["haxaml-mcp"]
    }
  }
}
```

**Codex CLI** — `.codex/config.toml` in project root:

```toml
[mcp_servers.haxaml]
command = "haxaml-mcp"
```

**Generic MCP JSON** (Windsurf, Cursor, etc.):

```json
{
  "mcpServers": {
    "haxaml": {
      "type": "stdio",
      "command": "uvx",
      "args": ["haxaml-mcp"]
    }
  }
}
```

### User-wide

Set `HAXAML_PROJECT_DIR` to pin the server to a specific project regardless of cwd. Useful for global configs that live outside the project.

**Claude Code** — `~/.claude.json`:

```json
{
  "mcpServers": {
    "haxaml": {
      "command": "uvx",
      "args": ["haxaml-mcp"],
      "env": {
        "HAXAML_PROJECT_DIR": "/absolute/path/to/project"
      }
    }
  }
}
```

**Codex CLI** — `~/.codex/config.toml`:

```toml
[mcp_servers.haxaml]
command = "haxaml-mcp"
env = { HAXAML_PROJECT_DIR = "/absolute/path/to/project" }
```

**Generic MCP JSON**:

```json
{
  "mcpServers": {
    "haxaml": {
      "type": "stdio",
      "command": "uvx",
      "args": ["haxaml-mcp"],
      "env": {
        "HAXAML_PROJECT_DIR": "/absolute/path/to/project"
      }
    }
  }
}
```

## Bootstrap Prompt

Paste this into your native agent instruction file (`AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `.github/copilot-instructions.md`, etc.):

```md
This repository uses Haxaml for agent governance.

Use the Haxaml MCP server for governed project work.
Before governed project work, call haxaml_about(project_dir='.') once in the active MCP session.
Follow the workflow returned by that tool.
If a governed step is skipped or out of order, treat Haxaml contract errors as hard blockers and fix the lifecycle step before continuing.
Do not edit .haxaml/* for utility or side tasks that are not governed project work.
```

## FRAME Files

- `.haxaml/facts.yaml` - project truth
- `.haxaml/rules.yaml` - agent operating rules
- `.haxaml/acts.yaml` - execution diary and decisions
- `.haxaml/expect.yaml` - run plan and milestones
- `.haxaml/map.yaml` - optional module ownership and impact map

## Docs

- [learn/FRAME.md](https://github.com/haxsysgit/haxaml/blob/main/learn/FRAME.md) - FRAME memory model
- [learn/haxaml.md](https://github.com/haxsysgit/haxaml/blob/main/learn/haxaml.md) - how Haxaml makes FRAME operational
- [learn/haxaml-mcp.md](https://github.com/haxsysgit/haxaml/blob/main/learn/haxaml-mcp.md) - MCP setup, architecture mapping, and lifecycle contract
- [v1.0_Roadmap.md](https://github.com/haxsysgit/haxaml/blob/main/v1.0_Roadmap.md) - roadmap from `0.6.0` to `1.0`
- [docs/architecture.md](https://github.com/haxsysgit/haxaml/blob/main/docs/architecture.md) - module layout and MCP split overview
- [docs/mcp-tool-reference.md](https://github.com/haxsysgit/haxaml/blob/main/docs/mcp-tool-reference.md) - compact MCP tool and resource index
- [CONTRIBUTING.md](https://github.com/haxsysgit/haxaml/blob/main/CONTRIBUTING.md) - contributor workflow and expectations
- [examples/minimal-governed-flow](https://github.com/haxsysgit/haxaml/tree/main/examples/minimal-governed-flow) - minimal FRAME project for governed-flow smoke tests
