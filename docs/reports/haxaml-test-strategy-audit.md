# Haxaml Test Strategy Audit

Date: 2026-05-17

The test suite is broad, but too much of it is smoke-level. It proves Haxaml has buttons. It does not yet prove the buttons survive a ranked match with messy state, repeated setup, ambiguous providers, large archives, and agents trying to skip the rules.

## Current Test Reality

The suite currently proves useful basics:

- CLI commands are wired.
- Direct MCP functions return expected envelopes.
- StateManager can read, write, record, and compact simple state.
- Setup can render basic files and merge simple known config shapes.
- Validator catches several schema and semantic problems.
- Runner tests cover a happy lifecycle path.

That is valuable. It is not enough for 1.0.

## Why The Current Tests Missed These Bugs

### They Test Clean Rooms More Than Messy Projects

The user bug happened in an adopted project with weak shared evidence, existing Haxaml state, and rerun behavior. Most tests use fresh temp projects with clean fixtures.

Needed: dirty fixtures that look like real user repos.

### They Test Counts More Than Budgets

Compaction tests checked that old runs moved to archive by count. They did not check whether the hot file stayed under the byte budget or whether `completed_tasks` kept bloating.

Needed: byte-budget tests, token-budget tests, and fixture replay tests from large `acts.yaml` files.

### They Test Function Calls More Than Protocol Contracts

MCP tests import Python functions directly. That bypasses real stdio/client behavior, parameter serialization, resource URI handling, and schema compatibility.

Needed: at least one real MCP client/stdio contract test path.

### They Test Setup Output, Not Setup Trust

Setup tests cover broad file generation, but not enough of the real danger:

- weak-only target selection
- wizard selections
- Codex accidentally becoming generic
- repeated setup over active `.haxaml`
- broad force replacing state
- malformed existing configs
- provider-specific skill snapshot correctness

Needed: setup fixture matrix and golden snapshots.

### They Test Verification As A Claim, Not Evidence

Verification can pass based on agent-supplied summaries and checked-file lists. Tests do not prove the evidence maps to actual commands, files, changed scope, or done criteria.

Needed: verification-plan tests that compare claimed evidence to actual receipts.

## New Test Shape For 1.0

Think of the current suite as target practice. The 1.0 suite needs scrims.

### State And Archive Tests

- Large `acts.yaml` fixture compacts under a real byte target.
- `completed_tasks` cannot grow forever in hot state.
- Archive append does not rewrite or duplicate unnecessary index data after the archive split lands.
- Corrupt archive index can be detected and rebuilt from history.
- Short context fetch does not hydrate full archive details.
- No `acts.lock`, temp state files, or archive temp files remain in the project after normal operations.
- Multiprocess writers cannot corrupt `acts.yaml`.

### Setup Tests

- Running setup twice over an active project is a no-op unless an explicit repair or reset command is used.
- `--force` cannot wipe FRAME state without a reset-specific flag.
- Weak `AGENTS.md` evidence does not auto-select Codex, OpenCode, or Windsurf.
- Explicit Codex selection writes Codex identity into the manifest and generated skill.
- Generic skill output cannot shadow provider-specific skill output.
- Wizard selections are tested through injected prompt answers.
- Dry-run and apply output show the same planned path list.
- Known TOML and JSON config merges preserve unrelated keys.
- Unknown config shape produces manual action instead of a risky write.

### Lifecycle Tests

- Prebuild with unresolved required questions blocks context pack.
- Prebuild with missing materials blocks build permit.
- Answered questions change readiness deterministically.
- Context pack includes only the blueprint-approved files and receipts.
- Verification fails when changed files exceed planned scope.
- Record fails when verification is missing, failed, stale, or unrelated.
- Restarting the process preserves lifecycle contract state.

### MCP Contract Tests

- Start real `haxaml-mcp` over stdio.
- Verify tool schemas and required parameters.
- Verify compact and full detail modes.
- Verify stable error envelopes.
- Verify resources and resource templates through the client, not private server internals.

### Docs And Release Tests

- README examples should be executable or snapshot-tested.
- Roadmap/checklist assertions should guard the 1.0 blockers.
- Changelog entries should match public behavior, not intended behavior.
- Provider docs claims should link to official sources or be marked guidance-only.

## Immediate Regression Tests Added

This audit added small regression coverage for the immediate state bugs:

- Reading state no longer creates project-local `acts.lock`.
- Size pressure can trigger archiving even when an older project still has `archive_mode: manual`.
- New setup scaffolds default to `archive_mode: on_record`.

These tests are not the full solution. They are guardrails for the first patch.

## Test Policy Before 1.0

Haxaml should not call itself stable until these are true:

- Every critical user complaint has a regression test.
- Every lifecycle stop condition has a failing test before the fix and a passing test after.
- Setup has fixture coverage for every supported provider.
- State/archive tests use byte budgets, not only record counts.
- MCP tests include real transport.
- Test failures explain the governance rule that was broken.

The goal is simple: Haxaml should not just work when the agent behaves. It should catch the agent when the agent behaves badly.
