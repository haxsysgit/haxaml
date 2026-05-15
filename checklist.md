# Haxaml Checklist

This file replaces the old scratch planning notes. It is the working checklist for what Haxaml still needs, plus a reality check on what the project already does today.

Status legend:

- `[x]` shipped or materially true today
- `[~]` partially true, but not product-complete
- `[ ]` still missing

## Reality Check

Haxaml today is strongest at:

- governed task entry through `about`, `guidance`, and `prebuild`
- FRAME normalization and semantic validation
- context discipline through scoped packs, follow-up retrieval, and refresh deltas
- governed history through acts archive + retrieval
- packaging separation across core, MCP, and dashboard

Haxaml today is still weak at:

- automated onboarding and setup
- first-party Skill/adapters as a complete product surface
- explicit outcome tracking and decision gates
- drift enforcement beyond the current validation and verification boundaries
- turning the dashboard into a broader inspection experience without adding mutation risk

## Product Positioning

- [x] Haxaml should be presented as prebuild and governance for AI coding agents.
  Reality: README and roadmap now reflect this clearly.
- [~] Package metadata and every public surface should speak the same positioning language.
  Reality: core package description is aligned; some deeper docs and examples still need continued cleanup over time.
- [ ] GitHub About, screenshots, examples, and release copy should fully reinforce the same product story.
  Reality: this is repo/publishing hygiene work, not a core-runtime blocker.

## Core Governance Engine

- [x] `haxaml_prebuild` should be the flagship tool.
  Reality: this is already the recommended governed entry point.
- [x] FRAME should be normalized into one reusable internal model.
  Reality: `FrameModel` is already shared by validation and lifecycle paths.
- [x] Validation should go beyond YAML shape checks.
  Reality: semantic validation, reconcile, doctor, health, and prebuild already do this.
- [~] “No evidence, no done” should be a hard product boundary everywhere.
  Reality: verification/recording are much stricter than before, but there is still room to harden enforcement further.
- [ ] Done checks should exist as a dedicated surface before record.
  Reality: still planned work.

## Context Discipline And Long-Lived Runtime Efficiency

- [x] Repeated FRAME reads should avoid rereading unchanged files.
  Reality: shared runtime snapshot cache shipped in `0.6.7`.
- [x] Repeated `context_pack` calls should return refresh deltas, not blind full packs.
  Reality: refresh metadata and changed-section deltas shipped in `0.6.7`.
- [x] Archive overview should stay shallow until drilldown.
  Reality: runtime cache separates archive index reads from full record hydration.
- [~] Context budget should be explicit and measurable, not only implied by pack choices.
  Reality: pack discipline exists, but budget planning is not yet first-class.
- [ ] Impact preview should be a clearer standalone operator surface.
  Reality: still planned work.

## MCP, CLI, And UI Separation

- [x] Core, MCP runtime, and dashboard should be separated operationally.
  Reality: `haxaml`, `haxaml-mcp`, and `haxaml-ui` are now distinct packages.
- [x] `haxaml[ui]` should remain a convenience install path, not a separate package name.
  Reality: shipped that way.
- [x] Dashboard launch should be `haxaml dashboard`.
  Reality: shipped that way.
- [~] Runtime/module boundaries should keep overhead low as the dashboard grows.
  Reality: packaging is separated; continued code-level discipline is still required.

## Dashboard

- [x] First dashboard must be local, browser-based, read-only, and overview-first.
  Reality: shipped in `0.6.7`.
- [x] All five FRAME files should render.
  Reality: facts/rules/acts/expect/map pages exist.
- [x] Archive should support shallow overview plus detail drilldown.
  Reality: shipped.
- [ ] Dashboard editing should remain out of scope until the governed write model is designed properly.
  Reality: no editing exists today, which is correct.
- [~] Dashboard should become a stronger inspection surface without turning into a second product.
  Reality: the current UI is intentionally thin and still needs iteration.

## Setup, Skill, And Adapters

- [x] `haxaml setup` should become the one-step onboarding path.
  Reality: shipped in `0.7.4` with interactive TTY flow plus non-interactive and JSON-safe modes.
- [x] Haxaml should ship a canonical built-in Skill.
  Reality: shipped in `0.7.4` with provider-aware `SKILL.md` generation and valid YAML frontmatter.
- [x] Target-specific adapters should be generated from one source recipe.
  Reality: setup now renders instructions, skills, agents, config, and workflow assets from one managed planner/renderer stack.
- [x] Setup should support project scope, safe user-scope guidance, dry-run mode, and doctor output.
  Reality: shipped, including preview-first dry runs and drift/missing-file audits.
- [x] Installed Skill/adapters should be version-aware and drift-checkable.
  Reality: shipped through setup manifest tracking, recipe hashes, pointer blocks, and setup doctor.

## Outcome Tracking, Drift, And Cross-Project Learning

- [ ] Outcome-first tracking should connect goals, KPIs, evidence, and decision gates.
  Reality: not modeled directly yet.
- [~] Drift detection should compare work against facts/rules more aggressively.
  Reality: some deterministic checks exist, but full rule-aware drift blocking is not complete.
- [ ] Cross-project pattern inheritance should be approached carefully, only after core single-project governance is stable.
  Reality: still a future research area, not current roadmap-critical work.

## Release And Repo Hygiene

- [x] Package versions should stay aligned across core, MCP, and UI.
  Reality: enforced by version helpers and tested.
- [x] Publish workflows should understand the three-package split.
  Reality: shipped.
- [x] Scratch planning files should be consolidated into maintainable repo docs.
  Reality: this checklist and `v1.0_Roadmap.md` now replace the older loose notes.
- [~] Docs should keep catching up with the product direction as setup and Skill work land.
  Reality: this is continuous work, not a one-time cleanup.
