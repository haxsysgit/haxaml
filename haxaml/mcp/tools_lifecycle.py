"""MCP lifecycle tools for Haxaml."""

from haxaml.mcp.base import *


def _contract_violation(
    tool: str,
    *,
    project_dir: str,
    contract: dict[str, Any],
    reason: str,
    retry_after: Optional[list[str]] = None,
    details: Optional[dict[str, Any]] = None,
) -> dict:
    payload = {
        "project_dir": str(Path(project_dir).resolve()),
        "current_phase": contract.get("phase", "idle"),
        "expected_next": contract.get("required_next", ["haxaml_about"]),
        "active_session_id": contract.get("active_session_id", ""),
        "active_task": contract.get("active_task", ""),
        "retry_after": retry_after or [],
    }
    if details:
        payload.update(details)
    return _err(tool, "lifecycle_contract_violation", reason, payload)


@mcp_app.tool()
def haxaml_about(project_dir: str = ".", detail: str = DETAIL_SHORT) -> dict:
    """Return onboarding context for Haxaml and FRAME. Call once per active agent/MCP session."""
    detail_mode, detail_err = _normalize_detail("haxaml_about", detail)
    if detail_err:
        return detail_err

    payload = _about_payload(project_dir)
    key = _project_key(project_dir)
    _ABOUT_ACK_CACHE.add(key)
    _retry_guard_clear(project_dir, tool="haxaml_session_start", error_code="about_required")

    warnings = []
    sm, _ = _get_state_manager(project_dir)
    if sm:
        state = sm.read()
        about = state.get("about", {})
        if not isinstance(about, dict):
            about = {}
        about["acknowledged_at"] = _now_iso()
        about["prompt_version"] = ABOUT_PROMPT_VERSION
        about["haxaml_version"] = get_version()
        state["about"] = about
        contract = _lifecycle_contract_state(state)
        required_next = contract.get("required_next", ["haxaml_about"])
        if required_next == ["haxaml_about"] or str(contract.get("phase", "idle")) in {"idle", ""}:
            contract = _contract_touch(
                contract,
                phase="about",
                required_next=["haxaml_guidance"],
                tool_name="haxaml_about",
                active_session_id="",
                active_task="",
            )
        else:
            contract = _contract_touch(
                contract,
                phase=str(contract.get("phase", "about") or "about"),
                required_next=list(required_next),
                tool_name="haxaml_about",
                active_session_id=str(contract.get("active_session_id", "") or ""),
                active_task=str(contract.get("active_task", "") or ""),
            )
        _set_lifecycle_contract_state(state, contract)
        err = _persist_state(sm, state)
        if err:
            warnings.append(f"Could not persist about acknowledgment: {err}")
    else:
        warnings.append("acts.yaml not found; using runtime-only about acknowledgment cache.")

    return _ok("haxaml_about", payload, warnings=warnings, detail=detail_mode)


@mcp_app.tool()
def haxaml_guidance(task: str, project_dir: str = ".", detail: str = DETAIL_SHORT) -> dict:
    """Generate structured task guidance and clarification needs for agent execution."""
    detail_mode, detail_err = _normalize_detail("haxaml_guidance", detail)
    if detail_err:
        return detail_err

    frame = load_frame_data(project_dir)
    if not frame.get("facts"):
        return _err("haxaml_guidance", "missing_facts", "facts.yaml not found")

    about_required = _require_about("haxaml_guidance", project_dir)
    if about_required:
        details = ((about_required.get("error") or {}).get("details") or {})
        return _gate_error_with_retry_policy(
            "haxaml_guidance",
            "about_required",
            "Call haxaml_about once per active agent/MCP session before governed lifecycle calls.",
            project_dir=project_dir,
            task=task,
            details=details,
        )

    guidance = _guidance_eval(task, frame)
    if guidance["execution_mode"] == "governed":
        sm, _ = _get_state_manager(project_dir)
        if not sm:
            return _err("haxaml_guidance", "missing_acts", "acts.yaml not found")
        state = sm.read()
        contract = _lifecycle_contract_state(state)
        if not _contract_allows(contract, "haxaml_guidance"):
            return _contract_violation(
                "haxaml_guidance",
                project_dir=project_dir,
                contract=contract,
                reason="Guidance is out of lifecycle order.",
                retry_after=contract.get("required_next", []),
            )
    else:
        sm = None
        state = {}
        contract = {}

    call_budget = _call_budget_for(guidance["task_type"], guidance["risk_level"])
    status = guidance["status"]
    execution_mode = guidance["execution_mode"]
    msg_lines = [
        f"Mode: {execution_mode}",
        f"Task type: {guidance['task_type']}",
        f"Risk: {guidance['risk_level']}",
        f"Status: {status}",
        (
            f"Call budget: target {call_budget['target_calls']} calls "
            f"(max {call_budget['max_calls_without_visibility']} without visibility calls)"
        ),
    ]
    if guidance["mode_reason"]:
        msg_lines.append(f"Mode reason: {guidance['mode_reason']}")
    if guidance["required_questions"]:
        msg_lines.append("Required clarification:")
        msg_lines.extend([f"  - {q}" for q in guidance["required_questions"]])
    if guidance["missing_context"]:
        msg_lines.append("Missing context:")
        msg_lines.extend([f"  - {m}" for m in guidance["missing_context"]])

    payload = {
        "message": "\n".join(msg_lines),
        "execution_mode": execution_mode,
        "mode_reason": guidance["mode_reason"],
        "mode_hints": guidance["mode_hints"],
        "status": status,
        "task_type": guidance["task_type"],
        "risk_level": guidance["risk_level"],
        "missing_context": guidance["missing_context"],
        "assumptions": guidance["assumptions"],
        "required_questions": guidance["required_questions"],
        "suggested_questions": guidance["suggested_questions"],
        "safer_path": guidance["safer_path"],
        "recommended_packs": guidance["recommended_packs"],
        "call_budget": call_budget,
        "visibility_calls_optional": call_budget["optional_visibility_calls"],
        "anti_bloat_policy": {
            "context_pack_limit": "One context_pack per task by default. Repeat only with scope/staleness reason.",
            "visibility_calls": "Optional diagnostics only; use on failure, uncertainty, or pre-final check.",
            "retry_behavior": "If same gate error appears twice, stop retrying and fix root cause.",
        },
    }
    if guidance["execution_mode"] == "governed" and sm:
        updated = _contract_touch(
            contract,
            phase="guidance",
            required_next=["haxaml_prebuild", "haxaml_session_start"],
            tool_name="haxaml_guidance",
            active_session_id="",
            active_task=task,
        )
        _set_lifecycle_contract_state(state, updated)
        err = _persist_state(sm, state)
        if err:
            return _err(
                "haxaml_guidance",
                "state_persist_error",
                "Guidance produced output but contract state could not be persisted.",
                {"persist_error": err},
            )
    return _ok("haxaml_guidance", payload, detail=detail_mode)


