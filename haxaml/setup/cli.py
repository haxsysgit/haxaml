"""CLI-facing wrappers for canonical setup service operations."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from haxaml.setup.service import (
    apply_setup,
    doctor_data,
    plan_setup,
    print_data,
    setup_data,
    setup_message,
    workflow_check_data,
)


def _ok(tool: str, data: dict[str, Any], warnings: list[str] | None = None) -> dict[str, Any]:
    return {"ok": True, "tool": tool, "data": data, "warnings": warnings or [], "error": None}


def _err(tool: str, code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "ok": False,
        "tool": tool,
        "data": {},
        "warnings": [],
        "error": {"code": code, "message": message, "details": details or {}},
    }


def _format_doctor_item(item: dict[str, Any]) -> str:
    path = str(item.get("path") or "(no path)")
    target = str(item.get("target") or "unknown")
    category = str(item.get("category") or item.get("kind") or "setup")
    label = str(item.get("label") or "")
    reason = str(item.get("reason") or "")
    repair_hint = str(item.get("repair_hint") or "")

    metadata = [f"target={target}", category]
    if label:
        metadata.append(label)

    line = f"- {path} ({', '.join(metadata)})"
    if reason:
        line += f" - {reason}"
    if repair_hint:
        line += f" | hint: {repair_hint}"
    return line


def _format_doctor_manual_action(item: dict[str, Any]) -> str:
    target = str(item.get("target") or "unknown")
    path = str(item.get("path") or target)
    category = str(item.get("category") or item.get("kind") or "setup")
    label = str(item.get("label") or "")
    reason = str(item.get("reason") or "")
    repair_hint = str(item.get("repair_hint") or "")

    metadata = [f"target={target}", category]
    if label:
        metadata.append(label)

    line = f"- {path} ({', '.join(metadata)})"
    if reason:
        line += f": {reason}"
    if repair_hint and repair_hint != reason:
        line += f" | hint: {repair_hint}"
    return line


def setup_plan(
    *,
    project_dir: str | Path,
    scope: str = "project",
    target: str = "auto",
    targets: tuple[str, ...] | list[str] | None = None,
    mode: str = "auto",
    only: tuple[str, ...] | list[str] | None = None,
    with_workflow: bool = False,
    output_format: str = "text",
    color: bool = False,
) -> dict[str, Any]:
    try:
        plan = plan_setup(
            project_dir=project_dir,
            scope=scope,
            target=target,
            targets=targets,
            mode=mode,
            only=only,
            with_workflow=with_workflow,
        )
    except (KeyError, ValueError) as exc:
        return _err("haxaml_setup", "invalid_setup_args", str(exc))

    data = setup_data(plan)
    if output_format == "text":
        data["message"] = setup_message(plan, color=color)
    if output_format == "json":
        data["message"] = json.dumps(data, indent=2, sort_keys=True)
    return _ok("haxaml_setup", data, warnings=plan.warnings)


def execute_setup(
    *,
    project_dir: str | Path,
    scope: str = "project",
    target: str = "auto",
    targets: tuple[str, ...] | list[str] | None = None,
    mode: str = "auto",
    only: tuple[str, ...] | list[str] | None = None,
    with_workflow: bool = False,
    force: bool = False,
    dry_run: bool = False,
    output_format: str = "text",
    color: bool = False,
) -> dict[str, Any]:
    try:
        if dry_run:
            plan = plan_setup(
                project_dir=project_dir,
                scope=scope,
                target=target,
                targets=targets,
                mode=mode,
                only=only,
                with_workflow=with_workflow,
            )
            apply_result = None
        else:
            plan, apply_result = apply_setup(
                project_dir=project_dir,
                scope=scope,
                target=target,
                targets=targets,
                mode=mode,
                only=only,
                with_workflow=with_workflow,
                force=force,
            )
    except (KeyError, ValueError) as exc:
        return _err("haxaml_setup", "invalid_setup_args", str(exc))

    data = setup_data(plan, apply_result=apply_result)
    if output_format == "text":
        data["message"] = setup_message(plan, apply_result=apply_result, color=color)
    if output_format == "json":
        data["message"] = json.dumps(data, indent=2, sort_keys=True)
    return _ok("haxaml_setup", data, warnings=plan.warnings)


def print_plan(
    *,
    project_dir: str | Path,
    scope: str = "project",
    target: str = "auto",
    targets: tuple[str, ...] | list[str] | None = None,
    mode: str = "auto",
    only: tuple[str, ...] | list[str] | None = None,
    with_workflow: bool = False,
    output_format: str = "text",
) -> dict[str, Any]:
    try:
        plan = plan_setup(
            project_dir=project_dir,
            scope=scope,
            target=target,
            targets=targets,
            mode=mode,
            only=only,
            with_workflow=with_workflow,
        )
    except (KeyError, ValueError) as exc:
        return _err("haxaml_setup", "invalid_setup_args", str(exc))

    data = print_data(plan)
    if output_format == "json":
        data["message"] = json.dumps(data, indent=2, sort_keys=True)
    return _ok("haxaml_setup", data, warnings=plan.warnings)


def doctor_plan(*, project_dir: str | Path, output_format: str = "text") -> dict[str, Any]:
    report = doctor_data(project_dir=project_dir)
    if output_format == "json":
        report["message"] = json.dumps(report, indent=2, sort_keys=True)
    else:
        lines = [report["message"]]
        for label in ("installed", "missing", "drifted"):
            entries = report.get(label, [])
            lines.append(f"{label.title()}:")
            if entries:
                lines.extend([_format_doctor_item(item) for item in entries if isinstance(item, dict)])
            else:
                lines.append("- none")
        manual = report.get("manual_actions", [])
        lines.append("Manual Actions:")
        if manual:
            lines.extend([_format_doctor_manual_action(item) for item in manual if isinstance(item, dict)])
        else:
            lines.append("- none")
        report["message"] = "\n".join(lines)
    return _ok("haxaml_setup_doctor", report)


def workflow_check_plan(
    *,
    project_dir: str | Path,
    target: str = "auto",
    context: str = "entry",
    signal: str = "",
    strict: bool = False,
    output_format: str = "text",
) -> dict[str, Any]:
    try:
        report = workflow_check_data(
            project_dir=project_dir,
            target=target,
            context=context,
            signal=signal,
            strict=strict,
        )
    except (KeyError, ValueError) as exc:
        return _err("haxaml_workflow_check", "invalid_workflow_args", str(exc))

    if output_format == "json":
        report["message"] = json.dumps(report, indent=2, sort_keys=True)
    return _ok("haxaml_workflow_check", report)
