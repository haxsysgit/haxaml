# Haxaml

[![PyPI version](https://img.shields.io/pypi/v/haxaml.svg)](https://pypi.org/project/haxaml/)

**MCP-first, Git-style workflow governance for AI coding agents.**

Most AI coding issues do not begin when an agent writes bad code. They begin earlier, when the agent jumps from a vague request straight into implementation without understanding the project, the missing context, the risks, or what "done" actually means.

Haxaml is a token and context-efficient engine built on top of FRAME: a simple model that splits project understanding into five parts: Facts, Rules, Acts, Map, and Expect.

Instead of dumping the whole project into an agent and hoping it figures things out, Haxaml gives the agent a governed workflow. It helps the agent prepare before coding, pull only the context needed for the task, verify the work with evidence, and record useful state for the next agent.

The result is a calmer agent workflow: less guessing, less context bloat, better handoffs, and a project state that can travel across Claude Code, Codex CLI, Cursor, Copilot, Windsurf, and any MCP-compatible agent.

## What Haxaml Is Not

- **Not an AI memory backpack.** Haxaml is not mainly about storing random facts for an agent to recall later. It is about shaping project understanding so agents can prepare, plan, verify, and record their work properly.
- **Not just a prompt file.** `AGENTS.md`, `CLAUDE.md`, Cursor rules, Copilot instructions, and similar files are adapters. Haxaml is the governed engine underneath them.
- **Not a replacement for your agent.** Haxaml does not write the code for the agent. It gives the agent a workflow spine so the work starts with context, follows project rules, and ends with verification.
- **Not a giant context dump.** Haxaml is built to reduce context noise by giving the agent the right project signals at the right time.

## How It Works

Haxaml exposes a lifecycle through MCP tools. The agent follows this flow before, during, and after implementation:

| Phase | Tool(s) | What happens |
|---|---|---|
| **about** | `haxaml_about` | The agent learns what Haxaml is, what FRAME means, and how to operate inside the project |
| **guidance** | `haxaml_guidance` | Haxaml classifies the request and decides whether it is governed project work or a utility task |
| **prebuild** | `haxaml_prebuild` → `haxaml_context_pack` | Agent classifies the task, checks FRAME readiness, opens a governed session, then pulls task-scoped context |
| **build** | *(no Haxaml tool)* | The agent edits files, writes code, runs commands, answers a question and performs the actual implementation |
| **verify** | `haxaml_session_verify` | The agent records what it inspected, what it changed, what was checked, and what risks remain |
| **record** | `haxaml_session_record` → `haxaml_expect_sync` | The outcome is written into project history and expectations are synced for future work |

In short:

```text
about → guidance → prebuild → context_pack → build → verify → record → expect_sync
```

Lower-level tools like `haxaml_session_start` and `haxaml_session_plan` still exist, but they are now the advanced/manual path. The recommended public flow uses `haxaml_prebuild`.

Project memory lives in `.haxaml/` — versioned files your agent uses at runtime, not a static wall of text.

## Install

```bash
uvx haxaml-mcp
```

For persistent local installs:

```bash
uv tool install haxaml-mcp
```

## MCP Start

Configure your MCP client to launch `haxaml-mcp`. For project-scoped configs, cwd is enough. For user-wide configs, set `HAXAML_PROJECT_DIR` to the project root. See [learn/haxaml-mcp.md](https://github.com/haxsysgit/haxaml/blob/main/learn/haxaml-mcp.md) for the full MCP/architecture guide.

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