@mcp_app.tool()
def haxaml_session_start(
    task: str,
    description: str = "",
    project_dir: str = ".",
    detail: str = DETAIL_SHORT,
) -> dict:
    """Start a governed agent session with guidance and read policy checks."""
    detail_mode, detail_err = _normalize_detail("haxaml_session_start", detail)
    if detail_err:
        return detail_err

    frame = load_frame_data(project_dir)
    if not frame.get("facts"):
        return _err("haxaml_session_start", "missing_facts", "facts.yaml not found")
    about_required = _require_about("haxaml_session_start", project_dir)
    if about_required:
        details = ((about_required.get("error") or {}).get("details") or {})
        return _gate_error_with_retry_policy(
            "haxaml_session_start",
            "about_required",
            "Call haxaml_about once per active agent/MCP session before haxaml_session_start.",
            project_dir=project_dir,
            task=task,
            details=details,
        )

    mode_eval = _utility_mode_eval(task, description)
    if mode_eval["mode"] == "utility":
        return _utility_mode_error("haxaml_session_start", project_dir, task, description)

    sm, _ = _get_state_manager(project_dir)
    if not sm:
        return _err("haxaml_session_start", "missing_acts", "acts.yaml not found")
    state = sm.read()
    contract = _lifecycle_contract_state(state)
    if not _contract_allows(contract, "haxaml_session_start"):
        return _contract_violation(
            "haxaml_session_start",
            project_dir=project_dir,
            contract=contract,
            reason="Session start is out of lifecycle order.",
            retry_after=contract.get("required_next", []),
        )
    guided_task = str(contract.get("active_task", "") or "").strip()
    if guided_task and guided_task != task.strip():
        return _contract_violation(
            "haxaml_session_start",
            project_dir=project_dir,
            contract=contract,
            reason="Session start task does not match the most recent governed guidance task.",
            details={"guided_task": guided_task, "requested_task": task.strip()},
            retry_after=["haxaml_guidance(task='<matching task>', project_dir='.')"],
        )

    try:
        runner = ExecutionRunner(project_dir)
        pre = runner.start_run(task=task, description=description)
        if pre.result == "failed":
            return _err(
                "haxaml_session_start",
                "preflight_failed",
                "Session failed preflight.",
                {"errors": pre.errors},
            )
    except FileNotFoundError as e:
        return _err("haxaml_session_start", "missing_frame", str(e))

    guidance = _guidance_eval(task, frame)
    read_policy = _session_read_policy(frame)
    session_id = f"session-{uuid.uuid4().hex[:10]}"
    now = _now_iso()

    warnings = []
    if sm:
        expect_sync = _expect_sync_state(state)
        if expect_sync["required"]:
            warnings.append(
                "Expect sync is pending from the previous recorded run. "
                "Call haxaml_expect_sync before claiming the next governed completion."
            )
        sessions = state.get("sessions", [])
        if not isinstance(sessions, list):
            sessions = []
        sessions.append(
            {
                "id": session_id,
                "task": task,
                "description": description,
                "execution_mode": "governed",
                "status": "started",
                "phase": "start",
                "risk_level": guidance["risk_level"],
                "guidance_status": guidance["status"],
                "started": now,
                "updated": now,
            }
        )
        state["sessions"] = sessions
        state["active_task"] = {
            "name": task,
            "description": description,
            "started": now,
            "assignee": "agent",
        }
        compaction = state.get("context_compaction", {})
        if not isinstance(compaction, dict):
            compaction = {}
        started = compaction.get("sessions_started", 0)
        if not isinstance(started, int) or started < 0:
            started = 0
        compaction["sessions_started"] = started + 1
        state["context_compaction"] = compaction
        contract = _contract_touch(
            contract,
            phase="start",
            required_next=["haxaml_session_plan"],
            tool_name="haxaml_session_start",
            active_session_id=session_id,
            active_task=task,
        )
        _set_lifecycle_contract_state(state, contract)
        err = _persist_state(sm, state)
        if err:
            warnings.append(f"Could not persist session state: {err}")
    else:
        warnings.append("acts.yaml not found; session was not persisted.")

    payload = {
        "message": (
            f"Session started: {session_id}\n"
            f"Mode: governed\n"
            f"Status: {guidance['status']}\n"
            f"Risk: {guidance['risk_level']}\n"
            f"Required reads: {', '.join(read_policy['required_reads'])}"
        ),
        "session_id": session_id,
        "execution_mode": "governed",
        "status": guidance["status"],
        "risk_level": guidance["risk_level"],
        "task_type": guidance["task_type"],
        "required_questions": guidance["required_questions"],
        "required_reads": read_policy["required_reads"],
        "recommended_context_packs": guidance["recommended_packs"],
        "onboarding": {
            "needs_full_reads": read_policy["needs_full_reads"],
            "sessions_started": read_policy["sessions_started"],
            "onboarding_full_reads": read_policy["onboarding_full_reads"],
        },
    }
    _retry_guard_clear(project_dir, tool="haxaml_session_start", error_code="about_required", task=task)
    return _ok("haxaml_session_start", payload, warnings=warnings, detail=detail_mode)


