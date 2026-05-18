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


def _selection_source_text(selection_source: str) -> str:
    mapping = {
        "explicit_targets": "explicit --targets selection",
        "explicit_target": "explicit --target selection",
        "auto_strong_detection": "single strong native provider detection",
        "generic_fallback": "generic fallback",
    }
    return mapping.get(selection_source, selection_source or "auto")


def _review_sections(plan: SetupPlan, *, apply_result: dict[str, object] | None = None) -> list[dict[str, object]]:
    planned: list[dict[str, object]]
    if apply_result is None:
        planned = [item.to_dict() for item in plan.planned_files]
        creates = [item for item in planned if str(item.get("action")) == "create"]
        updates = [item for item in planned if str(item.get("action")) in {"update", "append_pointer"}]
        merges = [item for item in planned if str(item.get("action")) == "merge"]
        skips = [item for item in planned if str(item.get("action")) == "skip"]
    else:
        result_items = list(apply_result.get("items", []))
        creates = [item for item in result_items if str(item.get("status")) == "created"]
        updates = [item for item in result_items if str(item.get("status")) == "updated"]
        merges = [item for item in result_items if str(item.get("status")) == "merged"]
        skips = [item for item in result_items if str(item.get("status")) == "skipped"]

    workflow_items = [
        item.to_dict() if hasattr(item, "to_dict") else item
        for item in (plan.planned_files if apply_result is None else list(apply_result.get("items", [])))
        if str((item.to_dict() if hasattr(item, "to_dict") else item).get("kind")) == "workflow"
    ]
    sections = [
        {
            "title": "Selection",
            "items": [
                {
                    "path": f"targets: {', '.join(plan.selected_targets) if plan.selected_targets else '(none)'}",
                    "reason": f"selection source: {_selection_source_text(plan.selection_source)}",
                }
            ],
        },
        {"title": "Created" if apply_result is not None else "Planned Creates", "items": creates},
        {"title": "Updated" if apply_result is not None else "Planned Updates", "items": updates},
        {"title": "Merged" if apply_result is not None else "Planned Merges", "items": merges},
        {"title": "Skipped" if apply_result is not None else "Planned Skips", "items": skips},
        {"title": "Workflow Additions", "items": workflow_items},
        {"title": "Manual Actions", "items": [item.to_dict() for item in plan.manual_actions]},
    ]
    return sections


def _setup_command_preview(plan: SetupPlan) -> str:
    parts = ["haxaml", "setup"]
    if plan.scope != "project":
        parts.extend(["--scope", plan.scope])
    if plan.requested_targets:
        for item in plan.requested_targets:
            parts.extend(["--targets", item])
    elif plan.requested_target != "auto":
        parts.extend(["--target", plan.requested_target])
    if plan.mode != "auto":
        parts.extend(["--mode", plan.mode])
    if plan.workflow_enabled:
        parts.append("--with-workflow")
    return " ".join(parts)


def _next_steps(plan: SetupPlan, *, apply_result: dict[str, object] | None = None) -> list[str]:
    steps: list[str] = []
    if apply_result is None:
        steps.append(f"Run `{_setup_command_preview(plan)}` to apply this plan.")
    else:
        steps.append("Run `haxaml setup doctor` to inspect managed setup state.")
    if plan.workflow_enabled:
        target = plan.selected_targets[0] if plan.selected_targets else "auto"
        steps.append(f"Run `haxaml workflow check --target {target}` to verify workflow adapters.")
    if plan.scope == "project":
        steps.append("Fill in FRAME files as needed, then run `haxaml validate`.")
    return list(dict.fromkeys(steps))


def _write_policy_summary() -> dict[str, object]:
    return {
        "mode": "preserve_and_repair",
        "default_behavior": "Existing populated FRAME files and unmanaged files are preserved by default.",
        "repairs": "Missing Haxaml-managed files are repaired on rerun.",
        "force": "Pass --force to replace existing managed outputs intentionally.",
    }


def setup_message(plan: SetupPlan, *, apply_result: dict[str, object] | None = None, color: bool = False) -> str:
    """Render a path-first human summary for a setup plan or apply result."""
    lines = [
        f"Mode: {plan.mode}",
        f"Scope: {plan.scope}",
        f"Targets: {', '.join(plan.selected_targets) if plan.selected_targets else '(none)'}",
        f"Selection source: {_selection_source_text(plan.selection_source)}",
    ]
    if plan.requested_targets:
        lines.append(f"Requested targets: {', '.join(plan.requested_targets)}")
    if plan.workflow_enabled:
        lines.append("Workflow adaptation: enabled")
    if plan.strong_detected_targets:
        lines.append(f"Strong target evidence: {', '.join(plan.strong_detected_targets)}")
    if plan.weak_detected_targets:
        lines.append(f"Weak target evidence: {', '.join(plan.weak_detected_targets)}")
    if plan.warnings:
        lines.extend(plan.warnings)
    lines.append("")

    for section in _review_sections(plan, apply_result=apply_result):
        title = str(section.get("title") or "")
        items = [item for item in section.get("items", []) if isinstance(item, dict)]
        if not title:
            continue
        ansi = None
        if "Create" in title:
            ansi = "32"
        elif "Update" in title:
            ansi = "33"
        elif "Merge" in title:
            ansi = "36"
        elif "Skip" in title:
            ansi = "90"
        elif "Manual" in title:
            ansi = "35"
        lines.extend(_render_section(title, items, color=color, ansi=ansi))
        lines.append("")
    lines.extend(_render_section("Next Steps", [{"path": step} for step in _next_steps(plan, apply_result=apply_result)], color=color, ansi="34"))
    return "\n".join(lines)


def setup_data(plan: SetupPlan, *, apply_result: dict[str, object] | None = None) -> dict[str, Any]:
    """Return the structured setup payload shared by CLI and MCP."""
    data = plan.to_dict()
    if apply_result is not None:
        data["apply_result"] = apply_result
    data["review_sections"] = _review_sections(plan, apply_result=apply_result)
    data["next_steps"] = _next_steps(plan, apply_result=apply_result)
    data["write_policy"] = _write_policy_summary()
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
