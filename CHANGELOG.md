# Changelog

## 0.7.2 - 2026-05-14

- Added provider workflow depth for Claude, GitHub Copilot, Cursor, OpenCode, and Junie on top of the `0.7.x` workflow accommodation foundation.
- Renamed the setup registry vocabulary from `surface` to `integration point` where it now describes `0.7.x` setup and workflow behavior.
- Refreshed the `0.7.x` and `v1.0` roadmaps so setup is treated as shipped, workflow accommodation is treated as the remaining `0.7.x` gap, and semantic retrieval stays research-first.
- Added local-first release tooling for build-only GitHub workflows and PyPI publishing through `scripts/publish_pypi.sh`.

## 0.7.1 - 2026-05-14

- Added the `workflow` setup kind, `--with-workflow`, and `haxaml workflow check` for project-scoped workflow accommodation.
- Added manifest-backed workflow planning, managed-file tracking, and workflow-aware doctor coverage.
- Added setup-owned workflow bundles for Claude, Codex, Gemini, Cursor, GitHub Copilot, OpenCode, and Junie.
- Replaced user-facing `sidecar` wording with `adapter file` in setup and adoption output.

## 0.7.0 - 2026-05-12

- Added a new `haxaml/setup/` package with a shared target registry, deterministic planning, target renderers, managed writes, adoption state, and drift-aware doctor output.
- Added `haxaml setup`, `haxaml setup print`, and `haxaml setup doctor` as the setup-owned onboarding integration point for fresh repositories and established-codebase adoption.
- Replaced the old standalone adoption CLI path with setup-driven adoption that preserves native instruction files, writes managed sidecars and pointer blocks, and keeps detailed adoption inventory under `.haxaml/adoption/`.
- Refreshed the `0.7.x` roadmap, README onboarding story, and CLI coverage around setup, adoption, project vs user scope, and setup doctor behavior.

## 0.6.8 - 2026-05-08

- Added `haxaml[full]` convenience extra in the core package.
- Restored `mcp` as a required core `haxaml` dependency because MCP is integral to the base runtime.
- Removed the `haxaml-mcp` console script from the core distribution so MCP launcher wiring stays in the `haxaml-mcp` adapter package.
- Updated CLI guidance for missing MCP runtime to point users to reinstall core `haxaml`.
- Refreshed release bump tooling and docs so root extras stay aligned with adapter package version bumps.
- Refactored dashboard lifecycle-state reads into `haxaml.lifecycle_state` and made `haxaml.mcp` lazy to prevent dashboard imports from requiring MCP app startup internals.

## 0.6.7 - 2026-05-07

- Added a shared in-process runtime snapshot cache so long-lived runtimes reuse canonical FRAME reads, invalidate only changed files, and keep archive indexing shallow until drilldown detail is requested.
- Updated repeated `haxaml_context_pack` behavior to compare against prior session snapshots in runtime memory and return refresh metadata:
  - `refresh_mode`
  - `refresh_summary`
  - `changed_sections`
  - `unchanged_sections`
  - `token_delta`
- Added smaller refresh responses when only part of the governed context changed, plus a repeat-context benchmark profile and cache-focused regression coverage.
- Shipped the first local read-only dashboard behind `haxaml dashboard`, with overview, FRAME, and archive routes designed for humans who need to inspect FRAME without editing it.
- Split packaging cleanly across:
  - `haxaml` for core CLI/governance
  - `haxaml-mcp` for MCP runtime
  - `haxaml-ui` for the dashboard
- Kept `haxaml[ui]` as the convenience install selector while making `haxaml-ui` the actual UI distribution.
- Moved `mcp` out of the core package default dependency set so base installs stay leaner.
- Hardened release tooling by teaching version checks, bump tooling, and publish workflow steps about the separate UI package and prerelease tags.

## 0.6.6 - 2026-05-07

- Replaced summary-style state compaction with tiered acts memory so `acts.yaml` stays small while older runs, sessions, and verifications move losslessly into `.haxaml/archive/acts-history.yaml`.
- Added guided follow-up retrieval through `haxaml_context_fetch`, including retrieval hints from `context_pack` and archive-aware search across governed FRAME memory only.
- Kept durable decisions hot by default and enriched run, session, and verification records with searchable file references, module references, verification links, and keywords.
- Made archive search easier to read in code by switching from jargon-heavy record-loading names to plain-language helpers and comments.
- Hardened the publish workflow by validating release versions under the pinned Python toolchain before build and publish steps run.
- Aligned `haxaml` and `haxaml-mcp` package versions at `0.6.6`.

## 0.6.5 - 2026-05-07

- Shipped the current governed lifecycle, export, resource, and documentation updates as the `0.6.5` release snapshot.
- Aligned `haxaml` and `haxaml-mcp` package versions at `0.6.5`.

