# Contributing to Haxaml

If you want to contribute here, the main thing to understand is that Haxaml is not "just another prompt file repo." It is trying to make agent work more disciplined: less improvisation, more explicit project state, clearer lifecycle rules, and better handoffs across tools.

That means good contributions are not just code that passes. They have to fit the product direction, preserve the public contract, and make the system easier to trust.

## First: understand what Haxaml already does

Before you start changing behavior, get the current model into your head first.

At minimum, read:

- `README.md`
- `learn/FRAME.md`
- `docs/architecture.md`
- the specific module or tests you plan to touch

If your patch changes onboarding or target integration, also read:

- `0.7.x_Roadmap.md`
- `haxaml/setup/*`
- `tests/test_cli.py`

If your patch changes governed lifecycle or MCP behavior, also read:

- `learn/haxaml-mcp.md`
- `docs/mcp-tool-reference.md`
- `haxaml/mcp/tools_*.py`
- `tests/mcp/`

I am not saying you need to inspect every single line an LLM generates or memorize the whole codebase before opening a file. I am saying you need to understand the current behavior you are changing. If you cannot explain what Haxaml does today, you are not ready to change what it should do tomorrow.

## What this repo values

- Deterministic behavior over clever behavior.
- Clear governed workflows over hidden heuristics.
- Small, reviewable changes over sprawling refactors.
- Curated tests over noisy test churn.
- Backward compatibility for public MCP and CLI surfaces unless a break is explicit and planned.

## Good contribution targets

Useful contributions usually look like one of these:

- fixing a bug with a clear reproduction
- tightening an MCP or CLI contract without breaking it
- improving setup/onboarding behavior for supported targets
- improving docs so they match real behavior
- adding focused regression coverage for an actual edge case
- reducing ambiguity in FRAME, lifecycle, or export behavior

Less useful contributions usually look like this:

- broad refactors with no behavioral reason
- adding abstractions before there is repeated pain
- changing docs to describe an imagined future instead of current behavior
- adding tests that assert implementation noise rather than real user-facing behavior

## Before you write code

For non-trivial changes, open or discuss an issue first.

This matters more here than in a throwaway utility project, because Haxaml has a few surfaces that other tools may already depend on:

- MCP tools and payloads
- CLI commands and output expectations
- generated adapter/setup files
- FRAME file expectations

If your change affects one of those, scope agreement first will save time.

## Local setup

`uv` is the preferred workflow in this repo.

```bash
uv venv
source .venv/bin/activate
uv pip install -e .[dev]
```

If you prefer plain `pip`, that is fine too:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

## Project map

The repo is split by responsibility. Start in the area closest to your change.

- `haxaml/mcp_server.py`
  - public MCP entrypoint
- `haxaml/mcp/`
  - MCP tool registration and tool implementations
  - `tools_frame.py`, `tools_lifecycle.py`, `tools_prebuild.py`, `tools_ops.py`, `tools_benchmark.py`
- `haxaml/setup/`
  - setup/onboarding registry, planning, rendering, adoption, writing, doctor output
- `haxaml/export_engine.py`
  - FRAME to agent-native instruction rendering
- `haxaml/frame_model.py`, `haxaml/validator.py`, `haxaml/reconcile.py`
  - core FRAME loading, validation, and consistency behavior
- `haxaml/runtime_cache.py`
  - long-lived in-process snapshot and refresh behavior
- `packages/haxaml-mcp/`
  - launcher package metadata
- `packages/haxaml-ui/`
  - dashboard package metadata
- `tests/`
  - non-MCP tests
- `tests/mcp/`
  - MCP-focused coverage

## Public contract areas

Be conservative in these areas.

### MCP tools

Normal PRs should not casually:

- rename MCP tools
- remove tool fields
- reshape payloads in incompatible ways
- break `haxaml.mcp_server:main`

If you think a break is worth it, make the case clearly and tie it to an intentional release boundary.

### CLI behavior

The CLI is not just a thin shell wrapper anymore. `haxaml setup`, `haxaml setup print`, and `haxaml setup doctor` are now product surface.

If you change CLI behavior, also think about:

- dry-run vs write parity
- text output vs JSON output
- fresh setup vs adoption flow
- project scope vs user scope

### Generated files

Generated setup/export files are part of the user contract too. If you change renderers, keep output intentional and explain the change in the PR.

## Working with LLM-generated code

Use LLMs if they help you move faster. Just do not outsource judgment to them.

You own the patch you submit.

That means:

- understand the behavior before changing it
- delete code the model added that the repo does not need
- align with existing naming and structure
- check that new branches are actually reachable
- make sure tests prove the behavior, not just the presence of code

This project does not need more volume. It needs more clarity.

## Testing expectations

Your tests should be well curated.

Do not add a pile of redundant assertions just to look thorough. Add the smallest set of tests that proves the behavior change and protects the edge you touched.

Rough guide:

- touched MCP tools: update `tests/mcp/*`
- touched setup/onboarding: update `tests/test_cli.py` and any setup-specific paths it exercises
- touched rendering/export: update `tests/test_export_engine.py`
- touched version or packaging logic: update `tests/test_versioning.py`
- touched runtime refresh/caching: update `tests/test_runtime_cache.py` or `tests/mcp/test_context_refresh.py`

Run targeted tests while working, then run the full suite before you send the PR.

Targeted examples:

```bash
uv run pytest -q tests/test_cli.py
uv run pytest -q tests/mcp
uv run pytest -q tests/test_export_engine.py
uv run pytest -q tests/test_versioning.py
```

Full suite:

```bash
uv run pytest -q
```

If you changed behavior and did not add or update tests, expect that to be questioned.

## Docs expectations

If behavior changes, docs should change with it.

Typical mapping:

- `README.md`
  - entrypoint, install, setup, high-level product story
- `learn/FRAME.md`
  - FRAME model changes
- `learn/haxaml-mcp.md`
  - governed lifecycle and MCP operating flow
- `docs/mcp-tool-reference.md`
  - MCP tool inventory or surface changes
- `docs/architecture.md`
  - module boundary or package split changes
- `0.7.x_Roadmap.md` / `v1.0_Roadmap.md`
  - roadmap or support-policy changes

Do not update docs just to sound nicer. Update them because the user-facing truth changed.

## Versioning and release metadata

Do not hand-edit package versions casually in feature PRs.

If the work is an actual release task, use:

```bash
python3 scripts/bump_version.py X.Y.Z
uv lock
```

That keeps:

- root package version
- adapter package versions
- dependency ranges
- lockfile state

in sync.

## Pull request checklist

Before opening the PR, make sure you can say yes to these:

- I understand the current behavior I changed.
- The patch is scoped to one coherent job.
- The tests are curated and relevant.
- I ran `uv run pytest -q`.
- I updated docs for any user-visible behavior change.
- I preserved public MCP/CLI behavior, or I made the break explicit.
- The diff does not contain unrelated cleanup.

## Need help?

Open an issue or draft PR with concrete context:

- what you expected
- what actually happened
- what files or tools are involved
- what you already checked

That is much easier to review than a vague "something seems off."
