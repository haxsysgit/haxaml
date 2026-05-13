"""Compatibility facade for execution services.

Historically this module owned the full execution workflow. That made it a poor
fit for the current package shape because validation, task context assembly, and
run recording all changed for different reasons. The code now lives in
``haxaml.services.execution_*`` modules, while this class remains as the small
public facade consumed by MCP tools and tests.
"""

from __future__ import annotations

from typing import Optional

from haxaml.services.execution_models import PreflightResult, RunResult
from haxaml.services.execution_preflight import (
    build_health_report,
    prepare_task_context,
    resolve_execution_paths,
    run_preflight,
    state_manager_for,
)
from haxaml.services.execution_records import finish_execution_run, start_execution_run


class ExecutionRunner:
    """Thin object wrapper around the execution service layer."""

    def __init__(self, project_dir: str):
        self.paths = resolve_execution_paths(project_dir)
        self.project_dir = self.paths.project_dir
        self.facts_path = self.paths.facts_path
        self.acts_path = self.paths.acts_path

    @property
    def state_manager(self):
        """Expose state access for callers that still expect the old property."""

        return state_manager_for(self.paths)

    def preflight(self) -> PreflightResult:
        """Run read-only execution checks."""

        return run_preflight(self.paths)

    def prepare_context(self, task: Optional[str] = None, include_state: bool = True) -> dict:
        """Build the lightweight execution context payload."""

        return prepare_task_context(self.paths, task=task, include_state=include_state)

    def start_run(self, task: str, description: str = "", assignee: str = "builder") -> RunResult:
        """Mark a task active after preflight succeeds."""

        return start_execution_run(
            self.paths,
            task=task,
            description=description,
            assignee=assignee,
        )

    def finish_run(
        self,
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
        """Record a completed run through the write-oriented service."""

        return finish_execution_run(
            self.paths,
            task=task,
            result=result,
            changes=changes,
            decisions=decisions,
            risks=risks,
            summary=summary,
            auto_compact=auto_compact,
            file_refs=file_refs,
            module_refs=module_refs,
            verification_id=verification_id,
            keywords=keywords,
            compact_threshold=compact_threshold,
        )

    def get_project_health(self) -> dict:
        """Summarize project execution readiness and current state stats."""

        return build_health_report(self.paths)
