"""MCP frame tools for Haxaml."""

from haxaml.mcp.base import *


@mcp_app.tool()
def haxaml_init(directory: str = ".", detail: str = DETAIL_SHORT) -> dict:
    """Initialize FRAME governance files in a project directory.

    Creates .haxaml/ with template facts.yaml, rules.yaml, acts.yaml,
    and expect.yaml. The AI agent should fill these in before building.
    """
    detail_mode, detail_err = _normalize_detail("haxaml_init", detail)
    if detail_err:
        return detail_err

    project_dir = Path(directory).resolve()
    project_dir.mkdir(parents=True, exist_ok=True)
    haxaml_root = frame_dir(project_dir)
    haxaml_root.mkdir(parents=True, exist_ok=True)
    created = write_missing_frame_files(project_dir)
    created_rel = [path.relative_to(project_dir).as_posix() for path in created]

    if not created:
        message = (
            f"⚠ FRAME scaffold already exists at {haxaml_root}\n"
            "  → haxaml_init only creates missing core FRAME files\n"
            "  → Run `haxaml setup` or call `haxaml_setup` for onboarding or adoption"
        )
        return _ok(
            "haxaml_init",
            {
                "message": message,
                "project_dir": str(project_dir),
                "created": False,
                "created_files": [],
            },
            detail=detail_mode,
        )

    message = (
        f"✓ Initialized FRAME scaffold at {haxaml_root}\n"
        f"  → .haxaml/facts.yaml — FRAME frontmatter for project truth\n"
        f"  → .haxaml/rules.yaml — FRAME frontmatter for constraints\n"
        f"  → .haxaml/acts.yaml — FRAME frontmatter for activity records\n"
        f"  → .haxaml/expect.yaml — FRAME frontmatter for planned direction\n"
        f"  → Only frontmatter is valid in 0.8.0 until future schema slices add more fields\n"
        f"  → Run `haxaml setup` or call `haxaml_setup` for onboarding or adoption\n"
        f"  → Call haxaml_validate when ready"
    )
    return _ok(
        "haxaml_init",
        {
            "message": message,
            "project_dir": str(project_dir),
            "created": True,
            "created_files": created_rel,
        },
        detail=detail_mode,
    )