@mcp_app.tool()
def haxaml_session_plan(
    session_id: str,
    project_dir: str = ".",
    detail: str = DETAIL_SHORT,
) -> dict:
    """Generate a short execution plan and risk check for a started session."""
    detail_mode, detail_err = _normalize_detail("haxaml_session_plan", detail)
    if detail_err:
        return detail_err

    sm, _ = _get_state_manager(project_dir)
    if not sm:
        return _err("haxaml_session_plan", "missing_acts", "acts.yaml not found")

    state = sm.read()
    contract = _lifecycle_contract_state(state)
    if not _contract_allows(contract, "haxaml_session_plan"):
        return _contract_violation(
            "haxaml_session_plan",
            project_dir=project_dir,
            contract=contract,
            reason="Session plan is out of lifecycle order.",
            retry_after=contract.get("required_next", []),
        )
    if contract.get("active_session_id", "") != session_id:
        return _contract_violation(
            "haxaml_session_plan",
            project_dir=project_dir,
            contract=contract,
            reason="Session plan must target the active governed session.",
            details={"requested_session_id": session_id},
        )
    session = _find_session(state, session_id)
    if not session:
        return _err("haxaml_session_plan", "unknown_session", f"Session not found: {session_id}")

    task = str(session.get("task", ""))
    frame = load_frame_data(project_dir)
    guidance = _guidance_eval(task, frame)
    rules = frame.get("rules") or {}
    verify_expect_raw = ((rules.get("after_task") or {}).get("verify", []) or [])
    verify_expect = [
        item.strip() for item in verify_expect_raw if isinstance(item, str) and item.strip()
    ]
    if not verify_expect:
        verify_expect = [
            "Confirm changes satisfy task scope.",
            "Run relevant validation/tests.",
            "Record unresolved risks and follow-ups.",
        ]

    plan = [
        "Inspect context pack and required rules for this task.",
        "Apply smallest logical change set in scoped files.",
        "Run validations/tests for touched behavior.",
        "Run reflective verification before record.",
    ]
    if guidance["status"] == "action_required":
        plan.insert(0, "Resolve required clarification questions before code changes.")

    session["phase"] = "plan"
    session["status"] = "planned"
    session["updated"] = _now_iso()
    session["plan"] = plan
    contract = _contract_touch(
        contract,
        phase="plan",
        required_next=["haxaml_context_pack"],
        tool_name="haxaml_session_plan",
        active_session_id=session_id,
        active_task=str(session.get("task", "") or ""),
    )
    _set_lifecycle_contract_state(state, contract)
    err = _persist_state(sm, state)
    warnings = [f"Could not persist session plan: {err}"] if err else []

    return _ok(
        "haxaml_session_plan",
        {
            "message": f"Session plan prepared for {session_id}",
            "session_id": session_id,
            "execution_mode": guidance["execution_mode"],
            "status": guidance["status"],
            "risk_level": guidance["risk_level"],
            "plan": plan,
            "risk_checks": guidance["assumptions"] + guidance["missing_context"],
            "verification_expectations": verify_expect,
            "visibility_policy": "Optional diagnostics only; call health/needs/reconcile/state_show on failure, uncertainty, or pre-final check.",
            "retry_policy": "If same gate error appears twice, stop retrying and fix root cause before retrying once.",
        },
        warnings=warnings,
        detail=detail_mode,
    )


@mcp_app.tool()
def haxaml_context_pack(
    task: str,
    project_dir: str = ".",
    pack: str = "balanced",
    include_state: bool = True,
    session_id: str = "",
    refresh_reason: str = "",
    detail: str = DETAIL_SHORT,
) -> dict:
    """Build compact task-specific context packs for token-efficient agent runs."""
    detail_mode, detail_err = _normalize_detail("haxaml_context_pack", detail)
    if detail_err:
        return detail_err

    frame = load_frame_data(project_dir)
    if not frame.get("facts"):
        return _err("haxaml_context_pack", "missing_facts", "facts.yaml not found")

    mode_eval = _utility_mode_eval(task)
    if mode_eval["mode"] == "utility":
        return _utility_mode_error("haxaml_context_pack", project_dir, task, "")

    if not session_id:
        return _err(
            "haxaml_context_pack",
            "lifecycle_contract_violation",
            "session_id is required for governed context-pack calls.",
            {
                "project_dir": str(Path(project_dir).resolve()),
                "expected_next": ["haxaml_context_pack"],
                "retry_after": ["haxaml_session_plan(session_id=..., project_dir='.')"],
            },
        )

    sm, _ = _get_state_manager(project_dir)
    if not sm:
        return _err("haxaml_context_pack", "missing_acts", "acts.yaml not found")
    warnings = []
    state = sm.read() if sm else {}
    contract = _lifecycle_contract_state(state)
    required_next = contract.get("required_next", [])
    allow_refresh_repeat = (
        isinstance(required_next, list)
        and "haxaml_session_verify" in required_next
        and contract.get("active_session_id", "") == session_id
    )
    if not _contract_allows(contract, "haxaml_context_pack") and not allow_refresh_repeat:
        return _contract_violation(
            "haxaml_context_pack",
            project_dir=project_dir,
            contract=contract,
            reason="Context pack is out of lifecycle order.",
            retry_after=contract.get("required_next", []),
        )
    if contract.get("active_session_id", "") != session_id:
        return _contract_violation(
            "haxaml_context_pack",
            project_dir=project_dir,
            contract=contract,
            reason="Context pack must target the active governed session.",
            details={"requested_session_id": session_id},
        )
    session = None
    prior_calls = 0
    refresh_reason = refresh_reason.strip()
    session = _find_session(state, session_id)
    if not session:
        return _err("haxaml_context_pack", "unknown_session", f"Session not found: {session_id}")
    raw_calls = session.get("context_pack_calls", 0)
    if isinstance(raw_calls, int) and raw_calls > 0:
        prior_calls = raw_calls
    if prior_calls >= 1 and not refresh_reason:
        return _err(
            "haxaml_context_pack",
            "context_pack_refresh_reason_required",
            "Context pack already generated for this session. Repeat only when scope changed or context is stale, and pass refresh_reason.",
            {
                "session_id": session_id,
                "context_pack_calls": prior_calls,
                "required": "refresh_reason",
                "allowed_examples": [
                    "scope changed to include billing module",
                    "context stale after major file updates",
                ],
            },
        )

    pack_data = build_context_pack(project_dir, task=task, pack=pack, include_state=include_state)
    text = format_context_pack(pack_data)
    tokens = count_tokens(text)

    compaction = state.get("context_compaction", {})
    if not isinstance(compaction, dict):
        compaction = {}
    compaction["last_pack_tokens"] = tokens
    compaction["last_window_usage"] = pack_data.get("_meta", {}).get("context_window_usage", {})
    resolved_pack = pack_data.get("_meta", {}).get("resolved_pack", pack)
    if resolved_pack in ("minimal", "balanced", "full"):
        compaction["default_pack"] = resolved_pack
    state["context_compaction"] = compaction
    session["context_pack_calls"] = prior_calls + 1
    session["last_context_pack_at"] = _now_iso()
    session["last_context_pack_reason"] = refresh_reason
    contract = _contract_touch(
        contract,
        phase="context",
        required_next=["haxaml_session_verify"],
        tool_name="haxaml_context_pack",
        active_session_id=session_id,
        active_task=str(session.get("task", "") or task),
    )
    _set_lifecycle_contract_state(state, contract)
    err = _persist_state(sm, state)
    if err:
        warnings.append(f"Could not persist context compaction stats: {err}")

    return _ok(
        "haxaml_context_pack",
        {
            "message": text,
            "context_pack": pack_data,
            "tokens": tokens,
            "pack": pack_data.get("_meta", {}).get("resolved_pack", pack),
            "session_id": session_id,
            "context_pack_calls": (prior_calls + 1) if session_id else 0,
            "refresh_reason": refresh_reason,
        },
        warnings=warnings,
        detail=detail_mode,
    )


