"""Transport-neutral setup planning and execution helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from haxaml.setup.doctor import run_setup_doctor
from haxaml.setup.planner import SetupPlan, build_setup_plan
from haxaml.setup.workflow import run_workflow_check
from haxaml.setup.writer import apply_setup_plan


def plan_setup(
    *,
    project_dir: str | Path,
    scope: str = "project",
    target: str = "auto",
    targets: tuple[str, ...] | list[str] | None = None,
    mode: str = "auto",
    only: tuple[str, ...] | list[str] | None = None,
    with_workflow: bool = False,
) -> SetupPlan:
    """Build a canonical setup plan."""
    return build_setup_plan(
        project_dir=project_dir,
        scope=scope,
        target=target,
        targets=targets,
        mode=mode,
        only=only,
        with_workflow=with_workflow,
    )


def apply_setup(
    *,
    project_dir: str | Path,
    scope: str = "project",
    target: str = "auto",
    targets: tuple[str, ...] | list[str] | None = None,
    mode: str = "auto",
    only: tuple[str, ...] | list[str] | None = None,
    with_workflow: bool = False,
    force: bool = False,
) -> tuple[SetupPlan, dict[str, object]]:
    """Build and apply a setup plan."""
    plan = plan_setup(
        project_dir=project_dir,
        scope=scope,
        target=target,
        targets=targets,
        mode=mode,
        only=only,
        with_workflow=with_workflow,
    )
    return plan, apply_setup_plan(plan, force=force)


def _styled(text: str, ansi: str | None, color: bool) -> str:
    if not color or not ansi:
        return text
    return f"\033[{ansi}m{text}\033[0m"


def _section(title: str, color: bool, ansi: str | None = None) -> str:
    return _styled(title, ansi, color)


def _item_lines(item: dict[str, object]) -> list[str]:
    path = str(item.get("path") or "(no path)")
    lines = [f"- {path}"]
    managed_key_path = str(item.get("managed_key_path") or "")
    if managed_key_path:
        lines.append(f"  key: {managed_key_path}")
    reason = str(item.get("action_reason") or item.get("reason") or item.get("note") or "").strip()
    if reason:
        lines.append(f"  reason: {reason}")
    preview = str(item.get("preview") or "").rstrip()
    if preview:
        lines.append("  preview:")
        lines.extend([f"    {line}" for line in preview.splitlines()])
    candidates = [str(candidate) for candidate in item.get("candidate_targets", []) or []]
    if candidates:
        lines.append(f"  candidates: {', '.join(candidates)}")
    return lines


def _render_section(title: str, items: list[dict[str, object]], *, color: bool, ansi: str | None = None) -> list[str]:
    lines = [_section(title, color, ansi)]
    if not items:
        lines.append("- none")
        return lines
    for item in items:
        lines.extend(_item_lines(item))
    return lines


def setup_message(plan: SetupPlan, *, apply_result: dict[str, object] | None = None, color: bool = False) -> str:
    """Render a path-first human summary for a setup plan or apply result."""
    lines = [
        f"Mode: {plan.mode}",
        f"Scope: {plan.scope}",
        f"Targets: {', '.join(plan.selected_targets) if plan.selected_targets else '(none)'}",
    ]
    if plan.workflow_enabled:
        lines.append("Workflow adaptation: enabled")
    if plan.strong_detected_targets:
        lines.append(f"Strong target evidence: {', '.join(plan.strong_detected_targets)}")
    if plan.weak_detected_targets:
        lines.append(f"Weak target evidence: {', '.join(plan.weak_detected_targets)}")
    if plan.warnings:
        lines.extend(plan.warnings)
    lines.append("")

    if apply_result is None:
        planned: list[dict[str, object]] = [item.to_dict() for item in plan.planned_files]
        by_action = {
            "Create": [item for item in planned if str(item.get("action")) == "create"],
            "Update": [item for item in planned if str(item.get("action")) in {"update", "append_pointer"}],
            "Merge": [item for item in planned if str(item.get("action")) == "merge"],
            "Skip": [item for item in planned if str(item.get("action")) == "skip"],
        }
        lines.extend(_render_section("Planned Creates", by_action["Create"], color=color, ansi="32"))
        lines.append("")
        lines.extend(_render_section("Planned Updates", by_action["Update"], color=color, ansi="33"))
        lines.append("")
        lines.extend(_render_section("Planned Merges", by_action["Merge"], color=color, ansi="36"))
        if by_action["Skip"]:
            lines.append("")
            lines.extend(_render_section("Planned Skips", by_action["Skip"], color=color, ansi="90"))
    else:
        result_items = list(apply_result.get("items", []))
        created = [item for item in result_items if str(item.get("status")) == "created"]
        updated = [item for item in result_items if str(item.get("status")) == "updated"]
        merged = [item for item in result_items if str(item.get("status")) == "merged"]
        skipped = [item for item in result_items if str(item.get("status")) == "skipped"]
        lines.extend(_render_section("Created", created, color=color, ansi="32"))
        lines.append("")
        lines.extend(_render_section("Updated", updated, color=color, ansi="33"))
        lines.append("")
        lines.extend(_render_section("Merged", merged, color=color, ansi="36"))
        lines.append("")
        lines.extend(_render_section("Skipped", skipped, color=color, ansi="90"))
    if plan.manual_actions:
        lines.append("")
        lines.extend(_render_section("Manual Actions", [item.to_dict() for item in plan.manual_actions], color=color, ansi="35"))
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


def workflow_check_data(
    *,
    project_dir: str | Path,
    target: str = "auto",
    context: str = "entry",
    signal: str = "",
    strict: bool = False,
) -> dict[str, Any]:
    """Return the canonical workflow check report."""
    return run_workflow_check(
        project_dir=project_dir,
        target=target,
        context=context,
        signal=signal,
        strict=strict,
    )