@mcp_app.tool()
def haxaml_validate(project_dir: str = ".", detail: str = DETAIL_SHORT) -> dict:
    """Validate all FRAME files against schemas.

    Checks facts.yaml, rules.yaml, acts.yaml, expect.yaml, and map.yaml.
    Returns validation results for each file.
    """
    detail_mode, detail_err = _normalize_detail("haxaml_validate", detail)
    if detail_err:
        return detail_err

    p = Path(project_dir).resolve()
    lines = []
    all_valid = True
    facts_blob = {}
    rules_blob = {}

    checks = [
        ("facts.yaml", validate_facts),
        ("rules.yaml", validate_rules),
        ("acts.yaml", validate_acts),
    ]

    for new_name, validator_fn in checks:
        path = resolve_frame_file(p, new_name)
        if path:
            errors = validator_fn(str(path))
            if errors:
                lines.append(f"✗ {new_name}: {len(errors)} error(s)")
                for e in errors:
                    lines.append(f"  → {e}")
                all_valid = False
            else:
                lines.append(f"✓ {new_name} is valid")
                if new_name == "facts.yaml":
                    facts_blob = load_yaml(str(path))
                if new_name == "rules.yaml":
                    rules_blob = load_yaml(str(path))
        else:
            if new_name == "facts.yaml":
                lines.append(f"✗ {new_name} not found")
                all_valid = False
            else:
                lines.append(f"⚠ {new_name} not found (optional)")
    acts_path = resolve_frame_file(p, "acts.yaml")
    if acts_path:
        acts = load_yaml(str(acts_path))
        sync_state = _expect_sync_state(acts)
        if sync_state["required"]:
            lines.append("✗ lifecycle drift: expect sync is required before validation can pass")
            lines.append("  → fix: call haxaml_expect_sync(project_dir='.')")
            all_valid = False

    lifecycle_rules = _rules_policy(rules_blob if isinstance(rules_blob, dict) else {}, "lifecycle", {})
    enforce_governed_evidence = bool(lifecycle_rules.get("enforce_governed_evidence_on_validate", True))
    governed_changed = _governed_code_changes(project_dir)
    if enforce_governed_evidence and governed_changed and acts_path:
        acts = load_yaml(str(acts_path))
        has_evidence = _has_governed_evidence_for_changes(acts, governed_changed)
        if not has_evidence:
            lines.append("✗ governance evidence missing: code changes exist without governed lifecycle evidence")
            lines.append("  → fix: run governed flow (about -> guidance -> prebuild -> context_pack -> verify -> record -> expect_sync)")
            all_valid = False

    expect_path = resolve_frame_file(p, "expect.yaml")
    if expect_path:
        errors = validate_expect(str(expect_path))
        if errors:
            lines.append(f"✗ expect.yaml: {len(errors)} error(s)")
            for e in errors:
                lines.append(f"  → {e}")
            all_valid = False
        else:
            lines.append("✓ expect.yaml is valid")

    map_path = resolve_frame_file(p, "map.yaml")
    if map_path:
        errors = validate_map(str(map_path))
        if errors:
            lines.append(f"✗ map.yaml: {len(errors)} error(s)")
            for e in errors:
                lines.append(f"  → {e}")
            all_valid = False
        else:
            lines.append("✓ map.yaml is valid")

    assessment = evaluate_map_complexity(p)
    map_errors, map_warnings = map_complexity_issues(assessment)
    lines.append(f"• Map complexity: {format_map_complexity_summary(assessment)}")
    if map_errors:
        for err in map_errors:
            lines.append(f"✗ map policy: {err}")
        if assessment.reasons:
            for reason in assessment.reasons:
                lines.append(f"  → complexity signal: {reason}")
        all_valid = False
    if map_warnings:
        for warning in map_warnings:
            lines.append(f"⚠ map policy: {warning}")

    reconcile = reconcile_derivation(p)
    lines.append(f"• Reconcile: {reconcile['human_summary']}")
    for conflict in reconcile["conflicts"]:
        marker = "✗" if conflict["severity"] == "blocking" else "⚠"
        lines.append(f"{marker} reconcile[{conflict['id']}]: {conflict['message']}")
        lines.append(f"  → fix: {conflict['suggested_fix_action']}")
    if reconcile["severity_totals"]["blocking"] > 0:
        all_valid = False

    sem = semantic_validate(FrameModel.load(project_dir))
    if sem.blocking:
        lines.append(f"\n✗ {len(sem.blocking)} semantic error(s):")
        for b in sem.blocking:
            lines.append(f"  → {b}")
        all_valid = False
    if sem.warnings:
        lines.append(f"\n⚠ {len(sem.warnings)} semantic warning(s) (see haxaml_doctor for details)")

    if all_valid:
        lines.append("\n✓ All FRAME files valid")
    else:
        lines.append("\n✗ Validation failed — fix errors above")
    message = "\n".join(lines)
    if all_valid:
        _retry_guard_clear(project_dir, tool="haxaml_validate")
        return _ok(
            "haxaml_validate",
            {
                "message": message,
                "valid": True,
                "reconcile": reconcile,
            },
            detail=detail_mode,
        )
    if acts_path:
        acts = load_yaml(str(acts_path))
        sync_state = _expect_sync_state(acts)
        if sync_state["required"]:
            return _gate_error_with_retry_policy(
                "haxaml_validate",
                "lifecycle_drift",
                "FRAME lifecycle drift detected: expect.yaml has not been synced after the latest session record.",
                project_dir=project_dir,
                details={
                    "message": message,
                    "pending_sync": sync_state,
                    "retry_after": ["haxaml_expect_sync(project_dir='.')", "haxaml_validate(project_dir='.')"],
                },
            )
        lifecycle_rules = _rules_policy(rules_blob if isinstance(rules_blob, dict) else {}, "lifecycle", {})
        enforce_governed_evidence = bool(lifecycle_rules.get("enforce_governed_evidence_on_validate", True))
        governed_changed = _governed_code_changes(project_dir)
        if enforce_governed_evidence and governed_changed:
            has_evidence = _has_governed_evidence_for_changes(acts, governed_changed)
            if not has_evidence:
                return _gate_error_with_retry_policy(
                    "haxaml_validate",
                    "governance_evidence_missing",
                    "Code changes were detected but no governed lifecycle evidence was found.",
                    project_dir=project_dir,
                    details={
                        "message": message,
                        "changed_files": governed_changed,
                        "retry_after": [
                            "haxaml_about(project_dir='.')",
                            "haxaml_guidance(task=..., project_dir='.')",
                            "haxaml_prebuild(task=..., description=..., project_dir='.')",
                            "haxaml_context_pack(task=..., session_id=..., project_dir='.')",
                            "haxaml_session_verify(task=..., session_id=..., project_dir='.')",
                            "haxaml_session_record(task=..., session_id=..., result='success'|'partial'|'failed', project_dir='.')",
                            "haxaml_expect_sync(project_dir='.')",
                            "haxaml_validate(project_dir='.')",
                        ],
                    },
                )
    error_code = "derivation_conflicts" if reconcile["severity_totals"]["blocking"] > 0 else "validation_failed"
    return _gate_error_with_retry_policy(
        "haxaml_validate",
        error_code,
        "FRAME validation failed.",
        project_dir=project_dir,
        details={
            "message": message,
            "reconcile": reconcile,
        },
    )