@mcp_app.tool()
def haxaml_session_verify(
    task: str,
    project_dir: str = ".",
    session_id: str = "",
    inspected_context: Optional[list[str]] = None,
    changed_files: Optional[list[str]] = None,
    unresolved_questions: Optional[list[str]] = None,
    assumptions: Optional[list[str]] = None,
    summary: str = "",
    detail: str = DETAIL_SHORT,
) -> dict:
    """Run reflective verification checks and store evidence in acts.yaml."""
    detail_mode, detail_err = _normalize_detail("haxaml_session_verify", detail)
    if detail_err:
        return detail_err

    frame = load_frame_data(project_dir)
    if not frame.get("facts"):
        return _err("haxaml_session_verify", "missing_facts", "facts.yaml not found")
    if not session_id and _utility_mode_eval(task)["mode"] == "utility":
        return _utility_mode_error("haxaml_session_verify", project_dir, task, "")
    if not session_id:
        return _err(
            "haxaml_session_verify",
            "lifecycle_contract_violation",
            "session_id is required for governed verification calls.",
            {
                "project_dir": str(Path(project_dir).resolve()),
                "expected_next": ["haxaml_session_verify"],
            },
        )

    rules = frame.get("rules") or {}
    guidance = _guidance_eval(task, frame)
    inspected_context = inspected_context or []
    changed_files = changed_files or []
    unresolved_questions = unresolved_questions or []
    assumptions = assumptions or []

    required_reads = ((rules.get("before_task") or {}).get("read_first", []) or [])
    required_checks = _rules_policy(
        rules,
        "verification_policy",
        {
            "require_checks": [
                "understood_task",
                "inspected_context",
                "changed_right_files",
                "risky_or_unrelated_touch",
                "followed_rules",
                "updated_journal",
                "unresolved_logged",
                "explained_changes",
            ],
            "allow_pass_with_risks": True,
        },
    )["require_checks"]

    risky_paths = [p for p in changed_files if any(x in p for x in (".env", "secrets", ".pem", "credentials"))]
    has_summary = bool(summary.strip())
    inspected_ok = all(path in inspected_context for path in required_reads) if required_reads else bool(inspected_context)
    unresolved_logged = bool(unresolved_questions) or guidance["status"] != "action_required"
    rule_follow_ok = not risky_paths

    checks = {
        "understood_task": (bool(task.strip()), "Task text was provided."),
        "inspected_context": (inspected_ok, "Inspected context includes required reads."),
        "changed_right_files": (bool(changed_files) or has_summary, "Changed files or summary evidence was provided."),
        "risky_or_unrelated_touch": (not risky_paths, "No risky file patterns were reported."),
        "followed_rules": (rule_follow_ok, "No forbidden risky path was reported."),
        "updated_journal": (True, "Journal update is enforced at session_record stage."),
        "unresolved_logged": (unresolved_logged, "Unresolved items were explicitly captured or not required."),
        "explained_changes": (has_summary, "Summary explains what changed and why."),
    }

    failures = [name for name in required_checks if name in checks and not checks[name][0]]
    if guidance["status"] == "action_required" and not unresolved_questions and not inspected_ok:
        verdict = "needs_clarification"
    elif not failures:
        verdict = "pass"
    elif len(failures) <= 2 and _rules_policy(rules, "verification_policy", {"allow_pass_with_risks": True}).get("allow_pass_with_risks", True):
        verdict = "pass_with_risks"
    else:
        verdict = "fail"

    check_rows = [
        {"name": name, "passed": checks[name][0], "details": checks[name][1]}
        for name in required_checks
        if name in checks
    ]

    evidence_refs = [".haxaml/facts.yaml", ".haxaml/rules.yaml", ".haxaml/acts.yaml"] + changed_files
    verification_id = f"verify-{uuid.uuid4().hex[:10]}"
    timestamp = _now_iso()

    sm, _ = _get_state_manager(project_dir)
    if not sm:
        return _err("haxaml_session_verify", "missing_acts", "acts.yaml not found")
    warnings = []
    state = sm.read()
    contract = _lifecycle_contract_state(state)
    if not _contract_allows(contract, "haxaml_session_verify"):
        return _contract_violation(
            "haxaml_session_verify",
            project_dir=project_dir,
            contract=contract,
            reason="Session verification is out of lifecycle order.",
            retry_after=contract.get("required_next", []),
        )
    if contract.get("active_session_id", "") != session_id:
        return _contract_violation(
            "haxaml_session_verify",
            project_dir=project_dir,
            contract=contract,
            reason="Session verification must target the active governed session.",
            details={"requested_session_id": session_id},
        )
    verifications = state.get("verifications", [])
    if not isinstance(verifications, list):
        verifications = []
    verifications.append(
        {
            "id": verification_id,
            "session_id": session_id or "",
            "task": task,
            "verdict": verdict,
            "summary": summary,
            "unresolved_questions": unresolved_questions,
            "assumptions": assumptions,
            "follow_ups": guidance["required_questions"] if verdict in ("fail", "needs_clarification") else [],
            "checks": check_rows,
            "evidence_refs": evidence_refs,
            "timestamp": timestamp,
        }
    )
    state["verifications"] = verifications
    session = _find_session(state, session_id)
    if session:
        session["phase"] = "verify"
        session["status"] = "verified" if verdict in ("pass", "pass_with_risks") else "failed"
        session["updated"] = timestamp
    next_tools = ["haxaml_session_verify"]
    if verdict in ("pass", "pass_with_risks"):
        next_tools = ["haxaml_session_record"]
    contract = _contract_touch(
        contract,
        phase="verify",
        required_next=next_tools,
        tool_name="haxaml_session_verify",
        active_session_id=session_id,
        active_task=task,
        last_verification_id=verification_id,
        last_verification_verdict=verdict,
    )
    _set_lifecycle_contract_state(state, contract)
    err = _persist_state(sm, state)
    if err:
        warnings.append(f"Could not persist verification report: {err}")

    message = f"Verification {verification_id}: {verdict}"
    if failures:
        message += f" ({len(failures)} failed check(s))"
    if guidance["status"] == "action_required":
        message += " — clarification needed before confident execution."

    if verdict in ("pass", "pass_with_risks"):
        _retry_guard_clear(
            project_dir,
            tool="haxaml_session_record",
            error_code="verification_required",
            task=task,
            session_id=session_id,
        )

    return _ok(
        "haxaml_session_verify",
        {
            "message": message,
            "verification_id": verification_id,
            "session_id": session_id or "",
            "task": task,
            "verdict": verdict,
            "checks": check_rows,
            "evidence_refs": evidence_refs,
            "risky_paths": risky_paths,
            "unresolved_questions": unresolved_questions,
            "assumptions": assumptions,
            "follow_ups": guidance["required_questions"] if verdict in ("fail", "needs_clarification") else [],
        },
        warnings=warnings,
        detail=detail_mode,
    )