## 0.6.4 - 2026-05-07

- Added deterministic 0.6.4 consistency checks and derived progress summaries across validator, reconcile, doctor, health, and prebuild without introducing a new inference layer.
- Tightened lifecycle flow guidance with machine-readable next-step hints while keeping short-mode responses lean and benchmark-safe.
- Standardized release version alignment through the central bump script so `haxaml`, `haxaml-mcp`, and release tags stay in sync.

## 0.6.3 - 2026-05-05

### Changed

- Reduced lifecycle response noise by adding a compact short response for `haxaml_prebuild` and cleaner utility-mode guidance output.
- Tightened repeated `haxaml_context_pack` calls so follow-up refreshes require a contextual reason and reject vague retries.
- Added refresh-reason categories and policy metadata to context-pack responses and repeat-call errors.
- Reused already-loaded FRAME data during context-pack generation to avoid an unnecessary reread in the MCP path.
- Fixed workflow benchmark fixtures so the preferred `prebuild` path completes and expanded workflow profiles actually exercise more calls than the essential profile.
- Aligned `acts.yaml` and `rules.yaml` lifecycle phase enums with the current governed flow by adding `prebuild` and `context`.
- Aligned `haxaml` and `haxaml-mcp` package versions at `0.6.3`.

## 0.6.2 - 2026-05-05

### Changed

- Unified the public governed lifecycle story around `about -> guidance -> prebuild -> context_pack -> verify -> record -> expect_sync`.
- Repositioned `haxaml_session_start` and `haxaml_session_plan` as advanced/manual tools across README, learning docs, CLI help text, and MCP reference docs.
- Updated validation guidance, about payload workflow metadata, and benchmark workflow profiles to use the recommended `prebuild` path.
- Updated compatibility wrapper deprecation metadata to target `0.7.0` instead of an already-past release.
- Aligned `haxaml` and `haxaml-mcp` package versions at `0.6.2`.

## 0.6.1 - 2026-05-02

### Changed

- Fixed version alignment so runtime metadata, package metadata, and MCP launcher metadata stay in sync.
- Added centralized version helpers in `haxaml/versioning.py`.
- Added `scripts/bump_version.py` to keep `haxaml` and `haxaml-mcp` bumps consistent.
- Updated release checks and tests around package/version consistency.

## 0.6.0 - 2026-05-02

### Added

- New `FrameModel` loader and normalized in-memory representation for FRAME files.
- New semantic validation layer on top of schema validation.
- New MCP tool: `haxaml_prebuild` for task classification, readiness checks, and governed session preparation.
- New prebuild templates for task typing, risk heuristics, context policy, and done-criteria guidance.
- New `PromptRecipe` export pipeline for deterministic agent export rendering.
- New learning docs for MCP and prebuild flow in `learn/`.

### Changed

- Recommended governed lifecycle now uses `about -> guidance -> prebuild -> context_pack -> verify -> record -> expect_sync`.
- `haxaml_prebuild` replaces the recommended use of `session_start + session_plan` for standard governed flows.
- Export rendering now routes through a normalized recipe instead of ad hoc markdown assembly.
- Validation and readiness checks now use the same semantic FRAME quality signals.

## 0.5.2 - 2026-05-01

### Added

- Deterministic lifecycle contract state in `acts.yaml` (`lifecycle_contract`) for governed MCP flow sequencing.
- New validation failure gate: `error.code="governance_evidence_missing"` when code changes exist without governed lifecycle evidence.
- New plain-language guide: `learn/mcp-architecture-for-haxaml.md`.

### Changed

- Governed lifecycle flow is now hard-ordered:
  `about -> guidance -> session_start -> session_plan -> context_pack -> session_verify -> session_record -> expect_sync`.
- Out-of-order governed lifecycle calls now fail with `error.code="lifecycle_contract_violation"`.
- `haxaml_context_pack`, `haxaml_session_verify`, and `haxaml_session_record` now require `session_id` for governed execution.
- `haxaml_run` compatibility wrapper now executes guidance/start/plan/context-pack to stay compliant with strict lifecycle order.
- `haxaml_done` wrapper now resolves and uses governed session context for verify/record compatibility.
- Added lifecycle policy flag `rules.lifecycle.enforce_governed_evidence_on_validate` (default `true` in scaffolded rules).
- Aligned `haxaml` and `haxaml-mcp` package versions at `0.5.2`.

## 0.5.1 - 2026-04-30

### Added

- New lifecycle tool: `haxaml_expect_sync` for deterministic acts -> expect runbook synchronization.
- New `acts.yaml` lifecycle marker: `expect_sync` state (`required`, pending run metadata, last sync metadata).

### Changed

