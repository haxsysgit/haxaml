# Haxaml

Deterministic agent-management framework for AI-assisted development. Stop re-explaining your project every session — Haxaml gives LLM agents a stable governance layer through **FRAME**.

- **You** are the owner. You decide what gets built.
- **Haxaml** is the architect desk — validates, stores, compacts, exports. No intelligence, no ML.
- **AI agents** (Claude, Codex, Cursor, Copilot, Windsurf, Gemini) are the builders. They read FRAME, code, then write back what changed.

## Setup (MCP — Recommended)

The fastest way to use Haxaml is as an MCP server. Your AI agent calls Haxaml tools natively during conversation — no CLI needed.

### Install

```bash
pip install haxaml[mcp]
```

### Connect Your IDE

Add to your MCP config (Windsurf, Cursor, Claude Desktop, or any MCP client):

```json
{
  "mcpServers": {
    "haxaml": {
      "command": "haxaml-mcp",
      "env": { "HAXAML_PROJECT_DIR": "/path/to/your/project" }
    }
  }
}
```

That's it. The agent now has 14 governance tools and 6 read-only FRAME resources.

### What the Agent Gets

| Tool | What it does |
| --- | --- |
| `haxaml_init` | Scaffold `.haxaml/` FRAME files |
| `haxaml_validate` | Validate FRAME against schemas |
| `haxaml_context` | Get compact project context + token count |
| `haxaml_run` / `haxaml_done` | Start and record governed tasks |
| `haxaml_needs` | List what the user still needs to provide |
| `haxaml_impact` | Check module dependencies before changing code |
| `haxaml_health` | Full project health dashboard |
| `haxaml_export` | Export FRAME → agent-native files |
| `haxaml_adopt` | Adopt an existing project into FRAME |

Full MCP reference: [advanced.md](advanced.md)

## Setup (CLI)

If you prefer the command line or need to script Haxaml:

```bash
pip install haxaml
```

```bash
haxaml init              # scaffold .haxaml/ FRAME files
haxaml validate          # check everything is valid
haxaml export --all      # export to all agent-native files
```

## What FRAME Stores

Haxaml implements FRAME in `.haxaml/`:

| File | Role |
| --- | --- |
| `facts.yaml` | Project truth: identity, stack, goals, constraints, services |
| `rules.yaml` | Agent rules: how builders should behave before, during, and after tasks |
| `acts.yaml` | Project diary: active task, completed work, decisions, risks, run history |
| `map.yaml` | Optional architecture map: modules, ownership, dependencies, impact checks |
| `expect.yaml` | Runbook: expected runs, required materials, done criteria, map policy |

The LLM writes the content. Haxaml validates, stores, and keeps the team aligned.

Raw token size is format- and fixture-dependent. In some benchmark fixtures, a single markdown file is smaller than raw YAML. FRAME value is the deterministic governance layer: validated project truth, governed state history, and controllable compiled views (for example `AGENTS.md`) from one source of truth.

## Codex Prompt Profile (Optional)

For Codex exports, `rules.yaml` can include an optional `agent_profile` block:

- `persona` — role, tone, and operating constraints
- `reasoning_policy` — keep private reasoning private, require concise public rationale and checklists
- `output_contract` — required output sections and formatting notes
- `few_shot_examples` — explicit input/output examples
- `example_policy` — deterministic limits for ordering and truncation budget

Haxaml does not generate examples with an LLM. It renders explicit examples first, then derives bounded examples from recent `.haxaml/acts.yaml` decisions/completed-task summaries when needed.

## How It Works

**New project** — the agent calls `haxaml_init`, asks clarifying questions, fills in FRAME, then builds:

```
You: "Build me an ecommerce site"
Agent → haxaml_init()          → scaffolds .haxaml/
Agent → asks: DB? Payment API?  → you provide materials
Agent → fills in FRAME files
Agent → haxaml_run("catalog")  → starts governed task
Agent → builds...
Agent → haxaml_done("catalog") → records in diary
```

**Existing project** — the agent scans what's already there:

```
Agent → haxaml_adopt()         → inventories CLAUDE.md, README, etc.
Agent → fills FRAME from evidence
Agent → haxaml_export("all")   → syncs all agent-native files
```

**Follow-up prompts** — the agent reads the diary instead of asking you to re-explain:

```
You: "Now add payments"
Agent → haxaml_context()       → reads full project state
Agent → haxaml_needs()         → "Blocking: Stripe API key"
You: provide key
Agent → haxaml_run("payments") → builds with full context
```

## Auto Re-Export

FRAME files are the source of truth. Agent-native files (CLAUDE.md, AGENTS.md, etc.) are generated views that stay in sync automatically:

```bash
haxaml install-hook    # git pre-commit hook — re-exports before every commit
haxaml watch           # file watcher — re-exports when .haxaml/ changes
```

The MCP server also auto re-exports after `haxaml_done` and `haxaml_init`.

## Supported Agents

| Agent/tool | Export command | Native file |
| --- | --- | --- |
| Claude Code | `haxaml export --agent claude` | `CLAUDE.md` |
| Cursor | `haxaml export --agent cursor` | `.cursor/rules/haxaml.mdc` |
| Codex | `haxaml export --agent codex` | `AGENTS.md` |
| GitHub Copilot | `haxaml export --agent copilot` | `.github/copilot-instructions.md` |
| Windsurf/Cascade | `haxaml export --agent windsurf` | `.windsurf/rules/haxaml.md` |
| Gemini CLI | `haxaml export --agent gemini` | `GEMINI.md` |

## What Haxaml Is Not

Haxaml is not an LLM, not a code generator, not a prompt library. It is the framework AI agents use to manage themselves through FRAME.

## More

- [advanced.md](advanced.md) — detailed FRAME model, MCP reference, runbooks, map.yaml, benchmarks, compatibility

## Status

MCP server and auto re-export are production-ready. FRAME-vs-long-prompt benchmarks are still planned.
