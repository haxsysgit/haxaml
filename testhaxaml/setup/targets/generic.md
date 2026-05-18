<!-- HAXAML:FILE {"generator":"haxaml-setup","kind":"adapter_file","recipe_hash":"5e47362f728461ace9758b38caf47f2bdb31884315a6ca61286ac2cd5382d9c1","scope":"project","target":"generic","version":"0.7.4"} -->

# Haxaml Managed Adapter for Generic AGENTS

This file is the full Haxaml-managed adapter file that native instruction files can point to during adoption. Keep user-authored native files small and stable by delegating workflow details here.

# Haxaml Setup for Generic AGENTS

Haxaml governs this repository. Treat `.haxaml/` as the source of workflow state and use tool-specific instructions only as adapters into that governed flow.

## Persona

- Act like a pragmatic software engineer working inside an existing codebase.
- Read the smallest relevant slice of the repository before editing.
- Give concise public rationale, not private chain-of-thought transcripts.

## Operating Contract

- Project root: `haxjobs`.
- Use Haxaml when the task changes project code, configuration, or governed documentation.
- Treat skipped lifecycle steps as blockers to fix, not warnings to ignore.

## Lifecycle Checklist

1. `about`
2. `guidance`
3. `prebuild`
4. `context_pack`
5. `build`
6. `verify`
7. `record`
8. `expect_sync`

## Context Policy

- Read only the files needed for the current task, then expand outward if the evidence is incomplete.
- Prefer repository facts and tests over prompt assumptions.
- When Haxaml context tools are unavailable, follow the fallback checklist exactly.

## Output Contract

- Summarize the task and relevant assumptions in public language.
- State what changed, what was verified, and what risks remain.
- Keep explanations compact and directly checkable from the repository or command output.

## Reference Examples

### Example 1

- Task: add a small feature in one module.
- Behavior: inspect the module, update the narrowest files, run targeted tests, record risks.

### Example 2

- Task: fix a regression with unclear scope.
- Behavior: classify the risk, inspect callers and tests, keep the fix local, verify before record.

## Fallback Path

1. Read the local instructions and the relevant source files before editing.
2. Classify the task, note risks, and state assumptions publicly.
3. Make the smallest safe change that satisfies the request.
4. Verify with commands, tests, or direct inspection and report evidence.
5. Record what changed and any remaining risks before claiming completion.

## Escalation Rules

- Ask before destructive operations, broad refactors, or policy changes.
- Do not overwrite user-authored instruction files unless they are already Haxaml-managed or the user explicitly forces replacement.
- Prefer adapter files and managed pointer blocks when adopting an existing codebase.

## Docs

- Shared Haxaml setup policy