@mcp_app.tool()
def haxaml_session_record(
    task: str,
    result: str = "success",
    project_dir: str = ".",
    session_id: str = "",
    changes: str = "",
    decisions: str = "",
    risks: str = "",
    detail: str = DETAIL_SHORT,
) -> dict:
    """Record a session result; enforces verification gate before success/partial record."""
    detail_mode, detail_err = _normalize_detail("haxaml_session_record", detail)
    if detail_err:
        return detail_err

    if result not in ("success", "partial", "failed"):
        return _err("haxaml_session_record", "invalid_result", f"Invalid result: {result}")

    try:
        runner = ExecutionRunner(project_dir)
    except FileNotFoundError as e:
        return _err("haxaml_session_record", "missing_frame", str(e))

    frame = load_frame_data(project_dir)
    if not session_id and _utility_mode_eval(task)["mode"] == "utility":
        return _utility_mode_error("haxaml_session_record", project_dir, task, "")
    if not session_id:
        return _err(
            "haxaml_session_record",
            "lifecycle_contract_violation",
            "session_id is required for governed session recording.",
            {
                "project_dir": str(Path(project_dir).resolve()),
                "expected_next": ["haxaml_session_record"],
            },
        )
    rules = frame.get("rules") or {}
    lifecycle = _rules_policy(rules, "lifecycle", {"enforce_verify_before_record": True})
    enforce_verify = bool(lifecycle.get("enforce_verify_before_record", True))

    sm, _ = _get_state_manager(project_dir)
    if not sm:
        return _err("haxaml_session_record", "missing_acts", "acts.yaml not found")
    state = sm.read()
    contract = _lifecycle_contract_state(state)

    latest_verdict = None
    latest_verification_id = ""
    verifications = state.get("verifications", []) if isinstance(state, dict) else []
    if isinstance(verifications, list):
        for item in reversed(verifications):
            if not isinstance(item, dict):
                continue
            if session_id and item.get("session_id") != session_id:
                continue
            if item.get("task") != task:
                continue
            latest_verdict = item.get("verdict")
            latest_verification_id = str(item.get("id", ""))
            break
    required_next = contract.get("required_next", [])
    if not _contract_allows(contract, "haxaml_session_record"):
        if (
            isinstance(required_next, list)
            and "haxaml_session_verify" in required_next
            and result in ("success", "partial")
        ):
            return _gate_error_with_retry_policy(
                "haxaml_session_record",
                "verification_required",
                "Verification is required before recording success/partial results.",
                project_dir=project_dir,
                task=task,
                session_id=session_id,
                details={
                    "task": task,
                    "session_id": session_id,
                    "latest_verdict": latest_verdict,
                    "allowed_verdicts": ["pass", "pass_with_risks"],
                },
            )
        if not (isinstance(required_next, list) and "haxaml_session_verify" in required_next and result == "failed"):
            return _contract_violation(
                "haxaml_session_record",
                project_dir=project_dir,
                contract=contract,
                reason="Session record is out of lifecycle order.",
                retry_after=required_next if isinstance(required_next, list) else [],
            )
    if contract.get("active_session_id", "") != session_id:
        return _contract_violation(
            "haxaml_session_record",
            project_dir=project_dir,
            contract=contract,
            reason="Session record must target the active governed session.",
            details={"requested_session_id": session_id},
        )
    expect_sync = _expect_sync_state(state)
    if expect_sync["required"]:
        return _gate_error_with_retry_policy(
            "haxaml_session_record",
            "expect_sync_required",
            "Previous record is not synced to expect.yaml. Call haxaml_expect_sync before recording another governed result.",
            project_dir=project_dir,
            task=task,
            session_id=session_id,
            details={
                "pending_sync": expect_sync,
                "retry_after": ["haxaml_expect_sync(project_dir='.')", "haxaml_session_record(...)"],
            },
        )

    reconcile = reconcile_derivation(project_dir)
    blocking_conflicts = reconcile["severity_totals"]["blocking"]
    if result in ("success", "partial") and blocking_conflicts > 0:
        return _gate_error_with_retry_policy(
            "haxaml_session_record",
            "derivation_conflicts",
            "Cannot record success/partial while blocking derivation conflicts exist.",
            project_dir=project_dir,
            task=task,
            session_id=session_id,
            details={
                "task": task,
                "session_id": session_id,
                "gate_reasons": reconcile["gate_reasons"],
                "reconcile": reconcile,
            },
        )
    if result == "failed" and blocking_conflicts > 0 and not _has_conflict_stop_reason(changes, decisions, risks):
        return _gate_error_with_retry_policy(
            "haxaml_session_record",
            "conflict_reason_required",
            "Recording failed is allowed only when unresolved conflicts are explicitly documented as the stop reason.",
            project_dir=project_dir,
            task=task,
            session_id=session_id,
            details={
                "task": task,
                "session_id": session_id,
                "required_hint": "Mention conflict/reconcile/derivation mismatch in changes, decisions, or risks.",
                "gate_reasons": reconcile["gate_reasons"],
                "reconcile": reconcile,
            },
        )

    if enforce_verify and result in ("success", "partial"):
        if latest_verdict not in ("pass", "pass_with_risks"):
            return _gate_error_with_retry_policy(
                "haxaml_session_record",
                "verification_required",
                "Verification is required before recording success/partial results.",
                project_dir=project_dir,
                task=task,
                session_id=session_id,
                details={
                    "task": task,
                    "session_id": session_id,
                    "latest_verdict": latest_verdict,
                    "allowed_verdicts": ["pass", "pass_with_risks"],
                },
            )

    run_result = runner.finish_run(
        task=task,
        result=result,
        changes=changes,
        decisions=decisions,
        risks=risks,
    )
    if run_result.errors:
        return _err(
            "haxaml_session_record",
            "run_record_error",
            "Run completed with errors.",
            {"errors": run_result.errors, "warnings": run_result.warnings},
        )

    warnings = list(run_result.warnings)
    state = sm.read()
    context_compaction = state.get("context_compaction", {})
    if not isinstance(context_compaction, dict):
        context_compaction = {}
    sync_state = _expect_sync_state(state)
    sync_state.update(
        {
            "required": True,
            "pending_run_id": run_result.run_id,
            "pending_task": task,
            "pending_result": result,
            "pending_recorded_at": _now_iso(),
        }
    )
    state["expect_sync"] = sync_state
    session = _find_session(state, session_id)
    if session:
        session["phase"] = "record"
        session["status"] = "recorded"
        session["updated"] = _now_iso()
        session["ended"] = _now_iso()
    contract = _contract_touch(
        contract,
        phase="record",
        required_next=["haxaml_expect_sync"],
        tool_name="haxaml_session_record",
        active_session_id=session_id,
        active_task=task,
        last_verification_id=latest_verification_id,
        last_verification_verdict=str(latest_verdict or ""),
        last_record_run_id=run_result.run_id,
        last_record_result=result,
    )
    _set_lifecycle_contract_state(state, contract)
    err = _persist_state(sm, state)
    if err:
        warnings.append(f"Could not persist session close state: {err}")

    stale = export_if_stale(project_dir, agents=["generic"])
    _retry_guard_clear(
        project_dir,
        tool="haxaml_session_record",
        task=task,
        session_id=session_id,
    )
    return _ok(
        "haxaml_session_record",
        {
            "message": (
                f"✓ Session record complete (run {run_result.run_id}, result={result}). "
                "Next: call haxaml_expect_sync to update expect.yaml deterministically."
            ),
            "session_id": session_id,
            "run_id": run_result.run_id,
            "token_count": run_result.token_count,
            "verification_id": latest_verification_id,
            "verification_verdict": latest_verdict,
            "gate_reasons": reconcile["gate_reasons"],
            "reconcile": reconcile,
            "last_pack_tokens": context_compaction.get("last_pack_tokens", 0) if sm else 0,
            "last_context_window_usage": context_compaction.get("last_window_usage", {}) if sm else {},
            "auto_exported": stale,
            "expect_sync_required": True,
        },
        warnings=warnings,
        detail=detail_mode,
    )


