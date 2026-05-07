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


def _missing_acts_error(tool: str) -> dict:
    return _err(tool, "missing_acts", "acts.yaml not found")


def _load_state_or_error(tool: str, project_dir: str) -> tuple[Optional[StateManager], Optional[dict], Optional[dict]]:
    """Load acts state once and keep the call-sites focused on lifecycle logic."""
    sm, _ = _get_state_manager(project_dir)
    if not sm:
        return None, None, _missing_acts_error(tool)
    return sm, sm.read(), None


def _active_session_violation(
    tool: str,
    *,
    project_dir: str,
    contract: dict[str, Any],
    session_id: str,
    reason: str,
) -> dict:
    return _contract_violation(
        tool,
        project_dir=project_dir,
        contract=contract,
        reason=reason,
        details={"requested_session_id": session_id},
    )


def _latest_verification_for_session(
    state: dict[str, Any],
    *,
    session_id: str,
    task: str,
) -> tuple[Optional[str], str]:
    """Return the latest verification verdict/id pair for the current session task."""
    latest_verdict: Optional[str] = None
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
    return latest_verdict, latest_verification_id


def _dedupe_strs(items: list[str]) -> list[str]:
    out: list[str] = []
    seen = set()
    for item in items:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def _record_keywords(*parts: Any) -> list[str]:
    tokens: list[str] = []
    seen = set()
    for part in parts:
        text = str(part or "").lower()
        for raw in text.replace("/", " ").replace("-", " ").replace("_", " ").split():
            token = "".join(ch for ch in raw if ch.isalnum())
            if len(token) < 4 or token in seen:
                continue
            seen.add(token)
            tokens.append(token)
            if len(tokens) >= 12:
                return tokens
    return tokens


def _module_refs_for_files(frame: dict[str, Any], file_refs: list[str], task: str = "") -> list[str]:
    map_data = frame.get("map") or {}
    modules = map_data.get("modules", []) if isinstance(map_data, dict) else []
    task_l = task.lower()
    matched: list[str] = []
    for module in modules if isinstance(modules, list) else []:
        if not isinstance(module, dict):
            continue
        name = str(module.get("name", "")).strip()
        if not name:
            continue
        files = [str(item).strip() for item in (module.get("files") or []) if str(item).strip()]
        if name.lower() in task_l:
            matched.append(name)
            continue
        for ref in file_refs:
            if any(pattern in ref or ref in pattern for pattern in files):
                matched.append(name)
                break
    return _dedupe_strs(matched)


def _session_seed_refs(project_dir: str, frame: dict[str, Any], task: str) -> tuple[list[str], list[str], list[str]]:
    hints = build_context_hints(project_dir, task=task, frame_data=frame)
    file_refs = _dedupe_strs(
        [".haxaml/facts.yaml", ".haxaml/rules.yaml", ".haxaml/acts.yaml", ".haxaml/expect.yaml"]
        + list(hints.get("candidate_file_refs", []))
    )
    module_refs = _dedupe_strs(
        _module_refs_for_files(frame, file_refs, task=task)
    )
    keywords = _record_keywords(task, " ".join(file_refs), " ".join(module_refs))
    return file_refs, module_refs, keywords


