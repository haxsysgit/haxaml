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

    facts_p = frame_path(project_dir, "facts.yaml")
    if facts_p.exists():
        sync_result = sync_rules_governance_version(project_dir)
        sync_message = ""
        if sync_result.get("updated"):
            from_version = sync_result.get("from") or "(empty)"
            to_version = sync_result.get("to", "?")
            sync_message = (
                f"\n  ↻ Synced .haxaml/rules.yaml governance.version "
                f"{from_version} → {to_version}"
            )
        return _ok(
            "haxaml_init",
            {
                "message": (
                    f"⚠ facts.yaml already exists at {facts_p}. Use haxaml_validate to check it."
                    f"{sync_message}"
                ),
                "project_dir": str(project_dir),
                "created": False,
                "rules_version_synced": bool(sync_result.get("updated")),
                "rules_version_sync": sync_result,
            },
            detail=detail_mode,
        )

    write_init_templates(project_dir)

    stale = export_if_stale(str(project_dir), agents=["generic"])
    re_export_msg = ""
    if stale:
        re_export_msg = f"\n  ↻ Auto-exported {len(stale)} agent file(s)"

    message = (
        f"✓ Initialized FRAME at {haxaml_root}\n"
        f"  → .haxaml/facts.yaml — fill in project truth\n"
        f"  → .haxaml/rules.yaml — define agent rules\n"
        f"  → .haxaml/acts.yaml — diary starts here\n"
        f"  → .haxaml/expect.yaml — plan your runs\n"
        f"  → Call haxaml_validate when ready{re_export_msg}"
    )
    return _ok(
        "haxaml_init",
        {
            "message": message,
            "project_dir": str(project_dir),
            "created": True,
            "auto_exported": stale,
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

    checks = [
        ("facts.yaml", "brain.yaml", validate_facts),
        ("rules.yaml", "mind.yaml", validate_rules),
        ("acts.yaml", "state.yaml", validate_acts),
    ]

    for new_name, old_name, validator_fn in checks:
        path = resolve_frame_file(p, new_name, old_name)
        if path:
            errors = validator_fn(str(path))
            if errors:
                lines.append(f"✗ {new_name}: {len(errors)} error(s)")
                for e in errors:
                    lines.append(f"  → {e}")
                all_valid = False
            else:
                lines.append(f"✓ {new_name} is valid")
        else:
            if new_name == "facts.yaml":
                lines.append(f"✗ {new_name} not found")
                all_valid = False
            else:
                lines.append(f"⚠ {new_name} not found (optional)")

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
def haxaml_context(
    project_dir: str = ".",
    include_state: bool = True,
    detail: str = DETAIL_SHORT,
) -> dict:
    """Get the current project context for the AI agent.

    Returns a compact summary of facts, rules, acts, and expect.
    This is what the agent reads to understand the project.
    """
    detail_mode, detail_err = _normalize_detail("haxaml_context", detail)
    if detail_err:
        return detail_err

    frame = load_frame_data(project_dir)
    if not frame.get("facts"):
        return _err("haxaml_context", "missing_facts", "facts.yaml not found")
    rules = frame.get("rules") or {}
    context_policy = _rules_policy(rules, "context_policy", {"default_pack": "balanced"})
    default_pack = str(context_policy.get("default_pack", "balanced"))
    pack_data = build_context_pack(
        project_dir,
        task="General project context",
        pack=default_pack,
        include_state=include_state,
    )
    ctx = "## Project Facts\n\n" + format_context_pack(pack_data)
    tokens = pack_data.get("_meta", {}).get("token_count", count_tokens(ctx))
    message = f"{ctx}\n\n--- Token count: {tokens} ---"
    dep = _wrapper_deprecation("haxaml_context", ["haxaml_context_pack"])
    return _ok(
        "haxaml_context",
        {
            "message": message,
            "context": ctx,
            "tokens": tokens,
            "context_pack": pack_data,
            "include_state": include_state,
            "deprecation": dep,
        },
        warnings=[dep["message"]],
        detail=detail_mode,
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

    report = runner.get_project_health()
    project_name = str(report.get("project", "")).strip() or "(unnamed)"
    lines = [
        f"Project:    {project_name}",
        f"Ready:      {'✓' if report['ready'] else '✗'}",
        f"Facts:      {'✓ valid' if report['facts_valid'] else '✗ invalid'}",
        f"Acts:       {'✓ valid' if report['acts_valid'] else '✗ invalid'}",
        f"Complete:   {'✓' if report['facts_complete'] else '✗ incomplete'}",
        f"Context:    {report['context_tokens']} tokens",
    ]

    p = Path(project_dir).resolve()
    rules_path = resolve_frame_file(p, "rules.yaml", "mind.yaml")
    if rules_path:
        errors = validate_rules(str(rules_path))
        lines.append(f"Rules:      {'✓ valid' if not errors else '✗ invalid'}")

    expect_path = resolve_frame_file(p, "expect.yaml")
    if expect_path:
        errors = validate_expect(str(expect_path))
        lines.append(f"Expect:     {'✓ valid' if not errors else '✗ invalid'}")

    map_path = resolve_frame_file(p, "map.yaml")
    if map_path:
        errors = validate_map(str(map_path))
        lines.append(f"Map:        {'✓ valid' if not errors else '✗ invalid'}")

    map_assessment = evaluate_map_complexity(p)
    map_errors, map_warnings = map_complexity_issues(map_assessment)
    lines.append(f"Map policy: {format_map_complexity_summary(map_assessment)}")
    if map_assessment.reasons:
        lines.append("Map signals:")
        for reason in map_assessment.reasons:
            lines.append(f"  → {reason}")
    for err in map_errors:
        lines.append(f"  ✗ {err}")
    for warning in map_warnings:
        lines.append(f"  ⚠ {warning}")

    if report.get("phase"):
        lines.extend([
            f"Phase:      {report['phase']}",
            f"Active:     {report['active_task']}",
            f"Completed:  {report['completed_tasks']}",
            f"Blocked:    {report['blocked_tasks']}",
            f"Total runs: {report['total_runs']}",
        ])

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

    Finds missing recommended fields and blocking unresolved items.
    """
    detail_mode, detail_err = _normalize_detail("haxaml_doctor", detail)
    if detail_err:
        return detail_err

    p = Path(project_dir).resolve()
    facts_path = resolve_frame_file(p, "facts.yaml", "brain.yaml")
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

    missing = detect_missing_facts_fields(str(facts_path))
    if missing:
        lines = [f"⚠ {len(missing)} recommendation(s):"]
        for m in missing:
            lines.append(f"  → {m}")
        return _ok(
            "haxaml_doctor",
            {"message": "\n".join(lines), "recommendations": missing, "has_recommendations": True},
            detail=detail_mode,
        )

    return _ok(
        "haxaml_doctor",
        {"message": "✓ facts.yaml is complete — no recommendations", "has_recommendations": False},
        detail=detail_mode,
    )