@mcp_app.tool()
def haxaml_expect_sync(
    project_dir: str = ".",
    run: int = 0,
    detail: str = DETAIL_SHORT,
) -> dict:
    """Sync latest recorded acts outcome into expect.yaml runbook deterministically."""
    detail_mode, detail_err = _normalize_detail("haxaml_expect_sync", detail)
    if detail_err:
        return detail_err

    sm, _ = _get_state_manager(project_dir)
    if not sm:
        return _err("haxaml_expect_sync", "missing_acts", "acts.yaml not found")

    state = sm.read()
    contract = _lifecycle_contract_state(state)
    if not _contract_allows(contract, "haxaml_expect_sync"):
        return _contract_violation(
            "haxaml_expect_sync",
            project_dir=project_dir,
            contract=contract,
            reason="Expect sync is out of lifecycle order.",
            retry_after=contract.get("required_next", []),
        )
    sync_state = _expect_sync_state(state)
    if not sync_state["required"]:
        return _ok(
            "haxaml_expect_sync",
            {
                "message": "No pending expect sync. acts.yaml and expect.yaml lifecycle is already reconciled.",
                "synced": False,
                "expect_sync": sync_state,
            },
            detail=detail_mode,
        )

    pending_result = sync_state["pending_result"].strip().lower()
    status_map = {"success": "done", "partial": "active", "failed": "blocked"}
    if pending_result not in status_map:
        return _err(
            "haxaml_expect_sync",
            "invalid_pending_result",
            f"Unsupported pending result for expect sync: {pending_result or '(empty)'}",
            {"pending_sync": sync_state, "allowed_results": sorted(status_map.keys())},
        )

    project = Path(project_dir).resolve()
    expect_path = resolve_frame_file(project, "expect.yaml")
    if not expect_path:
        return _err("haxaml_expect_sync", "missing_expect", "expect.yaml not found")

    expect = load_yaml(str(expect_path))
    runbook = expect.get("runbook", [])
    if not isinstance(runbook, list) or not runbook:
        return _err("haxaml_expect_sync", "invalid_expect_runbook", "expect.yaml runbook is missing or empty.")

    target_run = int(run) if isinstance(run, int) else 0
    if target_run <= 0:
        active_runs = [
            int(item.get("run"))
            for item in runbook
            if isinstance(item, dict) and item.get("status") == "active" and isinstance(item.get("run"), int)
        ]
        if len(active_runs) != 1:
            return _err(
                "haxaml_expect_sync",
                "ambiguous_active_run",
                "Cannot infer target runbook entry. Provide run=<number> explicitly.",
                {"active_runs": sorted(active_runs), "pending_sync": sync_state},
            )
        target_run = active_runs[0]

    target = None
    for item in runbook:
        if isinstance(item, dict) and item.get("run") == target_run:
            target = item
            break
    if not target:
        return _err(
            "haxaml_expect_sync",
            "run_not_found",
            f"Run {target_run} not found in expect.runbook.",
            {"run": target_run},
        )

    target["status"] = status_map[pending_result]
    expected_status = target["status"]

    # Maintain a single active run invariant when sync writes statuses.
    if pending_result in ("success", "partial"):
        for item in runbook:
            if (
                isinstance(item, dict)
                and item is not target
                and item.get("status") == "active"
            ):
                item["status"] = "planned"

    if pending_result == "success":
        done_like = {"done", "skipped"}
        next_candidate = None
        for item in sorted(
            [x for x in runbook if isinstance(x, dict) and isinstance(x.get("run"), int)],
            key=lambda r: int(r.get("run", 0)),
        ):
            if item.get("status") != "planned":
                continue
            deps = item.get("depends_on", [])
            if not isinstance(deps, list):
                deps = []
            deps_ok = True
            for dep_run in deps:
                dep = next(
                    (r for r in runbook if isinstance(r, dict) and r.get("run") == dep_run),
                    None,
                )
                if not dep or dep.get("status") not in done_like:
                    deps_ok = False
                    break
            if deps_ok:
                next_candidate = item
                break
        if next_candidate:
            next_candidate["status"] = "active"

    phases = expect.get("phases", [])
    if isinstance(phases, list):
        active_phase_seen = False
        for phase in phases:
            if not isinstance(phase, dict):
                continue
            phase_name = str(phase.get("name", "")).strip()
            if not phase_name:
                continue
            phase_runs = [
                item
                for item in runbook
                if isinstance(item, dict) and str(item.get("phase", "")).strip() == phase_name
            ]
            if not phase_runs:
                continue
            statuses = {str(item.get("status", "")).strip() for item in phase_runs}
            if statuses and statuses.issubset({"done", "skipped"}):
                phase["status"] = "done"
            elif "active" in statuses and not active_phase_seen:
                phase["status"] = "active"
                active_phase_seen = True
            else:
                phase["status"] = "planned"

    import yaml

    expect["runbook"] = runbook
    if isinstance(phases, list):
        expect["phases"] = phases
    with open(expect_path, "w", encoding="utf-8") as handle:
        yaml.dump(expect, handle, default_flow_style=False, sort_keys=False)

    now = _now_iso()
    sync_state["required"] = False
    sync_state["last_synced_run_id"] = sync_state["pending_run_id"]
    sync_state["last_synced_at"] = now
    sync_state["last_sync_status"] = expected_status
    sync_state["pending_run_id"] = ""
    sync_state["pending_task"] = ""
    sync_state["pending_result"] = ""
    sync_state["pending_recorded_at"] = ""
    state["expect_sync"] = sync_state
    contract = _contract_touch(
        contract,
        phase="sync",
        required_next=["haxaml_guidance"],
        tool_name="haxaml_expect_sync",
        active_session_id="",
        active_task="",
        last_record_run_id=sync_state["last_synced_run_id"],
        last_record_result="",
    )
    _set_lifecycle_contract_state(state, contract)
    err = _persist_state(sm, state)
    warnings = [f"Could not persist expect sync state: {err}"] if err else []

    _retry_guard_clear(project_dir, tool="haxaml_session_record", error_code="expect_sync_required")
    _retry_guard_clear(project_dir, tool="haxaml_validate", error_code="lifecycle_drift")

    return _ok(
        "haxaml_expect_sync",
        {
            "message": (
                f"Synced acts -> expect for run {target_run}. "
                f"Applied status '{expected_status}' from recorded result '{pending_result}'."
            ),
            "synced": True,
            "run": target_run,
            "applied_status": expected_status,
            "expect_sync": sync_state,
        },
        warnings=warnings,
        detail=detail_mode,
    )


