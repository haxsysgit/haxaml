# Advanced Haxaml Documentation

This document is the detailed reference for Haxaml and FRAME.

FRAME is the governance architecture. Haxaml is the deterministic agent-management framework that implements and works with that architecture.

In the project model, the user is the owner of the house. Haxaml is the non-intelligent developer, supervisor, manager, and architect desk. It has no ML layer and no project understanding of its own. AI agents are the construction workers that reason, code, test, and derive project truth. Haxaml gives those workers the diary, checklists, runbooks, validations, exports, and state transitions they use to keep themselves aligned.

Haxaml's job is to reduce repeated explanation, token waste, context bloat, and accidental drift between agents. The LLM supplies intelligence; Haxaml supplies the structure.

## FRAME Storage

Haxaml stores the agent-management record in `.haxaml/` by default:

| File | FRAME letter | Purpose |
| --- | --- | --- |
| `.haxaml/facts.yaml` | F | Project truth: identity, goal, stack, architecture, database, tools, constraints, success criteria |
| `.haxaml/rules.yaml` | R | Agent rules: read order, boundaries, coding discipline, reporting, forbidden actions |
| `.haxaml/acts.yaml` | A | Current and historical work: active task, completed work, decisions, unresolved dependencies, runs |
| `.haxaml/map.yaml` | M | Optional structure map: modules, ownership, dependencies, impact rules |
| `.haxaml/expect.yaml` | E | Forward plan: phases, expected runs, runbook, map policy, milestones, open questions |

Root-level `facts.yaml`, `rules.yaml`, `acts.yaml`, `expect.yaml`, and legacy `brain.yaml`, `mind.yaml`, `state.yaml` are still read for compatibility. New projects should use `.haxaml/`.

## New Project Flow

```bash
haxaml init
haxaml validate
haxaml doctor
haxaml export --all
```

`haxaml init` creates `.haxaml/` and scaffolds the core FRAME files. The scaffold is intentionally incomplete until the user or AI agent fills in real project decisions. Haxaml does not decide those facts.

A governed task then follows this loop:

```bash
haxaml context --tokens
haxaml run --task "task name" --description "what will change"
# agent implements and tests
haxaml done --task "task name" --result success --changes "what changed" --decisions "what was decided" --risks "remaining risks"
```

## Existing Project Adoption

Existing projects should be adopted through native AI-agent files, not by forcing agents to abandon their existing instruction surfaces.

Haxaml scans for:

| Agent/tool | Native file |
| --- | --- |
| Claude Code | `CLAUDE.md` |
| Codex | `AGENTS.md` |
| GitHub Copilot | `.github/copilot-instructions.md` |
| Cursor | `.cursor/rules/*.mdc` |
| Windsurf/Cascade | `.windsurf/rules/*.md` |
| Gemini CLI | `GEMINI.md` |

Run a dry-run inventory:

```bash
haxaml adopt --from-native
```

Write the adoption report and missing FRAME scaffold:

```bash
haxaml adopt --from-native --write
```

This creates `.haxaml/ADOPTION.md` plus missing `.haxaml/*.yaml` files. It does not infer project facts. The AI agent must read the listed evidence and replace blocking unknowns with real project truth before implementation work starts.

Use `--force` only when intentionally overwriting generated adoption scaffolds.

## Export Model

FRAME files are the source of truth. Agent-native files are generated views.

Raw token size is not guaranteed by format alone. In some fixtures, one markdown file can be smaller than raw YAML files. FRAME value is deterministic governance: schema validation, explicit project/state structure, and reproducible compiled exports from one source of truth.

```bash
haxaml export --agent claude
haxaml export --agent cursor
haxaml export --agent codex
haxaml export --agent copilot
haxaml export --agent windsurf
haxaml export --agent gemini
haxaml export --all
```

Generated files should be regenerated after FRAME changes. Manual edits to generated files can drift from `.haxaml/`.

### Codex Prompt Profile (Codex-first rollout)

`haxaml export --agent codex` supports an optional `rules.agent_profile` block:

- `persona`: role, tone, and operating constraints
- `reasoning_policy`: private-reasoning rule plus concise rationale/checklist policy
- `output_contract`: required response sections and formatting notes
- `few_shot_examples`: explicit bounded input/output examples
- `example_policy`: deterministic ordering and truncation budget

Few-shot source precedence is deterministic:

1. `rules.agent_profile.few_shot_examples`
2. Derived snippets from recent `.haxaml/acts.yaml` decisions and completed-task summaries

Exports avoid requesting chain-of-thought transcripts. The policy is to keep private reasoning private and provide concise, verifiable rationale plus checklists in public responses.

### Auto Re-Export

Haxaml provides three ways to keep exports in sync:

**Git hook** — re-exports before every commit:

```bash
haxaml install-hook      # installs .git/hooks/pre-commit
haxaml uninstall-hook    # removes it
```

**File watcher** — re-exports when `.haxaml/` files change:

```bash
haxaml watch             # polls every 2s, Ctrl+C to stop
```

**MCP auto-export** — the MCP server automatically re-exports after `haxaml_done` and `haxaml_init` if agent files are stale.

## .haxaml/expect.yaml as Runbook

`.haxaml/expect.yaml` is the planning guardrail. It should describe the path from the final goal back to the first implementation run.

Example:

```yaml
planning:
  goal: "Build an ecommerce MVP"
  strategy: "Create product browsing first, then basket, checkout, and order records."
  estimated_runs: 6
  project_size: medium
  map_required: false
  map_reason: "Boundaries are still small enough for .haxaml/rules.yaml."

runbook:
  - run: 1
    phase: "Catalog"
    status: active
    goal: "Create product domain"
    outcome: "Product model, seed catalog, and product listing endpoint exist."
    depends_on: []
    touches: ["products", "database"]
    requires: ["database decision", "product fields"]
    uses_map: false
    verify: ["product tests pass"]
    done_when: "Products can be listed from seeded data."
  - run: 2
    phase: "Basket"
    status: planned
    goal: "Create basket flow"
    outcome: "Users can add, remove, and total basket items."
    depends_on: [1]
    touches: ["basket", "products"]
    requires: ["product IDs", "price representation"]
    uses_map: false
    verify: ["basket tests pass"]
    done_when: "Basket totals are correct and covered by tests."
```

Haxaml validates and preserves this runbook. It does not decide the run sequence; the AI agent drafts it from the user's end goal and repo evidence.

## .haxaml/map.yaml as Project Size Guard

Small projects can keep boundaries in `.haxaml/rules.yaml`. Larger projects need `.haxaml/map.yaml`.

Use `.haxaml/map.yaml` when:

- `.haxaml/expect.yaml` estimates more than 12 runs
- the project has 10 or more modules
- a run touches three or more modules
- database, MCP, API, queue, storage, or auth integrations are shared across modules
- bug fixes need explicit impact checks beyond the changed file
- multiple agents work on separate areas in parallel

When `planning.map_required` is true or a run has `uses_map: true`, the agent must read `.haxaml/map.yaml` before touching source files.

## MCP Server

The MCP server wraps the same modules the CLI uses and exposes them as native tools AI agents can call during conversations.

```bash
pip install -e .
haxaml mcp
```

This starts a stdio-transport MCP server. Configure your IDE to connect:

```json
{
  "mcpServers": {
    "haxaml": {
      "command": "haxaml-mcp",
      "env": { "HAXAML_PROJECT_DIR": "/path/to/project" }
    }
  }
}
```

**14 tools:** `haxaml_init`, `haxaml_validate`, `haxaml_doctor`, `haxaml_context`, `haxaml_health`, `haxaml_run`, `haxaml_done`, `haxaml_export`, `haxaml_adopt`, `haxaml_needs`, `haxaml_impact`, `haxaml_state_show`, `haxaml_state_compact`, `haxaml_benchmark`.

**6 resources:** `haxaml://frame/facts`, `haxaml://frame/rules`, `haxaml://frame/acts`, `haxaml://frame/expect`, `haxaml://frame/map`, `haxaml://context`.

Two tools are MCP-only and not yet in the CLI:

- `haxaml_needs` — aggregates blocking items from facts, acts, and expect into one list of what the user must provide.
- `haxaml_impact` — queries `map.yaml` for module ownership, dependencies, and impact rules.

This section is the public MCP reference for Haxaml.

## Benchmarks

The current benchmark command measures:

- token counts for YAML, pretty JSON, and compact JSON
- parse speed for YAML and JSON
- token budget for FRAME files in a project
- simulated `.haxaml/acts.yaml` growth across many runs

Run:

```bash
haxaml benchmark --dir .
```

This is useful for validating format and context-budget behavior. It does not yet prove that FRAME-managed development is empirically more efficient than long prompts, repeated prompting, manual notes, or separately maintained agent instruction files.

The planned benchmark suite should compare the same development tasks across:

| Strategy | What is measured |
| --- | --- |
| FRAME | `haxaml context` plus governed `.haxaml/acts.yaml` updates |
| Long prompt | A single large project markdown prompt |
| Repeated prompt | Re-explaining project facts at each task start |
| Manual notes | Reading scattered markdown notes without schema validation |

Minimum metrics should include tokens loaded per task, files needed for onboarding, required fact coverage, state growth, and whether output can be validated deterministically.

## Command Reference

```bash
haxaml init                  # scaffold .haxaml FRAME files
haxaml validate              # schema validation
haxaml doctor                # completeness checks beyond schema
haxaml context --tokens      # compact agent context
haxaml run --task "..."      # start a governed task
haxaml done --task "..."     # record task outcome
haxaml state show            # inspect .haxaml/acts.yaml
haxaml state compact         # compact old runs
haxaml adopt --from-native   # inventory existing native agent files
haxaml export --agent codex  # generate AGENTS.md
haxaml export --agent gemini # generate GEMINI.md
haxaml benchmark             # token and growth measurements
haxaml install-hook          # git pre-commit hook for auto re-export
haxaml uninstall-hook        # remove the pre-commit hook
haxaml watch                 # poll .haxaml/ and auto re-export on change
haxaml mcp                   # start MCP server (stdio transport)
```

## Repository Layout

```text
.haxaml/      FRAME governance for this repository
haxaml/       CLI, MCP server, context, validation, state, export, adoption, and benchmark code
schemas/      JSON Schemas for FRAME files
tests/        Haxaml core tests
templates/    Example FRAME facts templates
legacy_docs/  Archived earlier product notes
minitrack/    Smaller FRAME-governed test project
```

## Compatibility

New projects should use `.haxaml/`. Haxaml still reads root-level FRAME files and legacy `brain.yaml`, `mind.yaml`, and `state.yaml` for migration compatibility.