@mcp_app.tool()
def haxaml_about(project_dir: str = ".", detail: str = DETAIL_SHORT) -> dict:
    """Return onboarding context for Haxaml and FRAME. Call once per active agent/MCP session."""
    detail_mode, detail_err = _normalize_detail("haxaml_about", detail)
    if detail_err:
        return detail_err

    payload = _about_payload(project_dir)
    key = _project_key(project_dir)
    _ABOUT_ACK_CACHE.add(key)
    _retry_guard_clear(project_dir, tool="haxaml_prebuild", error_code="about_required")

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
        # Fresh or idle contracts are advanced to guidance; otherwise we only refresh
        # the acknowledgment metadata and preserve the active lifecycle position.
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
        sm, state, state_err = _load_state_or_error("haxaml_guidance", project_dir)
        if state_err:
            return state_err
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
    ]
    if execution_mode == "governed":
        msg_lines.append(
            f"Call budget: target {call_budget['target_calls']} calls "
            f"(max {call_budget['max_calls_without_visibility']} before optional diagnostics)"
        )
        next_step = "haxaml_prebuild"
    else:
        msg_lines.append("Next step: run the task directly and keep FRAME unchanged.")
        next_step = "run_outside_governed_flow"
    if guidance["mode_reason"]:
        msg_lines.append(f"Mode reason: {guidance['mode_reason']}")
    if guidance["required_questions"]:
        msg_lines.append("Required clarification:")
        msg_lines.extend([f"  - {q}" for q in guidance["required_questions"]])
    if guidance["missing_context"]:
        msg_lines.append("Missing context:")
        msg_lines.extend([f"  - {m}" for m in guidance["missing_context"]])

    # Keep the payload split between human-readable summary text and machine-usable fields.
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
        "next_step": next_step,
        "lifecycle": _lifecycle_hint(
            tool="haxaml_guidance",
            phase="guidance",
            depends_on=["haxaml_about"],
            preferred_next=next_step,
            allowed_next=["haxaml_prebuild"] if execution_mode == "governed" else ["run_outside_governed_flow"],
            contract_enforced=(execution_mode == "governed"),
        ),
    }
    if execution_mode == "governed":
        payload["call_budget"] = call_budget
        payload["visibility_calls_optional"] = call_budget["optional_visibility_calls"]
        payload["anti_bloat_policy"] = {
            "context_pack_limit": CONTEXT_PACK_LIMIT_TEXT,
            "visibility_calls": VISIBILITY_POLICY_TEXT,
            "retry_behavior": RETRY_POLICY_TEXT,
            "context_refresh_policy": _compact_context_refresh_policy(),
        }
    else:
        payload["policy"] = _utility_mode_policy()
    if guidance["execution_mode"] == "governed" and sm:
        # Guidance claims ownership of the active task before prebuild/session-start continue.
        updated = _contract_touch(
            contract,
            phase="guidance",
            required_next=["haxaml_prebuild"],
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
    if pack not in {"minimal", "balanced", "full"}:
        return _err(
            "haxaml_context_pack",
            "invalid_pack",
            "Invalid pack. Use 'minimal', 'balanced', or 'full'.",
            {"received": pack, "allowed": ["minimal", "balanced", "full"]},
        )

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
                "retry_after": ["haxaml_prebuild(task=..., description=..., project_dir='.')"],
            },
        )

    sm, state, state_err = _load_state_or_error("haxaml_context_pack", project_dir)
    if state_err:
        return state_err
    warnings = []
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
        return _active_session_violation(
            "haxaml_context_pack",
            project_dir=project_dir,
            contract=contract,
            session_id=session_id,
            reason="Context pack must target the active governed session.",
        )
    prior_calls = 0
    refresh_info = _normalize_context_refresh_reason(refresh_reason)
    session = _find_session(state, session_id)
    if not session:
        return _err("haxaml_context_pack", "unknown_session", f"Session not found: {session_id}")
    raw_calls = session.get("context_pack_calls", 0)
    if isinstance(raw_calls, int) and raw_calls > 0:
        prior_calls = raw_calls
    if prior_calls >= 1 and not refresh_info["reason"]:
        return _err(
            "haxaml_context_pack",
            "context_pack_refresh_reason_required",
            "Context pack already generated for this session. Repeat only when scope changed or context is stale, and pass refresh_reason.",
            {
                "session_id": session_id,
                "context_pack_calls": prior_calls,
                "required": "refresh_reason",
                "refresh_policy": _context_refresh_policy(),
            },
        )
    if prior_calls >= 1 and refresh_info["too_vague"]:
        return _err(
            "haxaml_context_pack",
            "context_pack_refresh_reason_too_vague",
            "Refresh reason is too vague. Explain what changed in scope or why the current context is stale.",
            {
                "session_id": session_id,
                "context_pack_calls": prior_calls,
                "received": refresh_info["reason"],
                "refresh_policy": _context_refresh_policy(),
            },
        )

    pack_data = build_context_pack(
        project_dir,
        task=task,
        pack=pack,
        include_state=include_state,
        frame_data=frame,
    )
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
    session["last_context_pack_reason"] = refresh_info["reason"]
    session["last_context_pack_reason_category"] = refresh_info["category"]
    contract = _contract_touch(
        contract,
        phase="context",
        required_next=["haxaml_context_fetch", "haxaml_session_verify"],
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
            "refresh_reason": refresh_info["reason"],
            "refresh_reason_category": refresh_info["category"],
            "next_step": "haxaml_session_verify",
            "lifecycle": _lifecycle_hint(
                tool="haxaml_context_pack",
                phase="context",
                depends_on=["haxaml_prebuild"],
                preferred_next="haxaml_session_verify",
                allowed_next=["haxaml_context_fetch", "haxaml_session_verify"],
            ),
        },
        warnings=warnings,
        detail=detail_mode,
    )