# Deprecated compatibility helper.
# Not registered as an MCP tool.
# Remove fully in v0.7 after dogfooding.
def haxaml_run(
    task: str,
    description: str = "",
    project_dir: str = ".",
    detail: str = DETAIL_SHORT,
) -> dict:
    """Deprecated wrapper. Use haxaml_guidance + haxaml_prebuild instead."""
    detail_mode, detail_err = _normalize_detail("haxaml_run", detail)
    if detail_err:
        return detail_err

    guided = haxaml_guidance(task=task, project_dir=project_dir, detail=detail_mode)
    if not guided.get("ok"):
        dep = _wrapper_deprecation("haxaml_run", ["haxaml_guidance", "haxaml_session_start"])
        return _err(
            "haxaml_run",
            guided.get("error", {}).get("code", "guidance_failed"),
            guided.get("error", {}).get("message", "Guidance failed."),
            guided.get("error", {}).get("details", {}),
            warnings=[dep["message"]],
        )

    started = haxaml_session_start(task=task, description=description, project_dir=project_dir, detail=detail_mode)
    dep = _wrapper_deprecation("haxaml_run", ["haxaml_session_start"])
    if not started.get("ok"):
        return _err(
            "haxaml_run",
            started.get("error", {}).get("code", "session_start_failed"),
            started.get("error", {}).get("message", "Session start failed."),
            started.get("error", {}).get("details", {}),
            warnings=[dep["message"]],
        )

    payload = started.get("data", {})
    session_id = payload.get("session_id", "")
    planned = haxaml_session_plan(session_id=session_id, project_dir=project_dir, detail=detail_mode)
    if not planned.get("ok"):
        return _err(
            "haxaml_run",
            planned.get("error", {}).get("code", "session_plan_failed"),
            planned.get("error", {}).get("message", "Session plan failed."),
            planned.get("error", {}).get("details", {}),
            warnings=[dep["message"]],
        )
    packed = haxaml_context_pack(
        task=task,
        project_dir=project_dir,
        pack="minimal",
        include_state=True,
        session_id=session_id,
        refresh_reason="wrapper bootstrap context for compatibility",
        detail=detail_mode,
    )
    if not packed.get("ok"):
        return _err(
            "haxaml_run",
            packed.get("error", {}).get("code", "context_pack_failed"),
            packed.get("error", {}).get("message", "Context pack failed."),
            packed.get("error", {}).get("details", {}),
            warnings=[dep["message"]],
        )

    lines = [f"✓ Run started: {task}"]
    lines.append(f"  Session: {session_id}")
    lines.append(f"  Status: {payload.get('status', 'proceed')}")
    lines.append("  → Work on the task, then call haxaml_done (or haxaml_session_verify + haxaml_session_record)")
    return _ok(
        "haxaml_run",
        {
            "message": "\n".join(lines),
            "task": task,
            "session_id": session_id,
            "warnings": started.get("warnings", []),
            "deprecation": dep,
        },
        warnings=[dep["message"]],
        detail=detail_mode,
    )


