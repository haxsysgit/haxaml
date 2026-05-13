"""Write-oriented execution services.

These helpers own the pieces that mutate ``acts.yaml``:

- opening a run by setting the active task
- recording a finished run
- triggering archival when hot history grows too large

Keeping these writes separate from preflight logic makes the governed workflow
easier to trace and safer to evolve.
"""

from __future__ import annotations

from typing import Optional

from haxaml.context import build_context, count_tokens
from haxaml.services.execution_models import RunResult
from haxaml.services.execution_preflight import (
    ExecutionPaths,
    run_preflight,
    state_manager_for,
)
from haxaml.state_manager import StateError


def start_execution_run(
    paths: ExecutionPaths,
    task: str,
    description: str = "",
    assignee: str = "builder",
) -> RunResult:
    """Open a new active task after preflight succeeds."""

    result = RunResult(task=task)
    preflight = run_preflight(paths)
    if not preflight.ready:
        result.result = "failed"
        result.errors = preflight.errors
        return result

    state_manager = state_manager_for(paths)
    if state_manager:
        try:
            current_state = state_manager.read()
            active = current_state.get("active_task", {})
            if active and active.get("name") not in ("none", ""):
                result.warnings.append(f"Overwriting active task: {active.get('name')}")
            state_manager.set_active_task(task, description, assignee)
        except StateError as exc:
            result.errors.append(f"State error: {exc}")
            result.result = "failed"
            return result

    result.result = "pending"
    return result


def finish_execution_run(
    paths: ExecutionPaths,
    task: str,
    result: str = "success",
    changes: str = "",
    decisions: str = "",
    risks: str = "",
    summary: str = "",
    auto_compact: bool = True,
    file_refs: Optional[list[str]] = None,
    module_refs: Optional[list[str]] = None,
    verification_id: str = "",
    keywords: Optional[list[str]] = None,
    compact_threshold: int = 10,
) -> RunResult:
    """Record a completed run and update hot/archive state.

    ``compact_threshold`` is kept for compatibility with the old signature even
    though archival policy is now controlled by ``StateManager.archive_on_record``.
    """

    del compact_threshold

    run_result = RunResult(
        task=task,
        result=result,
        changes=changes,
        decisions=decisions,
        risks=risks,
    )

    state_manager = state_manager_for(paths)
    if not state_manager:
        run_result.errors.append("No state manager — acts.yaml not found")
        return run_result

    try:
        run_id = state_manager.record_run(
            task=task,
            result=result,
            changes=changes,
            decisions=decisions,
            risks=risks,
            file_refs=file_refs,
            module_refs=module_refs,
            verification_id=verification_id,
            keywords=keywords,
        )
        run_result.run_id = run_id

        state_manager.complete_task(result=result, summary=summary or changes)

        if auto_compact:
            archive_result = state_manager.archive_on_record()
            archived = archive_result["archived"]
            if any(int(archived.get(kind, 0) or 0) > 0 for kind in ("runs", "sessions", "verifications")):
                run_result.warnings.append(
                    "Auto-archived cold history: "
                    f"{archived['runs']} run(s), "
                    f"{archived['sessions']} session(s), "
                    f"{archived['verifications']} verification(s)."
                )

        # Token count is recomputed from the full context after the write so
        # callers can observe how much governed state the project now carries.
        context_text = build_context(str(paths.project_dir))
        run_result.token_count = count_tokens(context_text)

    except StateError as exc:
        run_result.errors.append(f"State error: {exc}")
        if run_result.result != "failed":
            run_result.result = "partial"

    return run_result