@mcp_app.tool()
def haxaml_context_fetch(
    task: str,
    query: str,
    session_id: str,
    project_dir: str = ".",
    sources: Optional[list[str]] = None,
    limit: int = 5,
    detail: str = DETAIL_SHORT,
) -> dict:
    """Follow-up governed retrieval across hot and archived FRAME memory."""
    detail_mode, detail_err = _normalize_detail("haxaml_context_fetch", detail)
    if detail_err:
        return detail_err

    frame = load_frame_data(project_dir)
    if not frame.get("facts"):
        return _err("haxaml_context_fetch", "missing_facts", "facts.yaml not found")
    if not session_id:
        return _err(
            "haxaml_context_fetch",
            "lifecycle_contract_violation",
            "session_id is required for governed context fetch calls.",
            {
                "project_dir": str(Path(project_dir).resolve()),
                "expected_next": ["haxaml_context_fetch", "haxaml_session_verify"],
            },
        )
    if not str(query or "").strip():
        return _err("haxaml_context_fetch", "missing_query", "query is required")

    sm, state, state_err = _load_state_or_error("haxaml_context_fetch", project_dir)
    if state_err:
        return state_err
    contract = _lifecycle_contract_state(state)
    required_next = contract.get("required_next", [])
    allow_repeat = (
        isinstance(required_next, list)
        and "haxaml_session_verify" in required_next
        and contract.get("active_session_id", "") == session_id
    )
    if not _contract_allows(contract, "haxaml_context_fetch") and not allow_repeat:
        return _contract_violation(
            "haxaml_context_fetch",
            project_dir=project_dir,
            contract=contract,
            reason="Context fetch is out of lifecycle order.",
            retry_after=contract.get("required_next", []),
        )
    if contract.get("active_session_id", "") != session_id:
        return _active_session_violation(
            "haxaml_context_fetch",
            project_dir=project_dir,
            contract=contract,
            session_id=session_id,
            reason="Context fetch must target the active governed session.",
        )

    result = search_context_memory(
        project_dir,
        task=task,
        query=query,
        sources=sources,
        limit=limit,
        frame_data=frame,
    )

    session = _find_session(state, session_id)
    if not session:
        return _err("haxaml_context_fetch", "unknown_session", f"Session not found: {session_id}")
    prior_calls = session.get("context_fetch_calls", 0)
    if not isinstance(prior_calls, int) or prior_calls < 0:
        prior_calls = 0
    session["context_fetch_calls"] = prior_calls + 1
    session["last_context_fetch_at"] = _now_iso()
    session["last_context_fetch_query"] = query
    session["last_context_fetch_sources"] = result["sources"]
    contract = _contract_touch(
        contract,
        phase="context",
        required_next=["haxaml_context_fetch", "haxaml_session_verify"],
        tool_name="haxaml_context_fetch",
        active_session_id=session_id,
        active_task=str(session.get("task", "") or task),
    )
    _set_lifecycle_contract_state(state, contract)
    err = _persist_state(sm, state)
    warnings = [f"Could not persist context fetch state: {err}"] if err else []

    return _ok(
        "haxaml_context_fetch",
        {
            "message": (
                f"Retrieved {len(result['hits'])} governed memory hit(s) for query '{query}'. "
                "Archive and hot FRAME state were searched without repo-wide content search."
            ),
            "task": task,
            "query": query,
            "session_id": session_id,
            "sources": result["sources"],
            "hits": result["hits"],
            "candidate_file_refs": result["candidate_file_refs"],
            "archive_available": result["archive_available"],
            "context_fetch_calls": prior_calls + 1,
            "next_step": "haxaml_session_verify",
            "lifecycle": _lifecycle_hint(
                tool="haxaml_context_fetch",
                phase="context",
                depends_on=["haxaml_context_pack"],
                preferred_next="haxaml_session_verify",
                allowed_next=["haxaml_context_fetch", "haxaml_session_verify"],
            ),
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
    file_refs = _dedupe_strs(evidence_refs + inspected_context)
    module_refs = _module_refs_for_files(frame, file_refs, task=task)
    verification_id = f"verify-{uuid.uuid4().hex[:10]}"
    timestamp = _now_iso()

    sm, state, state_err = _load_state_or_error("haxaml_session_verify", project_dir)
    if state_err:
        return state_err
    warnings = []
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
        return _active_session_violation(
            "haxaml_session_verify",
            project_dir=project_dir,
            contract=contract,
            session_id=session_id,
            reason="Session verification must target the active governed session.",
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
            "file_refs": file_refs,
            "module_refs": module_refs,
            "keywords": _record_keywords(task, summary, " ".join(file_refs), " ".join(module_refs)),
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
            "file_refs": file_refs,
            "module_refs": module_refs,
            "risky_paths": risky_paths,
            "unresolved_questions": unresolved_questions,
            "assumptions": assumptions,
            "follow_ups": guidance["required_questions"] if verdict in ("fail", "needs_clarification") else [],
            "next_step": "haxaml_session_record" if verdict in ("pass", "pass_with_risks") else "haxaml_session_verify",
            "lifecycle": _lifecycle_hint(
                tool="haxaml_session_verify",
                phase="verify",
                depends_on=["haxaml_context_pack"],
                preferred_next="haxaml_session_record" if verdict in ("pass", "pass_with_risks") else "haxaml_session_verify",
                allowed_next=["haxaml_session_record"] if verdict in ("pass", "pass_with_risks") else ["haxaml_session_verify"],
            ),
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

    sm, state, state_err = _load_state_or_error("haxaml_session_record", project_dir)
    if state_err:
        return state_err
    contract = _lifecycle_contract_state(state)

    latest_verdict, latest_verification_id = _latest_verification_for_session(
        state,
        session_id=session_id,
        task=task,
    )
    latest_verification = None
    verifications = state.get("verifications", []) if isinstance(state, dict) else []
    if isinstance(verifications, list):
        for item in reversed(verifications):
            if not isinstance(item, dict):
                continue
            if item.get("id") == latest_verification_id:
                latest_verification = item
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
        return _active_session_violation(
            "haxaml_session_record",
            project_dir=project_dir,
            contract=contract,
            session_id=session_id,
            reason="Session record must target the active governed session.",
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
        file_refs=_dedupe_strs(
            list((latest_verification or {}).get("file_refs", []))
            or list((latest_verification or {}).get("evidence_refs", []))
        ),
        module_refs=_dedupe_strs(list((latest_verification or {}).get("module_refs", []))),
        verification_id=latest_verification_id,
        keywords=_record_keywords(
            task,
            changes,
            decisions,
            risks,
            " ".join(list((latest_verification or {}).get("file_refs", []))),
            " ".join(list((latest_verification or {}).get("module_refs", []))),
        ),
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
        session["verification_id"] = latest_verification_id
        session["file_refs"] = _dedupe_strs(
            list((latest_verification or {}).get("file_refs", []))
            or list((latest_verification or {}).get("evidence_refs", []))
        )
        session["module_refs"] = _dedupe_strs(list((latest_verification or {}).get("module_refs", [])))
        session["keywords"] = _record_keywords(
            task,
            changes,
            decisions,
            risks,
            " ".join(session.get("file_refs", [])),
            " ".join(session.get("module_refs", [])),
        )
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
            "next_step": "haxaml_expect_sync",
            "lifecycle": _lifecycle_hint(
                tool="haxaml_session_record",
                phase="record",
                depends_on=["haxaml_session_verify"],
                preferred_next="haxaml_expect_sync",
                allowed_next=["haxaml_expect_sync"],
            ),
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

    sm, state, state_err = _load_state_or_error("haxaml_expect_sync", project_dir)
    if state_err:
        return state_err
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
            "next_step": "haxaml_guidance",
            "lifecycle": _lifecycle_hint(
                tool="haxaml_expect_sync",
                phase="sync",
                depends_on=["haxaml_session_record"],
                preferred_next="haxaml_guidance",
                allowed_next=["haxaml_guidance"],
            ),
        },
        warnings=warnings,
        detail=detail_mode,
    )