# Deprecated compatibility helper.
# Not registered as an MCP tool.
# Remove fully in v0.7 after dogfooding.
def haxaml_done(
    task: str,
    result: str = "success",
    changes: str = "",
    decisions: str = "",
    risks: str = "",
    project_dir: str = ".",
    session_id: str = "",
    detail: str = DETAIL_SHORT,
) -> dict:
    """Deprecated wrapper. Use haxaml_session_verify + haxaml_session_record instead."""
    detail_mode, detail_err = _normalize_detail("haxaml_done", detail)
    if detail_err:
        return detail_err

    if not session_id:
        sm, _ = _get_state_manager(project_dir)
        if sm:
            state = sm.read()
            sessions = state.get("sessions", [])
            if isinstance(sessions, list):
                for item in reversed(sessions):
                    if not isinstance(item, dict):
                        continue
                    if str(item.get("task", "")).strip() != task.strip():
                        continue
                    if str(item.get("status", "")).strip() not in {"started", "planned", "verified"}:
                        continue
                    session_id = str(item.get("id", "")).strip()
                    if session_id:
                        break

    verify = haxaml_session_verify(
        task=task,
        project_dir=project_dir,
        session_id=session_id,
        summary=changes or decisions or risks or f"Completed task: {task}",
        changed_files=[],
        unresolved_questions=[],
        assumptions=[],
        detail=detail_mode,
    )
    if not verify.get("ok"):
        dep = _wrapper_deprecation("haxaml_done", ["haxaml_session_verify", "haxaml_session_record"])
        return _err(
            "haxaml_done",
            verify.get("error", {}).get("code", "verify_failed"),
            verify.get("error", {}).get("message", "Verification failed."),
            verify.get("error", {}).get("details", {}),
            warnings=[dep["message"]],
        )

    record = haxaml_session_record(
        task=task,
        result=result,
        project_dir=project_dir,
        session_id=session_id,
        changes=changes,
        decisions=decisions,
        risks=risks,
        detail=detail_mode,
    )
    if not record.get("ok"):
        dep = _wrapper_deprecation("haxaml_done", ["haxaml_session_verify", "haxaml_session_record"])
        return _err(
            "haxaml_done",
            record.get("error", {}).get("code", "record_failed"),
            record.get("error", {}).get("message", "Recording failed."),
            record.get("error", {}).get("details", {}),
            warnings=[dep["message"]],
        )

    payload = record.get("data", {})
    dep = _wrapper_deprecation("haxaml_done", ["haxaml_session_verify", "haxaml_session_record"])
    payload["message"] = f"{payload.get('message', '')}\n(verification: {verify.get('data', {}).get('verification_id', '')})"
    payload["deprecation"] = dep
    return _ok(
        "haxaml_done",
        payload,
        warnings=[dep["message"]],
        detail=detail_mode,
    )
