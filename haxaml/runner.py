"""Execution loop runner — FRAME → task → execute → validate → acts update.

This is the core workflow engine that ties everything together.
It implements the controlled execution loop from build.md Phase 5.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import yaml

from haxaml.validator import validate_facts, validate_acts, detect_missing_facts_fields, load_yaml
from haxaml.state_manager import StateManager, StateError
from haxaml.context import build_context, count_tokens
from haxaml.map_policy import evaluate_map_complexity, map_complexity_issues
from haxaml.paths import resolve_frame_file


@dataclass
class RunResult:
    """Result of a single execution run."""
    run_id: str = ""
    task: str = ""
    result: str = "pending"  # success, partial, failed
    changes: str = ""
    decisions: str = ""
    risks: str = ""
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    token_count: int = 0


@dataclass
class PreflightResult:
    """Result of pre-execution validation."""
    ready: bool = True
    facts_valid: bool = False
    acts_valid: bool = False
    facts_complete: bool = False
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    context_tokens: int = 0


class ExecutionRunner:
    """Manages the full execution loop for a Haxaml project."""

    def __init__(self, project_dir: str):
        self.project_dir = Path(project_dir).resolve()
        self.facts_path = resolve_frame_file(self.project_dir, "facts.yaml") or (self.project_dir / ".haxaml" / "facts.yaml")
        self.acts_path = resolve_frame_file(self.project_dir, "acts.yaml") or (self.project_dir / ".haxaml" / "acts.yaml")

        if not self.facts_path.exists():
            raise FileNotFoundError(f"facts.yaml not found at {self.project_dir}")

    @property
    def state_manager(self) -> Optional[StateManager]:
        if self.acts_path.exists():
            return StateManager(str(self.acts_path))
        return None

    def preflight(self) -> PreflightResult:
        """Phase 0: Validate everything before execution.

        Checks:
        - facts.yaml exists and is valid
        - acts.yaml exists and is valid
        - facts are complete (no blocking unresolved items)
        - context fits within token budget
        """
        result = PreflightResult()

        facts_errors = validate_facts(str(self.facts_path))
        if facts_errors:
            result.facts_valid = False
            result.ready = False
            result.errors.extend([f"facts: {e}" for e in facts_errors])
        else:
            result.facts_valid = True

        if self.acts_path.exists():
            acts_errors = validate_acts(str(self.acts_path))
            if acts_errors:
                result.acts_valid = False
                result.ready = False
                result.errors.extend([f"acts: {e}" for e in acts_errors])
            else:
                result.acts_valid = True
        else:
            result.acts_valid = False
            result.warnings.append("acts.yaml not found — will be created on first run")

        if result.facts_valid:
            missing = detect_missing_facts_fields(str(self.facts_path))
            blocking = [m for m in missing if "BLOCKING" in m]
            non_blocking = [m for m in missing if "BLOCKING" not in m]

            if blocking:
                result.facts_complete = False
                result.ready = False
                result.errors.extend(blocking)
            else:
                result.facts_complete = True

            if non_blocking:
                result.warnings.extend(non_blocking)

        map_assessment = evaluate_map_complexity(self.project_dir)
        map_errors, map_warnings = map_complexity_issues(map_assessment)
        if map_errors:
            result.ready = False
            result.errors.extend([f"map: {e}" for e in map_errors])
        if map_warnings:
            result.warnings.extend([f"map: {w}" for w in map_warnings])

        ctx = build_context(str(self.project_dir))
        result.context_tokens = count_tokens(ctx)
        if result.context_tokens > 8000:
            result.warnings.append(
                f"Context is {result.context_tokens} tokens — consider reducing for smaller models"
            )

        return result

    def prepare_context(self, task: Optional[str] = None,
                        include_state: bool = True) -> dict:
        """Prepare structured context for an agent task.

        Returns a dict with brain summary, state summary, task info,
        and token count. This is what an agent receives at task start.
        """
        facts = load_yaml(str(self.facts_path))
        context = {
            "facts": {
                "project": facts.get("identity", {}).get("name", "unknown"),
                "purpose": facts.get("goal", {}).get("purpose", ""),
                "scope": facts.get("goal", {}).get("scope", ""),
                "stack": facts.get("stack", {}),
                "architecture": facts.get("architecture", {}),
                "database": facts.get("database", {}),
                "constraints": facts.get("constraints", []),
            },
            "task": task or "No specific task assigned",
        }

        if include_state and self.acts_path.exists():
            state = load_yaml(str(self.acts_path))
            context["state"] = {
                "phase": state.get("current_phase", "unknown"),
                "active_task": state.get("active_task", {}),
                "blocked": state.get("blocked_tasks", []),
                "recent_decisions": (state.get("decisions", []) or [])[-3:],
                "unresolved": state.get("unresolved_dependencies", []),
            }

        ctx_text = yaml.dump(context, default_flow_style=False)
        context["_meta"] = {
            "token_count": count_tokens(ctx_text),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        return context

    def start_run(self, task: str, description: str = "",
                  assignee: str = "builder") -> RunResult:
        """Begin a new execution run.

        Sets the active task and prepares for execution.
        """
        result = RunResult(task=task)

        preflight = self.preflight()
        if not preflight.ready:
            result.result = "failed"
            result.errors = preflight.errors
            return result

        sm = self.state_manager
        if sm:
            try:
                current_state = sm.read()
                active = current_state.get("active_task", {})
                if active and active.get("name") not in ("none", ""):
                    result.warnings.append(
                        f"Overwriting active task: {active.get('name')}"
                    )
                sm.set_active_task(task, description, assignee)
            except StateError as e:
                result.errors.append(f"State error: {e}")
                result.result = "failed"
                return result

        result.result = "pending"
        return result

    def finish_run(self, task: str, result: str = "success",
                   changes: str = "", decisions: str = "",
                   risks: str = "", summary: str = "",
                   auto_compact: bool = True,
                   compact_threshold: int = 10) -> RunResult:
        """Complete an execution run.

        Records the run, completes the task, and optionally compacts state.
        """
        run_result = RunResult(task=task, result=result, changes=changes,
                               decisions=decisions, risks=risks)

        sm = self.state_manager
        if not sm:
            run_result.errors.append("No state manager — acts.yaml not found")
            return run_result

        try:
            run_id = sm.record_run(
                task=task, result=result, changes=changes,
                decisions=decisions, risks=risks
            )
            run_result.run_id = run_id

            sm.complete_task(result=result, summary=summary or changes)

            if auto_compact:
                state = sm.read()
                run_count = len(state.get("runs", []))
                if run_count > compact_threshold:
                    compact_result = sm.compact(keep_recent=5)
                    run_result.warnings.append(
                        f"Auto-compacted: {compact_result['compacted']} runs archived"
                    )

            ctx = build_context(str(self.project_dir))
            run_result.token_count = count_tokens(ctx)

        except StateError as e:
            run_result.errors.append(f"State error: {e}")
            if run_result.result != "failed":
                run_result.result = "partial"

        return run_result

    def get_project_health(self) -> dict:
        """Get overall project health report."""
        preflight = self.preflight()

        health = {
            "project": "unknown",
            "ready": preflight.ready,
            "facts_valid": preflight.facts_valid,
            "acts_valid": preflight.acts_valid,
            "facts_complete": preflight.facts_complete,
            "context_tokens": preflight.context_tokens,
            "errors": preflight.errors,
            "warnings": preflight.warnings,
        }

        facts = load_yaml(str(self.facts_path))
        health["project"] = facts.get("identity", {}).get("name", "unknown")

        sm = self.state_manager
        if sm:
            stats = sm.get_stats()
            health.update({
                "phase": stats["current_phase"],
                "active_task": stats["active_task"],
                "completed_tasks": stats["completed_count"],
                "blocked_tasks": stats["blocked_count"],
                "total_runs": stats["run_count"] + stats["total_runs_compacted"],
                "state_size_bytes": stats["file_size_bytes"],
            })

        return health