@mcp_app.tool()
def haxaml_health(project_dir: str = ".", detail: str = DETAIL_SHORT) -> dict:
    """Get project health report.

    Shows validation status, state summary, token count, errors and warnings.
    """
    detail_mode, detail_err = _normalize_detail("haxaml_health", detail)
    if detail_err:
        return detail_err

    try:
        runner = ExecutionRunner(project_dir)
    except FileNotFoundError as e:
        return _err("haxaml_health", "missing_frame", str(e))

    frame = FrameModel.load(project_dir)
    report = runner.get_project_health()
    sem = semantic_validate(frame)
    consistency = frame_consistency_report(frame)
    reconcile = reconcile_derivation(project_dir)
    project_name = str(report.get("project", "")).strip() or "(unnamed)"
    health_errors = list(report.get("errors", []))
    health_warnings = list(report.get("warnings", []))

    def _append_unique(items: list[str], extra: list[str]) -> None:
        for item in extra:
            if item not in items:
                items.append(item)

    _append_unique(health_errors, list(sem.blocking))
    consistency_messages = [finding["message"] for finding in consistency["findings"]]
    _append_unique(health_warnings, [warning for warning in sem.warnings if warning not in consistency_messages])
    _append_unique(health_warnings, consistency_messages)

    sync_state = _expect_sync_state(frame.acts or {})
    if sync_state["required"]:
        _append_unique(
            health_errors,
            [
                "Lifecycle drift: expect.yaml sync is pending "
                f"for run '{sync_state['pending_run_id'] or 'unknown'}'."
            ],
        )

    rules_blob = frame.rules or {}
    lifecycle_rules = _rules_policy(rules_blob, "lifecycle", {})
    enforce_governed_evidence = bool(lifecycle_rules.get("enforce_governed_evidence_on_validate", True))
    governed_changed = _governed_code_changes(project_dir)
    if enforce_governed_evidence and governed_changed and not _has_governed_evidence_for_changes(frame.acts or {}, governed_changed):
        _append_unique(
            health_errors,
            [
                "Governance evidence missing: code changes exist without matching governed lifecycle evidence."
            ],
        )

    blocking_conflicts = [item["message"] for item in reconcile["conflicts"] if item["severity"] == "blocking"]
    warning_conflicts = [item["message"] for item in reconcile["conflicts"] if item["severity"] == "warning"]
    _append_unique(health_errors, [f"Reconcile: {message}" for message in blocking_conflicts])
    _append_unique(health_warnings, [f"Reconcile: {message}" for message in warning_conflicts])

    report["errors"] = health_errors
    report["warnings"] = health_warnings
    report["ready"] = not health_errors
    report["progress_summary"] = consistency
    report["reconcile"] = reconcile
    lines = [
        f"Project:    {project_name}",
        f"Ready:      {'✓' if report['ready'] else '✗'}",
        f"Facts:      {'✓ valid' if report['facts_valid'] else '✗ invalid'}",
        f"Acts:       {'✓ valid' if report['acts_valid'] else '✗ invalid'}",
        f"Complete:   {'✓' if report['facts_complete'] else '✗ incomplete'}",
        f"Context:    {report['context_tokens']} tokens",
        f"Derived:    {consistency['status']} — {consistency['reason']}",
    ]

    p = Path(project_dir).resolve()
    rules_path = resolve_frame_file(p, "rules.yaml")
    rules_errors = validate_rules(str(rules_path)) if rules_path else []
    expect_path = resolve_frame_file(p, "expect.yaml")
    expect_errors = validate_expect(str(expect_path)) if expect_path else []
    map_path = resolve_frame_file(p, "map.yaml")
    map_schema_errors = validate_map(str(map_path)) if map_path else []

    map_assessment = evaluate_map_complexity(p)
    map_errors, map_warnings = map_complexity_issues(map_assessment)
    if detail_mode == "full" or rules_errors:
        lines.append(f"Rules:      {'✓ valid' if not rules_errors else '✗ invalid'}")
    if detail_mode == "full" or expect_errors:
        lines.append(f"Expect:     {'✓ valid' if not expect_errors else '✗ invalid'}")
    if map_path and (detail_mode == "full" or map_schema_errors):
        lines.append(f"Map:        {'✓ valid' if not map_schema_errors else '✗ invalid'}")
    if detail_mode == "full" or map_errors or map_warnings:
        lines.append(f"Map policy: {format_map_complexity_summary(map_assessment)}")
    if detail_mode == "full" and map_assessment.reasons:
        lines.append("Map signals:")
        for reason in map_assessment.reasons:
            lines.append(f"  → {reason}")
    for err in map_errors:
        lines.append(f"  ✗ {err}")
    for warning in map_warnings:
        lines.append(f"  ⚠ {warning}")

    lines.append(f"Reconcile:  {reconcile['human_summary']}")

    if report.get("phase"):
        lines.extend([
            f"Phase:      {report['phase']}",
            f"Active:     {report['active_task']}",
            f"Completed:  {report['completed_tasks']}",
            f"Blocked:    {report['blocked_tasks']}",
            f"Total runs: {report['total_runs']}",
        ])
    if consistency.get("open_session_count") is not None:
        lines.append(f"Open sess:  {consistency['open_session_count']}")
    if consistency.get("active_run") is not None:
        lines.append(f"Active run: {consistency['active_run']}")

    if report["errors"]:
        lines.append(f"\n✗ {len(report['errors'])} error(s):")
        for e in report["errors"]:
            lines.append(f"  → {e}")

    if report["warnings"]:
        lines.append(f"\n⚠ {len(report['warnings'])} warning(s):")
        for w in report["warnings"]:
            lines.append(f"  → {w}")

    message = "\n".join(lines)
    if report["ready"]:
        return _ok("haxaml_health", {"message": message, "report": report}, detail=detail_mode)
    return _err("haxaml_health", "not_ready", "Project health has errors.", {"message": message, "report": report})