- `haxaml_session_record` now marks expect sync as required after every recorded result and blocks the next record until synced.
- `haxaml_session_start` now warns (but allows start) when expect sync is pending from a previous record.
- `haxaml_validate` now fails with `error.code="lifecycle_drift"` when expect sync is pending.
- `haxaml_needs` now reports blocking lifecycle sync requirements when expect is out of date.
- Workflow metadata and docs now include `haxaml_expect_sync` after `haxaml_session_record`.
- Aligned `haxaml` and `haxaml-mcp` package versions at `0.5.1`.

## 0.5.0 - 2026-04-29

### Changed

- Repositioned the public docs around Haxaml as an MCP-first governance project.
- Simplified the public README into a lean OSS entrypoint with an MCP-centered bootstrap prompt.
- Moved the public deep-dive guide to `learn/haxaml.md`.
- Removed non-public scratch, research, generated build, and legacy documentation artifacts from the public repo surface.
- Aligned `haxaml` and `haxaml-mcp` package versions at `0.5.0`.

## 0.4.5 - 2026-04-28

### Added

- Optional `detail` mode across MCP tools: `short` (default) and `full`.
- `invalid_detail` error for unsupported detail values.
- `standard` context-pack alias, normalized to `balanced`.
- Context-pack metadata for compaction visibility:
  - `included_sections`
  - `omitted_sections`
  - `omitted_context`
  - `requested_pack`
  - `resolved_pack`

### Changed

- Success responses are short by default for MCP tools, while failures keep rich error details.
- `haxaml_context_pack` short mode now returns context text plus compact metadata (without full duplicated structured payload).
- `haxaml_context` short mode now avoids duplicating full context payload fields.
- CLI `context-pack --pack` now accepts `standard`.
- `rules.schema` now allows `context_policy.default_pack: standard`.
- `haxaml` and `haxaml-mcp` versions are aligned at `0.4.5`.

### Notes

- `0.4.3` and `0.4.4` were internal roadmap milestones and were not published as tagged releases.
- Official tagged releases moved from `v0.4.2` directly to `v0.4.5`.

## 0.4.2 - 2026-04-28

### Added

- `haxaml_adopt_plan` now returns structured `instruction_analysis` metadata:
  - `conflicts` (warning-level, metadata-first)
  - `duplicates`
  - `precedence_decision_required`
  - `precedence_candidates`
  - deterministic analysis counts
- README agent-section scanning for adoption analysis (agent/instruction sections only).
- Top-level MCP `warnings` for adopt-plan conflict/duplicate awareness, with full structure kept in `data`.
- PyPI publish workflow guardrail that hard-fails when:
  - tag version does not match package versions
  - `haxaml` and `haxaml-mcp` versions are out of sync
  - `haxaml-mcp` dependency floor is not aligned with the tag version

### Changed

- Expanded native rule-directory detection for adoption:
  - `.cursor/rules/*`
  - `.windsurf/rules/*`
- Adoption report now includes compact instruction-analysis summaries.
- `haxaml` and `haxaml-mcp` versions are aligned at `0.4.2`.

### Notes

- No automatic precedence winner is selected when instruction conflicts are detected.
- Adoption analysis remains non-destructive and compact (no raw content snippets).

## 0.4.0 - 2026-04-28

### Added

- `haxaml_adopt_plan(project_dir='.')` for non-destructive adoption inventory and migration planning.
- `haxaml_reconcile(project_dir='.')` for deterministic derivation-boundary conflict reports.
- Structured reconcile metrics: `conflict_counts`, `warning_counts`, `severity_totals`, `gate_reasons`, `human_summary`.
- CLI mirrors for new MCP tools: `haxaml adopt-plan` and `haxaml reconcile`.

### Changed

- Derivation boundaries are map-canonical when `map.yaml` exists.
- If map is absent and optional by policy, map-canonical checks are deferred.
- `haxaml_validate` now includes reconcile checks and fails on blocking conflicts (`error.code=derivation_conflicts`).
- `haxaml_session_record` now blocks `success`/`partial` when blocking conflicts are unresolved.
- `haxaml_session_record` permits `failed` with conflicts only when conflict stop reason is explicitly recorded.
- `haxaml_adopt` dry-run payload now includes structured adoption plan data.

### Deprecated (still available in 0.4.x)

- `haxaml_run` (use `haxaml_session_start`)
- `haxaml_done` (use `haxaml_session_verify` + `haxaml_session_record`)
- `haxaml_context` (use `haxaml_context_pack`)

Wrappers now include stronger deprecation metadata and warnings.

### Migration Notes

Recommended sequence for existing projects:

1. `haxaml_adopt_plan`
2. `haxaml_reconcile`
3. resolve blocking conflicts
4. `haxaml_validate`
5. lifecycle tools and exports
