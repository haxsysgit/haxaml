# Changelog

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
