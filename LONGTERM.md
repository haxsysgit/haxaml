# Haxaml Long-Term Plan

## Positioning

Haxaml is git-style governance for AI agent sessions.
It is a structured journal, context engine, and guidance layer.

MCP first.
CLI second.

## 0.3 line (current major pass)

- add MCP-first lifecycle tools: guidance/start/plan/context-pack/verify/record
- keep FRAME five-file model canonical
- enforce verify-before-record gate for success/partial runs
- add reflective evidence in `acts.verifications`
- add context compaction and onboarding-read policy metadata

## 0.4 line

- improve derivation boundaries between facts/rules/acts/expect/map
- stronger module-impact checks in verify phase
- richer task-type and safer-path guidance policies
- better migration helpers for existing projects

## 0.5 line

- multi-repo and larger-project session scaling
- stronger map policy links to verify checks
- improved context-pack retrieval heuristics and deterministic budgets

## 1.0 target

- freeze MCP tool envelope and lifecycle contract
- remove legacy compatibility wrappers that are still deprecated
- publish stable migration guide from pre-1.0 flows

## Core invariants

- one version source of truth: package metadata
- no hidden LLM synthesis inside Haxaml engine
- FRAME content is authored by user/agent; Haxaml validates, structures, and tracks
- deterministic behavior from input FRAME + tool arguments
