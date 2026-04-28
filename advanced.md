# Advanced Haxaml Guide

This is the deeper reference for Haxaml, FRAME, the CLI, MCP, exports, benchmarks, and releases.

The README gives the quick story. This file is the "how does it actually work?" version.

## Core Idea

Haxaml is a deterministic management layer for AI-assisted development.

It does not reason about your code by itself. It does not generate app code. It does not use an LLM internally. It gives LLM coding agents a structured project model they can read, validate, update, and export.

FRAME is that model:

- **Facts**: what is true about the project
- **Rules**: how agents should work
- **Acts**: what happened and what changed
- **Map**: what modules exist and what depends on what
- **Expect**: what should happen next

The point is boring on purpose: keep project truth out of scattered chat history.

## Storage Model

By default Haxaml stores FRAME in `.haxaml/`.

| File | Required | Purpose |
| --- | --- | --- |
| `.haxaml/facts.yaml` | yes | Project identity, goal, stack, constraints, features, success criteria |
| `.haxaml/rules.yaml` | yes | Agent behavior rules, task boundaries, reporting expectations |
| `.haxaml/acts.yaml` | yes | Active task, completed work, decisions, risks, run history |
| `.haxaml/expect.yaml` | yes | Plan, phases, runbook, map policy, upcoming work |
| `.haxaml/map.yaml` | optional | Modules, ownership, dependencies, impact checks |

Compatibility fallbacks still exist:

- root `facts.yaml`, `rules.yaml`, `acts.yaml`, `expect.yaml`
- legacy `brain.yaml`, `mind.yaml`, `state.yaml`

New projects should use `.haxaml/`.

## Package Layout

Current package structure:

```text
haxaml/
  adoption.py        native agent file adoption
  auto_export.py     stale export detection, hook, watcher
  benchmarks.py      token and state-growth measurements
  brain_builder.py   guided facts draft builder
  cli.py             Click CLI
  context.py         compact context rendering
  export_engine.py   agent-native markdown exports
  init_templates.py  default FRAME scaffolds
  map_policy.py      map complexity and impact policy
  mcp_server.py      MCP tools and resources
  paths.py           FRAME path resolution
  runner.py          governed task lifecycle
  schemas/           packaged FRAME schemas
  state_manager.py   acts.yaml updates and compaction
  supervision.py     needs and impact summaries
  validator.py       JSON Schema validation
tests/
  test_*.py
```

The schemas are packaged under `haxaml/schemas/` so installed wheels can validate projects without needing a source checkout.

## CLI Reference

Initialize FRAME:

```bash
haxaml init
```

Validate FRAME:

```bash
haxaml validate
```

Run completeness checks:

```bash
haxaml doctor
```

Render compact context:

```bash
haxaml context
haxaml context --tokens
```

Start and finish governed work:

```bash
haxaml run --task "catalog" --description "Build product listing"
haxaml done --task "catalog" --result success --changes "Added listing endpoint"
```

Inspect and compact state:

```bash
haxaml state show
haxaml state compact --keep 5
```

Adopt an existing project:

```bash
haxaml adopt --from-native
haxaml adopt --from-native --write
```

Export native agent files:

```bash
haxaml export --agent codex
haxaml export --agent claude
haxaml export --agent copilot
haxaml export --agent cursor
haxaml export --agent windsurf
haxaml export --agent gemini
haxaml export --all
```

Run token utilities:

```bash
haxaml benchmark --dir .
```

Start the MCP server:

```bash
uvx --from haxaml haxaml-mcp
haxaml mcp
haxaml-mcp
```

## MCP Server

Haxaml uses stdio MCP transport.

The recommended setup is `uvx`, because it avoids global installs and keeps the MCP command copy-pasteable across editors.

Default config:

```json
{
  "mcpServers": {
    "haxaml": {
      "command": "uvx",
      "args": ["--from", "haxaml", "haxaml-mcp"],
      "env": {
        "HAXAML_PROJECT_DIR": "/path/to/project"
      }
    }
  }
}
```

`uvx haxaml-mcp` is not enough because `uvx` will look for a package named `haxaml-mcp`. Use `--from haxaml` so it installs the `haxaml` package and runs the `haxaml-mcp` console script.

If you want a persistent local install instead:

```bash
uv tool install haxaml
```

Then use:

```json
{
  "mcpServers": {
    "haxaml": {
      "command": "haxaml-mcp",
      "env": {
        "HAXAML_PROJECT_DIR": "/path/to/project"
      }
    }
  }
}
```

Tools exposed:

| Tool | Purpose |
| --- | --- |
| `haxaml_init` | Scaffold FRAME files |
| `haxaml_validate` | Validate FRAME against schemas |
| `haxaml_doctor` | Check completeness beyond schema validity |
| `haxaml_context` | Render compact project context |
| `haxaml_health` | Report validation, state, map, and context health |
| `haxaml_run` | Start a governed task |
| `haxaml_done` | Complete a task and record outcome |
| `haxaml_export` | Export agent-native instruction files |
| `haxaml_adopt` | Inventory native agent files and scaffold FRAME |
| `haxaml_needs` | List missing user/agent inputs |
| `haxaml_impact` | Check module impact using map policy |
| `haxaml_state_show` | Summarize current acts state |
| `haxaml_state_compact` | Compact old run history |
| `haxaml_benchmark` | Run token/context measurements |

