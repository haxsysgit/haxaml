"""MCP benchmark tools for Haxaml."""

from haxaml.mcp.base import *

WORKFLOW_BENCHMARK_TASK = "update lifecycle guidance docs"
WORKFLOW_BENCHMARK_DESCRIPTION = "workflow benchmark profile"


def _benchmark_call_entry(index: int, tool: str, detail: str, result: dict, elapsed_ms: float) -> dict[str, Any]:
    data = result.get("data") if isinstance(result.get("data"), dict) else {}
    message = str(data.get("message", ""))
    payload_text = json.dumps(data, ensure_ascii=False, sort_keys=True)
    normalized_payload = _normalize_dynamic_text(payload_text)
    normalized_message = _normalize_dynamic_text(message)
    envelope = {"jsonrpc": "2.0", "id": index, "result": result}
    envelope_text = _normalize_dynamic_text(json.dumps(envelope, ensure_ascii=False, sort_keys=True))
    return {
        "call_index": index,
        "tool": tool,
        "detail_mode": detail,
        "ok": bool(result.get("ok")),
        "elapsed_ms": round(elapsed_ms, 2),
        "payload_tokens": count_tokens(normalized_payload),
        "message_tokens": count_tokens(normalized_message) if normalized_message else 0,
        "envelope_tokens": count_tokens(envelope_text),
    }


def _benchmark_profile_steps(name: str) -> list[str]:
    if name == "essential_short":
        return [
            "haxaml_about",
            "haxaml_guidance",
            "haxaml_prebuild",
            "haxaml_context_pack",
            "haxaml_session_verify",
            "haxaml_session_record",
            "haxaml_expect_sync",
        ]
    if name == "expanded_short":
        return [
            "haxaml_about",
            "haxaml_guidance",
            "haxaml_prebuild",
            "haxaml_context_pack",
            "haxaml_health",
            "haxaml_needs",
            "haxaml_session_verify",
            "haxaml_session_record",
            "haxaml_expect_sync",
            "haxaml_reconcile",
            "haxaml_state_show",
        ]
    if name == "essential_full":
        return [
            "haxaml_about",
            "haxaml_guidance",
            "haxaml_prebuild",
            "haxaml_context_pack",
            "haxaml_session_verify",
            "haxaml_session_record",
            "haxaml_expect_sync",
        ]
    raise ValueError(f"Unknown workflow benchmark profile: {name}")




def _benchmark_tool_registry() -> dict[str, Any]:
    from haxaml.mcp import tools_frame, tools_lifecycle, tools_ops, tools_prebuild

    return {
        "haxaml_about": tools_lifecycle.haxaml_about,
        "haxaml_guidance": tools_lifecycle.haxaml_guidance,
        "haxaml_prebuild": tools_prebuild.haxaml_prebuild,
        "haxaml_context_pack": tools_lifecycle.haxaml_context_pack,
        "haxaml_session_verify": tools_lifecycle.haxaml_session_verify,
        "haxaml_session_record": tools_lifecycle.haxaml_session_record,
        "haxaml_expect_sync": tools_lifecycle.haxaml_expect_sync,
        "haxaml_health": tools_frame.haxaml_health,
        "haxaml_needs": tools_ops.haxaml_needs,
        "haxaml_reconcile": tools_ops.haxaml_reconcile,
        "haxaml_state_show": tools_ops.haxaml_state_show,
    }

def _benchmark_run_profile(project_dir: str, name: str, detail: str) -> dict[str, Any]:
    session_id = ""
    calls: list[dict[str, Any]] = []
    payload_total = 0
    envelope_total = 0
    elapsed_total = 0.0

    for idx, tool_name in enumerate(_benchmark_profile_steps(name), start=1):
        common = {"project_dir": project_dir, "detail": detail}
        if tool_name == "haxaml_about":
            kwargs = common
        elif tool_name == "haxaml_guidance":
            kwargs = {"task": WORKFLOW_BENCHMARK_TASK, **common}
        elif tool_name == "haxaml_prebuild":
            kwargs = {
                "task": WORKFLOW_BENCHMARK_TASK,
                "description": WORKFLOW_BENCHMARK_DESCRIPTION,
                **common,
            }
        elif tool_name == "haxaml_context_pack":
            kwargs = {
                "task": WORKFLOW_BENCHMARK_TASK,
                "pack": "balanced",
                "include_state": True,
                "session_id": session_id,
                **common,
            }
        elif tool_name == "haxaml_session_verify":
            kwargs = {
                "task": WORKFLOW_BENCHMARK_TASK,
                "session_id": session_id,
                "inspected_context": [
                    ".haxaml/facts.yaml",
                    ".haxaml/rules.yaml",
                    ".haxaml/acts.yaml",
                    ".haxaml/expect.yaml",
                ],
                "changed_files": [],
                "summary": "workflow benchmark profiling",
                **common,
            }
        elif tool_name == "haxaml_session_record":
            kwargs = {
                "task": WORKFLOW_BENCHMARK_TASK,
                "session_id": session_id,
                "result": "success",
                "changes": "Captured workflow benchmark metrics.",
                "decisions": "Use lean baseline as default guidance.",
                "risks": "Transport numbers include envelope estimates only.",
                **common,
            }
        elif tool_name == "haxaml_expect_sync":
            kwargs = common
        else:
            kwargs = common

        fn = _benchmark_tool_registry()[tool_name]
        started = time.perf_counter()
        result = fn(**kwargs)
        elapsed = (time.perf_counter() - started) * 1000
        entry = _benchmark_call_entry(idx, tool_name, detail, result, elapsed)
        calls.append(entry)
        payload_total += entry["payload_tokens"]
        envelope_total += entry["envelope_tokens"]
        elapsed_total += entry["elapsed_ms"]

        if tool_name == "haxaml_prebuild":
            session_id = str((result.get("data") or {}).get("session_id", ""))
        if not result.get("ok"):
            break

    overhead_tokens = envelope_total - payload_total
    overhead_pct = round((overhead_tokens / payload_total) * 100, 2) if payload_total > 0 else 0.0
    return {
        "name": name,
        "detail_mode": detail,
        "ok": all(call["ok"] for call in calls),
        "call_count": len(calls),
        "payload_tokens": payload_total,
        "envelope_tokens": envelope_total,
        "transport_overhead_tokens": overhead_tokens,
        "transport_overhead_pct": overhead_pct,
        "elapsed_ms": round(elapsed_total, 2),
        "calls": calls,
    }


