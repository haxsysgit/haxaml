# Haxaml

[![PyPI version](https://img.shields.io/pypi/v/haxaml.svg)](https://pypi.org/project/haxaml/)

**Force Agents to Plan. Record the Acts. Build the End from the Beginning.**

## Why Haxaml

### The Problem

I started Haxaml because I noticed a recurring pattern: AI agents are builders who skip the blueprints. They read a few chunks of code, make a guess about the intent, and head straight for implementation. This improvisation is where the real failures begin. Most coding issues do not happen because the model is limited; they happen because the agent is working in a vacuum without understanding the project, the rules, or the criteria for being "done."

### The Rule

This project is my attempt to fix that. Haxaml is essentially an agent diary and a workflow protocol. It is built on a simple rule: **no planning, no building.**

### The Model

It uses a model I call **FRAME** to split project understanding into five parts: Facts, Rules, Acts, Map, and Expect. Instead of letting an agent guess, I give them a notebook that they are required to fill out. If they skip a step or ignore a project rule, the contract breaks.

### The Handoff

The goal is to move the "brain" of the project out of the AI provider's temporary memory and into the repository itself. When you switch between Claude Code, Cursor, Windsurf, or any other tool, the next agent should be able to read the diary, the map, and the expected runbook and continue from real project state without rereading the whole codebase.

## The Agent Diary Philosophy

I want to move away from agents that act like code generators with intelligence and toward agents that act like seasoned builders. A real professional does not start by hammering nails: they study the site and verify the materials before the first tool is ever lifted. Haxaml provides the structure they need to maintain that discipline:

1. **Gather Materials:** Just like a builder cannot work if the owner does not buy the materials: the agent must identify and ask for every tool, API key, or DB URI they need before they start.
2. **Plan the End:** They have to define what "success" looks like before they touch a single line of code.
3. **Budget Tokens:** While token budgeting is a convenience feature here: it matters for efficiency. Haxaml uses incremental reads to ensure agents only pull the context delta they need for the specific task.
4. **Clarify Intent:** I want the agent to stop and ask me questions if the task is high-risk or the intent is vague.

## How the Lifecycle Works

Haxaml operates through an MCP (Model Context Protocol) server that enforces a deterministic sequence. Every agent that enters the repo follows this playbook:

| Phase | Tool | The Purpose |
|---|---|---|
| **About** | `haxaml_about` | The agent reads the "Laws of the Land" and learns how to operate here. |
| **Guidance** | `haxaml_guidance` | Haxaml determines if the request is real project work or just a quick off-topic question. |
| **Prebuild** | `haxaml_prebuild` | **The Architect Phase.** This is where the agent classifies the task, checks risks, identifies missing materials, and turns the requested end state into an expected run path. |
| **Context** | `haxaml_context_pack` | **The Builder Phase.** The agent pulls a task-scoped context pack. This uses refresh deltas to save tokens. |
| **Build** | *(External)* | The implementing agent does the work (edits, tests, commands) outside Haxaml tools. |
| **Verify** | `haxaml_session_verify` | **The Inspection Phase.** The agent must provide evidence of what they checked and what risks still exist. |
| **Record** | `haxaml_session_record` | The outcome is written into the Acts diary for the next agent to pick up. |
| **Sync** | `haxaml_expect_sync` | The recorded outcome updates the expected runbook so the next agent sees what was planned, what really happened, and what should happen next. |

## Install

Haxaml is split into three related packages:
- `haxaml`: the core engine and CLI.
- `haxaml-mcp`: the stdio launcher for your editor.
- `haxaml-ui`: a local browser dashboard for humans.

**Note on requirements:** I highly recommend installing [uv](https://docs.astral.sh/uv/) first. Haxaml uses it internally for managed upgrades, bootstrap tasks, and fast tool execution.

### 1. Recommended: uv tool
This is the cleanest way to add Haxaml to your global path:
```bash
uv tool install "haxaml[full]"
```

### 2. Traditional: pip
You can also install the full suite into your active environment:
```bash
pip install "haxaml[full]"
```

### 3. Run Immediately
If you want to run the MCP server instantly without a persistent install:
```bash
uvx haxaml-mcp
```

## Setup and Adoption

I want Haxaml to be hard to use badly, so setup is now the single onboarding integration point.

- `haxaml setup` now runs as a minimal scaffold-style terminal flow by default in a real TTY, but stays machine-friendly in non-interactive or `--format json` flows.
- The setup contract is provider-aware: strong target evidence should guide defaults, weak shared signals like `AGENTS.md` should stay advisory, and the final output should show exact targets, paths, and previews before writing.
- In a fresh repo it creates `.haxaml/` and then writes the selected target's native instructions plus any matching skill, agent, config, or workflow adapters you asked for.
- In an existing repo it should adopt native files instead of replacing them. Haxaml appends managed pointer blocks where safe, keeps the full governed adapter in `.haxaml/setup/targets/`, and records adoption state in `.haxaml/adoption/`.
- Known MCP config shapes merge only the Haxaml-owned entry or table (`mcpServers.haxaml` or `[mcp_servers.haxaml]`) and preserve unrelated config.
- `haxaml setup --dry-run` now shows exact paths plus concise previews instead of only file counts.
- `haxaml setup print` still shows the full rendered contents before writing.
- `haxaml setup doctor` checks for missing managed files, drift, and manual follow-up.

The 1.0 hardening track treats setup target clarity and rerun idempotency as blockers. Setup must never silently downgrade a selected provider to `generic`, and rerunning setup over active FRAME state must be safe by default.

Managed upgrades use the installed `haxaml` CLI. `haxaml upgrade` refreshes core plus MCP by default, and `haxaml upgrade --include-ui` adds the dashboard package when you use the full suite.

If you want only the bare FRAME scaffold without onboarding, use `haxaml init`. That command now creates missing core FRAME files and stops there.

## Local Dashboard

I built a lightweight dashboard so you can see the "state of the union" for your repo. It is read-only and runs on localhost. It lets you drill down into the Acts history, check your project Facts, inspect the Map boundaries, and see what the agent is currently expected to build next.

```bash
haxaml dashboard
```

## The FRAME Files

- `.haxaml/facts.yaml`: The project truth: the stack, the goals, and the hard constraints.
- `.haxaml/rules.yaml`: The operating laws for the agent.
- `.haxaml/acts.yaml`: The diary of what happened: recent decisions, verification evidence, recorded runs, and what really happened against the plan.
- `.haxaml/map.yaml`: The module ownership and impact rules that explain what changes can affect what.
- `.haxaml/expect.yaml`: The forward-looking plan: the final intended end state, expected runs, checkpoints, milestones, and done criteria the agent is working toward.

The important loop is simple: `expect` defines the planned path and finish line, `acts` records the checks and real outcomes, and `map` explains the scope and impact boundaries between them.

## Roadmap and Docs

- [goals.md](./goals.md): the canonical product vision, thesis, and feature direction.
- [learn/FRAME.md](./learn/FRAME.md): the underlying memory model.
- [learn/haxaml.md](./learn/haxaml.md): how Haxaml turns FRAME into a working governed system.
- [learn/haxaml-mcp.md](./learn/haxaml-mcp.md): the operator-facing MCP guide.
- [docs/architecture.md](./docs/architecture.md): how the modules are split.
- [CONTRIBUTING.md](./CONTRIBUTING.md): how to help build the protocol.