@mcp_app.tool()
def haxaml_doctor(project_dir: str = ".", detail: str = DETAIL_SHORT) -> dict:
    """Check facts completeness beyond schema validation.

    Finds missing recommended fields, blocking unresolved items, and semantic
    quality gaps across all FRAME files.
    """
    detail_mode, detail_err = _normalize_detail("haxaml_doctor", detail)
    if detail_err:
        return detail_err

    p = Path(project_dir).resolve()
    facts_path = resolve_frame_file(p, "facts.yaml")
    if not facts_path:
        return _err("haxaml_doctor", "missing_facts", "facts.yaml not found")

    errors = validate_facts(str(facts_path))
    if errors:
        lines = ["✗ facts.yaml fails schema validation — fix these first:"]
        for e in errors:
            lines.append(f"  → {e}")
        return _err(
            "haxaml_doctor",
            "invalid_facts_schema",
            "facts.yaml fails schema validation.",
            {"message": "\n".join(lines), "errors": errors},
        )

    lines: list[str] = []
    all_recommendations: list[str] = []
    frame = FrameModel.load(project_dir)
    consistency = frame_consistency_report(frame)
    reconcile = reconcile_derivation(project_dir)

    lines.append(
        f"Derived progress: {consistency['status']} — {consistency['reason']}"
    )

    missing = detect_missing_facts_fields(str(facts_path))
    if missing:
        lines.append(f"⚠ {len(missing)} facts field recommendation(s):")
        for m in missing:
            lines.append(f"  → {m}")
            all_recommendations.append(m)

    sem = semantic_validate(frame)
    consistency_messages = {finding["message"] for finding in consistency["findings"]}
    if sem.blocking:
        lines.append(f"✗ {len(sem.blocking)} blocking semantic issue(s):")
        for b in sem.blocking:
            lines.append(f"  → {b}")
    general_sem_warnings = [warning for warning in sem.warnings if warning not in consistency_messages]
    if general_sem_warnings:
        lines.append(f"⚠ {len(general_sem_warnings)} semantic quality warning(s):")
        for w in general_sem_warnings:
            lines.append(f"  → {w}")
            all_recommendations.append(w)

    if consistency["findings"]:
        lines.append(f"⚠ {len(consistency['findings'])} consistency advisory finding(s):")
        for finding in consistency["findings"]:
            lines.append(f"  → {finding['message']}")
            if finding["hint"]:
                lines.append(f"    fix: {finding['hint']}")
            all_recommendations.append(finding["message"])

    reconcile_blocking = [item for item in reconcile["conflicts"] if item["severity"] == "blocking"]
    reconcile_warnings = [item for item in reconcile["conflicts"] if item["severity"] == "warning"]
    if reconcile_blocking:
        lines.append(f"✗ {len(reconcile_blocking)} blocking reconcile conflict(s):")
        for conflict in reconcile_blocking:
            lines.append(f"  → {conflict['message']}")
            lines.append(f"    fix: {conflict['suggested_fix_action']}")
    if reconcile_warnings:
        lines.append(f"⚠ {len(reconcile_warnings)} reconcile warning(s):")
        for conflict in reconcile_warnings:
            lines.append(f"  → {conflict['message']}")
            lines.append(f"    fix: {conflict['suggested_fix_action']}")
            all_recommendations.append(conflict["message"])

    has_blocking = bool(sem.blocking or reconcile_blocking)
    has_issues = bool(has_blocking or all_recommendations)
    if not has_issues:
        return _ok(
            "haxaml_doctor",
            {
                "message": "✓ FRAME is complete — no recommendations",
                "has_recommendations": False,
                "progress_summary": consistency,
            },
            detail=detail_mode,
        )

    return _ok(
        "haxaml_doctor",
        {
            "message": "\n".join(lines) if lines else "⚠ Issues found",
            "recommendations": all_recommendations,
            "blocking": [*sem.blocking, *[item["message"] for item in reconcile_blocking]],
            "warnings": [*general_sem_warnings, *[item["message"] for item in consistency["findings"]], *[item["message"] for item in reconcile_warnings]],
            "has_recommendations": bool(all_recommendations),
            "has_blocking": has_blocking,
            "progress_summary": consistency,
            "reconcile": reconcile,
            "consistency_findings": consistency["findings"],
        },
        detail=detail_mode,
    )