Resources exposed:

| Resource | Purpose |
| --- | --- |
| `haxaml://frame/facts` | Read facts |
| `haxaml://frame/rules` | Read rules |
| `haxaml://frame/acts` | Read acts |
| `haxaml://frame/expect` | Read expect |
| `haxaml://frame/map` | Read map |
| `haxaml://context` | Read compiled compact context |

## Export Model

FRAME is the source of truth. Agent instruction files are compiled views.

This matters because each tool wants a different shape:

- Codex reads `AGENTS.md`
- Claude Code reads `CLAUDE.md`
- Copilot reads `.github/copilot-instructions.md`
- Cursor reads `.cursor/rules/*.mdc`
- Windsurf reads `.windsurf/rules/*.md`
- Gemini reads `GEMINI.md`

Haxaml keeps the content deterministic. It does not ask an LLM to rewrite exports. Same FRAME input means same export output.

### Codex Prompt Profile

`rules.yaml` can include `agent_profile` for Codex exports:

```yaml
agent_profile:
  persona:
    role: "Pragmatic implementation agent"
    tone:
      - "Clear"
      - "Concise"
  reasoning_policy:
    private_reasoning: "Keep private reasoning internal."
    public_rationale: "Give concise rationale and checks."
    prohibit_cot_transcript: true
  output_contract:
    required_sections:
      - "Summary"
      - "Verification"
  few_shot_examples: []
  example_policy:
    max_examples: 4
    max_input_chars: 260
    max_output_chars: 360
    max_total_chars: 2200
```

The policy intentionally avoids asking agents to reveal chain-of-thought transcripts. Public output should be concise rationale, checks, and concrete results.

## Runbook: expect.yaml

`expect.yaml` is the forward plan. It says where the project is going and what runs should happen next.

Example:

```yaml
planning:
  goal: "Build an ecommerce MVP"
  strategy: "Catalog first, then basket, checkout, and order records."
  estimated_runs: 6
  project_size: medium
  map_required: false

runbook:
  - run: 1
    phase: "Catalog"
    status: active
    goal: "Create product domain"
    outcome: "Product model, seed catalog, and listing endpoint exist."
    depends_on: []
    touches: ["products", "database"]
    requires: ["database decision", "product fields"]
    uses_map: false
    verify: ["product tests pass"]
    done_when: "Products can be listed from seeded data."
```

Haxaml validates the structure. It does not decide the plan. The user or AI agent provides the actual project strategy.

## Map Policy

Small projects can often work from facts, rules, acts, and expect.

Use `map.yaml` when:

- expected runs go above 12
- there are 10 or more modules
- one run touches three or more modules
- shared integrations affect multiple modules
- bug fixes need explicit blast-radius checks
- multiple agents work in parallel

When map is required, agents should read `.haxaml/map.yaml` before touching source files.

## Benchmarks

Current benchmark utilities measure:

- YAML vs JSON token counts
- YAML vs JSON parse speed
- FRAME context token budget
- simulated `acts.yaml` state growth

Run:

```bash
haxaml benchmark --dir .
```

Current limitation: this does not yet prove FRAME is more efficient than every long-prompt or markdown-notes workflow. Raw token size depends on the fixture. Haxaml's value is the deterministic governance layer: validation, state history, runbook structure, and reproducible compiled exports.

## Auto Export

Install a git pre-commit hook:

```bash
haxaml install-hook
```

Watch `.haxaml/` for changes:

```bash
haxaml watch
```

The MCP server also re-exports after init and done operations when exports are stale.

## Development Workflow

Install dependencies:

```bash
uv sync --all-extras
```

Run tests:

```bash
uv run pytest -q
```

Build package:

```bash
uv build
```

Check package metadata:

```bash
uv run twine check dist/*
```

Publish manually:

```bash
uv publish --token "$PYPI_TOKEN"
```

## GitHub Release Workflow

Publishing is handled by `.github/workflows/publish.yml`.

The workflow runs on tags that match `v*` and on manual dispatch. It:

1. checks out the repo
2. installs uv
3. installs Python
4. syncs all extras
5. runs tests
6. builds the package
7. checks the package metadata
8. publishes with `uv publish`

Required GitHub secret:

```text
PYPI_TOKEN
```

## Tagging

Recommended release flow:

```bash
git tag -a v0.1.0 -m "Haxaml 0.1.0 public package release"
git push origin v0.1.0
```

Tag pushes trigger the PyPI workflow.

## Status

Current release line: `0.1.x`

Working:

- FRAME schemas and validation
- CLI
- MCP server
- run/state tracking
- context rendering
- native agent exports
- adoption from existing agent files
- auto export
- token benchmark utilities

Planned:

- broader benchmark scenarios
- more real-world examples
- PyPI release polish
- CLI parity where MCP tools are ahead
