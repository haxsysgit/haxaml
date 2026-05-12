# Haxaml

[![PyPI version](https://img.shields.io/pypi/v/haxaml.svg)](https://pypi.org/project/haxaml/)

**Workflow governance for AI coding agents.**

Most AI coding failures do not start when an agent writes code. They start earlier, when the agent jumps from a vague request straight into implementation without understanding the project, the missing context, the real risks, or what "done" actually means.

Haxaml exists to turn that early phase into a governed workflow. It gives agent work a durable project contract: what is true, what rules apply, what changed recently, what areas are affected, and what evidence is required before a task is considered complete.

Under the hood, Haxaml is a token and context-efficient engine built on FRAME: a simple model that splits project understanding into five parts, Facts, Rules, Acts, Map, and Expect.

The goal is straightforward: agent work should begin with preparation instead of improvisation. Haxaml keeps project rules, current state, expected runs, and verification evidence in the repository so the workflow survives model switches, tool changes, and long-running projects.

Instead of dumping the whole project into an agent and hoping it figures things out, Haxaml gives the agent a governed path. It helps the agent prepare before coding, pull only the context needed for the task, verify the work with evidence, and record useful state for the next agent.

The result is less guessing, less prompt drift, better handoffs, and a project state that can travel across Claude Code, Codex CLI, Cursor, Copilot, Windsurf, Gemini CLI, and other agent-native environments.

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
| **prebuild** | `haxaml_prebuild` → `haxaml_context_pack` | Agent classifies the task, checks FRAME readiness, opens a governed session, then pulls the first task-scoped context pass |
| **retrieve** | `haxaml_context_fetch` *(optional, repeatable)* | Agent asks for more governed memory only when the first context pass is not enough |
| **build** | *(no Haxaml tool)* | The agent edits files, writes code, runs commands, answers a question and performs the actual implementation |
| **verify** | `haxaml_session_verify` | The agent records what it inspected, what it changed, what was checked, and what risks remain |
| **record** | `haxaml_session_record` → `haxaml_expect_sync` | The outcome is written into project history and expectations are synced for future work |

In short:

```text
about → guidance → prebuild → context_pack → [context_fetch]* → build → verify → record → expect_sync
```

Project memory lives in `.haxaml/` — versioned files your agent uses at runtime, not a static wall of text. Older acts history is kept in `.haxaml/archive/acts-history.yaml` and pulled back only on demand.

In `0.6.7`, long-lived runtimes also stop rereading unchanged FRAME files blindly. Repeated `context_pack` calls now compare the current runtime snapshot to the earlier session snapshot, report what changed, and return smaller refresh deltas when only part of the governed context moved.

## Install

Haxaml now ships as three related packages:

- `haxaml` - core FRAME governance engine and CLI
- `haxaml-mcp` - MCP launcher/runtime package
- `haxaml-ui` - local read-only dashboard package

Common install paths:

```bash
pip install haxaml
pip install haxaml-mcp
pip install haxaml-ui
pip install "haxaml[ui]"
pip install "haxaml[full]"
```

If you want to run the MCP server without a persistent install:

```bash
uvx haxaml-mcp
```

For persistent local installs:

```bash
uv tool install haxaml-mcp
```

After install, the main onboarding command is:

```bash
haxaml setup
```

## Local Dashboard

The first dashboard release is intentionally narrow:

- browser UI, not TUI
- localhost only
- read-only
- overview-first
- all five FRAME files rendered
- archive summary plus drilldown

Launch it with:

```bash
haxaml dashboard
```

Supported flags:

- `--project-dir`
- `--host`
- `--port`
- `--no-open`
- `--read-only`

Install note:

- `haxaml dashboard` is the primary human launcher
- core `haxaml` install now includes the MCP runtime dependency (`mcp`)
- `haxaml[ui]` installs the dashboard package (`haxaml-ui`)
- `haxaml[full]` installs both optional adapter packages
- `haxaml-ui` is the separate dashboard distribution

## Setup and adoption

`haxaml setup` is the onboarding command in `0.7.0`.

On a clean repository it creates `.haxaml/`, writes a root `AGENTS.md` adapter, and installs the shared Haxaml skill in `.agents/skills/haxaml/SKILL.md`. That gives the repository a governed default path before you add target-specific files.

For established codebases, `haxaml setup --adopt auto` scans native instruction files such as `CLAUDE.md`, `AGENTS.md`, Cursor rules, Copilot instructions, and `GEMINI.md`. It preserves those files, adds a small managed pointer block where appropriate, and stores the detailed adoption inventory under `.haxaml/adoption/` instead of pushing that state into core FRAME files.

Use `haxaml setup print` to inspect exactly what setup would write, and `haxaml setup doctor` to audit installed files, drift, missing managed files, and manual follow-up. `--scope user` targets home-directory installs, while `--target` narrows setup to a specific environment such as `claude`, `codex`, `cursor`, `copilot`, or `gemini`.

Where a target has a stable documented file-backed MCP config, setup writes it. Where the surface is settings-backed or not safely documented, setup prints the exact manual step and tracks it in doctor output.

## FRAME Files

- `.haxaml/facts.yaml` - project truth
- `.haxaml/rules.yaml` - agent operating rules
- `.haxaml/acts.yaml` - execution diary and decisions
- `.haxaml/map.yaml` - optional module ownership and impact map
- `.haxaml/expect.yaml` - run plan and milestones

## Docs

- [learn/FRAME.md](https://github.com/haxsysgit/haxaml/blob/main/learn/FRAME.md) - FRAME memory model
- [learn/haxaml.md](https://github.com/haxsysgit/haxaml/blob/main/learn/haxaml.md) - how Haxaml makes FRAME operational
- [learn/haxaml-mcp.md](https://github.com/haxsysgit/haxaml/blob/main/learn/haxaml-mcp.md) - MCP setup, architecture mapping, and lifecycle contract
- [0.7.x_Roadmap.md](https://github.com/haxsysgit/haxaml/blob/main/0.7.x_Roadmap.md) - setup, onboarding, and target support roadmap for the `0.7.x` line
- [v1.0_Roadmap.md](https://github.com/haxsysgit/haxaml/blob/main/v1.0_Roadmap.md) - roadmap from `0.6.0` to `1.0`
- [docs/architecture.md](https://github.com/haxsysgit/haxaml/blob/main/docs/architecture.md) - module layout and MCP split overview
- [docs/mcp-tool-reference.md](https://github.com/haxsysgit/haxaml/blob/main/docs/mcp-tool-reference.md) - compact MCP tool and resource index
- [CONTRIBUTING.md](https://github.com/haxsysgit/haxaml/blob/main/CONTRIBUTING.md) - contributor workflow and expectations
- [examples/minimal-governed-flow](https://github.com/haxsysgit/haxaml/tree/main/examples/minimal-governed-flow) - minimal FRAME project for governed-flow smoke tests
