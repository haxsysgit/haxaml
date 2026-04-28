# Changelog

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
