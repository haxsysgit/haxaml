"""Validation and read-only execution helpers.

The old ``ExecutionRunner`` used to own everything: file discovery, validation,
task context construction, and run recording. That made the lifecycle harder to
follow. This module keeps only the read-oriented parts:

- locate the FRAME files used by execution
- run preflight checks
- assemble lightweight task context
- derive a health report
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml

from haxaml.context import build_context, count_tokens
from haxaml.map_policy import evaluate_map_complexity, map_complexity_issues
from haxaml.paths import resolve_frame_file
from haxaml.services.execution_models import PreflightResult
from haxaml.state_manager import StateManager
from haxaml.utils import now_iso
from haxaml.validator import (
    detect_missing_facts_fields,
    load_yaml,
    validate_acts,
    validate_expect,
    validate_facts,
    validate_map,
    validate_rules,
)


@dataclass(frozen=True)
class ExecutionPaths:
    """Canonical file paths used by execution services for one project."""

    project_dir: Path
    facts_path: Path
    acts_path: Path
    rules_path: Path
    expect_path: Path
    map_path: Path


def resolve_execution_paths(project_dir: str) -> ExecutionPaths:
    """Resolve the FRAME files needed by execution services.

    We fail early when ``facts.yaml`` is missing because every execution path
    depends on it. ``acts.yaml`` may be missing on first run, so we resolve the
    expected path without requiring the file to exist yet.
    """

    root = Path(project_dir).resolve()
    facts_path = resolve_frame_file(root, "facts.yaml") or (root / ".haxaml" / "facts.yaml")
    acts_path = resolve_frame_file(root, "acts.yaml") or (root / ".haxaml" / "acts.yaml")
    rules_path = resolve_frame_file(root, "rules.yaml") or (root / ".haxaml" / "rules.yaml")
    expect_path = resolve_frame_file(root, "expect.yaml") or (root / ".haxaml" / "expect.yaml")
    map_path = resolve_frame_file(root, "map.yaml") or (root / ".haxaml" / "map.yaml")

    if not facts_path.exists():
        raise FileNotFoundError(f"facts.yaml not found at {root}")

    return ExecutionPaths(
        project_dir=root,
        facts_path=facts_path,
        acts_path=acts_path,
        rules_path=rules_path,
        expect_path=expect_path,
        map_path=map_path,
    )


def state_manager_for(paths: ExecutionPaths) -> Optional[StateManager]:
    """Return a state manager only when acts storage already exists."""

    if paths.acts_path.exists():
        return StateManager(str(paths.acts_path))
    return None


def run_preflight(paths: ExecutionPaths) -> PreflightResult:
    """Validate FRAME state before a governed run starts.

    The checks stay intentionally conservative:
    - schemas must pass
    - facts must not have blocking unresolved gaps
    - map policy must not require a missing ``map.yaml``
    - the current full context should stay within a manageable token budget
    """

    result = PreflightResult()

    facts_errors = validate_facts(str(paths.facts_path))
    if facts_errors:
        result.facts_valid = False
        result.ready = False
        result.errors.extend([f"facts: {error}" for error in facts_errors])
    else:
        result.facts_valid = True

    if not paths.rules_path.exists():
        result.ready = False
        result.errors.append("rules: rules.yaml not found")
    else:
        rules_errors = validate_rules(str(paths.rules_path))
        if rules_errors:
            result.ready = False
            result.errors.extend([f"rules: {error}" for error in rules_errors])

    if not paths.expect_path.exists():
        result.ready = False
        result.errors.append("expect: expect.yaml not found")
    else:
        expect_errors = validate_expect(str(paths.expect_path))
        if expect_errors:
            result.ready = False
            result.errors.extend([f"expect: {error}" for error in expect_errors])

    if paths.acts_path.exists():
        acts_errors = validate_acts(str(paths.acts_path))
        if acts_errors:
            result.acts_valid = False
            result.ready = False
            result.errors.extend([f"acts: {error}" for error in acts_errors])
        else:
            result.acts_valid = True
    else:
        result.acts_valid = False
        result.warnings.append("acts.yaml not found — will be created on first run")

    if result.facts_valid:
        missing = detect_missing_facts_fields(str(paths.facts_path))
        blocking = [item for item in missing if "BLOCKING" in item]
        advisory = [item for item in missing if "BLOCKING" not in item]

        if blocking:
            result.facts_complete = False
            result.ready = False
            result.errors.extend(blocking)
        else:
            result.facts_complete = True

        result.warnings.extend(advisory)

    map_assessment = evaluate_map_complexity(paths.project_dir)
    if paths.map_path.exists():
        map_schema_errors = validate_map(str(paths.map_path))
        if map_schema_errors:
            result.ready = False
            result.errors.extend([f"map: {error}" for error in map_schema_errors])
    map_errors, map_warnings = map_complexity_issues(map_assessment)
    if map_errors:
        result.ready = False
        result.errors.extend([f"map: {error}" for error in map_errors])
    if map_warnings:
        result.warnings.extend([f"map: {warning}" for warning in map_warnings])

    context_text = build_context(str(paths.project_dir))
    result.context_tokens = count_tokens(context_text)
    if result.context_tokens > 8000:
        result.warnings.append(
            f"Context is {result.context_tokens} tokens — consider reducing for smaller models"
        )

    return result


def prepare_task_context(
    paths: ExecutionPaths,
    task: Optional[str] = None,
    include_state: bool = True,
) -> dict:
    """Build the compact task payload given to execution clients.

    This is intentionally smaller than the full ``context_pack`` output. It is
    just enough for tooling that wants a quick structured snapshot of facts and
    recent state without invoking the full governed retrieval flow.
    """

    facts = load_yaml(str(paths.facts_path))
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

    if include_state and paths.acts_path.exists():
        state = load_yaml(str(paths.acts_path))
        context["state"] = {
            "phase": state.get("current_phase", "unknown"),
            "active_task": state.get("active_task", {}),
            "blocked": state.get("blocked_tasks", []),
            "recent_decisions": (state.get("decisions", []) or [])[-3:],
            "unresolved": state.get("unresolved_dependencies", []),
        }

    # We token-count the serialized payload because that is what callers
    # effectively hand to a model or another tool boundary.
    context_text = yaml.dump(context, default_flow_style=False)
    context["_meta"] = {
        "token_count": count_tokens(context_text),
        "timestamp": now_iso(),
    }
    return context


def build_health_report(paths: ExecutionPaths) -> dict:
    """Summarize current execution readiness for status-style callers."""

    preflight = run_preflight(paths)
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

    facts = load_yaml(str(paths.facts_path))
    health["project"] = facts.get("identity", {}).get("name", "unknown")

    state_manager = state_manager_for(paths)
    if state_manager:
        stats = state_manager.get_stats()
        health.update(
            {
                "phase": stats["current_phase"],
                "active_task": stats["active_task"],
                "completed_tasks": stats["completed_count"],
                "blocked_tasks": stats["blocked_count"],
                "total_runs": stats["total_runs"],
                "archive_mode": stats["archive_mode"],
                "archived_runs": stats["archived_run_count"],
                "state_size_bytes": stats["file_size_bytes"],
            }
        )

    return health