def _benchmark_workflow_mode() -> dict[str, Any]:
    import tempfile
    from haxaml.mcp import tools_frame

    guardrails = {
        "essential_short_max_payload_tokens": 2100,
        "expanded_short_max_payload_tokens": 2600,
        "essential_full_max_payload_tokens": 3500,
    }
    def _run_isolated_profile(name: str, detail: str) -> dict[str, Any]:
        with tempfile.TemporaryDirectory(prefix=f"haxaml-benchmark-workflow-{name}-") as td:
            project_dir = str(Path(td))
            init_result = tools_frame.haxaml_init(directory=project_dir, detail=DETAIL_SHORT)
            if not init_result.get("ok"):
                raise RuntimeError(f"workflow benchmark fixture init failed for {name}: {init_result}")
            return _benchmark_run_profile(project_dir, name, detail)

    profiles = {
        "essential_short": _run_isolated_profile("essential_short", DETAIL_SHORT),
        "expanded_short": _run_isolated_profile("expanded_short", DETAIL_SHORT),
        "essential_full": _run_isolated_profile("essential_full", DETAIL_FULL),
    }
    essential = profiles["essential_short"]["payload_tokens"]
    expanded = profiles["expanded_short"]["payload_tokens"]
    full = profiles["essential_full"]["payload_tokens"]
    comparisons = {
        "expanded_vs_essential": {
            "extra_tokens": expanded - essential,
            "pct_over_essential": round(((expanded - essential) / essential) * 100, 2) if essential else 0.0,
            "extra_calls": profiles["expanded_short"]["call_count"] - profiles["essential_short"]["call_count"],
        },
        "full_vs_essential": {
            "extra_tokens": full - essential,
            "pct_over_essential": round(((full - essential) / essential) * 100, 2) if essential else 0.0,
            "extra_calls": profiles["essential_full"]["call_count"] - profiles["essential_short"]["call_count"],
        },
    }
    transport = {
        name: {
            "payload_tokens": prof["payload_tokens"],
            "envelope_tokens": prof["envelope_tokens"],
            "overhead_tokens": prof["transport_overhead_tokens"],
            "overhead_pct": prof["transport_overhead_pct"],
        }
        for name, prof in profiles.items()
    }
    guardrail_results = {
        "essential_short_pass": profiles["essential_short"]["payload_tokens"] <= guardrails["essential_short_max_payload_tokens"],
        "expanded_short_pass": profiles["expanded_short"]["payload_tokens"] <= guardrails["expanded_short_max_payload_tokens"],
        "essential_full_pass": profiles["essential_full"]["payload_tokens"] <= guardrails["essential_full_max_payload_tokens"],
    }
    guardrail_results["all_pass"] = all(guardrail_results.values())
    return {
        "profiles": profiles,
        "comparisons": comparisons,
        "transport_overhead": transport,
        "guardrails": {"ceilings": guardrails, "results": guardrail_results},
    }


@mcp_app.tool()
def haxaml_benchmark(project_dir: str = ".", mode: str = "frame", detail: str = DETAIL_SHORT) -> dict:
    """Run token efficiency benchmarks on FRAME files."""
    detail_mode, detail_err = _normalize_detail("haxaml_benchmark", detail)
    if detail_err:
        return detail_err

    mode = str(mode or "frame").strip().lower()
    if mode not in {"frame", "workflow"}:
        return _err(
            "haxaml_benchmark",
            "invalid_mode",
            "Invalid benchmark mode. Use 'frame' or 'workflow'.",
            {"received": mode, "allowed": ["frame", "workflow"]},
        )

    from haxaml.benchmarks import format_benchmark_report

    p = Path(project_dir).resolve()
    if mode == "frame":
        facts_path = resolve_frame_file(p, "facts.yaml", "brain.yaml")
        if not facts_path:
            return _err("haxaml_benchmark", "missing_facts", "facts.yaml not found")
        report = format_benchmark_report(str(facts_path), project_dir)
        return _ok(
            "haxaml_benchmark",
            {"message": report, "mode": "frame"},
            detail=detail_mode,
        )

    try:
        workflow = _benchmark_workflow_mode()
    except Exception as exc:
        return _err("haxaml_benchmark", "workflow_benchmark_failed", str(exc))

    profiles = workflow["profiles"]
    message = (
        "Workflow benchmark complete.\n"
        f"essential_short={profiles['essential_short']['payload_tokens']} tokens, "
        f"expanded_short={profiles['expanded_short']['payload_tokens']} tokens, "
        f"essential_full={profiles['essential_full']['payload_tokens']} tokens."
    )
    return _ok(
        "haxaml_benchmark",
        {
            "message": message,
            "mode": "workflow",
            "profiles": profiles,
            "comparisons": workflow["comparisons"],
            "transport_overhead": workflow["transport_overhead"],
            "guardrails": workflow["guardrails"],
        },
        detail=detail_mode,
    )
