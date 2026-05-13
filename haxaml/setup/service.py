"""Transport-neutral setup planning and execution helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from haxaml.setup.doctor import run_setup_doctor
from haxaml.setup.planner import SetupPlan, build_setup_plan
from haxaml.setup.writer import apply_setup_plan


def plan_setup(
    *,
    project_dir: str | Path,
    scope: str = "project",
    target: str = "auto",
    mode: str = "auto",
    only: tuple[str, ...] | list[str] | None = None,
) -> SetupPlan:
    """Build a canonical setup plan."""
    return build_setup_plan(
        project_dir=project_dir,
        scope=scope,
        target=target,
        mode=mode,
        only=only,
    )


def apply_setup(
    *,
    project_dir: str | Path,
    scope: str = "project",
    target: str = "auto",
    mode: str = "auto",
    only: tuple[str, ...] | list[str] | None = None,
    force: bool = False,
) -> tuple[SetupPlan, dict[str, object]]:
    """Build and apply a setup plan."""
    plan = plan_setup(
        project_dir=project_dir,
        scope=scope,
        target=target,
        mode=mode,
        only=only,
    )
    return plan, apply_setup_plan(plan, force=force)


def setup_message(plan: SetupPlan, *, apply_result: dict[str, object] | None = None) -> str:
    """Render a concise human summary for a setup plan or apply result."""
    lines = [
        f"Mode: {plan.mode}",
        f"Scope: {plan.scope}",
        f"Targets: {', '.join(plan.selected_targets) if plan.selected_targets else '(none)'}",
    ]
    if plan.detected_targets:
        lines.append(f"Detected native targets: {', '.join(plan.detected_targets)}")
    if apply_result is None:
        lines.append(f"Planned files: {len(plan.planned_files)}")
    else:
        created = apply_result.get("created", [])
        updated = apply_result.get("updated", [])
        skipped = apply_result.get("skipped", [])
        lines.append(f"Created: {len(created)}")
        lines.append(f"Updated: {len(updated)}")
        if skipped:
            lines.append(f"Skipped: {len(skipped)}")
    if plan.manual_actions:
        lines.append(f"Manual actions: {len(plan.manual_actions)}")
    if plan.warnings:
        lines.extend(plan.warnings)
    return "\n".join(lines)


def setup_data(plan: SetupPlan, *, apply_result: dict[str, object] | None = None) -> dict[str, Any]:
    """Return the structured setup payload shared by CLI and MCP."""
    data = plan.to_dict()
    if apply_result is not None:
        data["apply_result"] = apply_result
    data["message"] = setup_message(plan, apply_result=apply_result)
    return data


def print_data(plan: SetupPlan) -> dict[str, Any]:
    """Return a setup payload with rendered file previews."""
    data = setup_data(plan)
    previews = []
    for item in data.get("planned_files", []):
        previews.append(f"=== {item['path']} ===\n{item['content']}".rstrip())
    data["message"] = "\n\n".join(previews) if previews else "No planned files."
    return data


def doctor_data(*, project_dir: str | Path) -> dict[str, Any]:
    """Return the canonical setup doctor report."""
    return run_setup_doctor(project_dir)
