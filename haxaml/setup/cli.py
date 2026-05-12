"""CLI-facing wrappers for setup planning, writing, and doctor output."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from haxaml.setup.doctor import run_setup_doctor
from haxaml.setup.planner import SetupPlan, build_setup_plan
from haxaml.setup.writer import apply_setup_plan


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


def _text_summary(plan: SetupPlan, *, apply_result: dict[str, object] | None = None) -> str:
    lines = [
        f"Mode: {plan.mode}",
        f"Scope: {plan.scope}",
        f"Targets: {', '.join(plan.selected_targets) if plan.selected_targets else '(none)'}",
    ]
    if plan.detected_targets:
        lines.append(f"Detected native targets: {', '.join(plan.detected_targets)}")
    if plan.needs_adoption_confirmation:
        lines.append("Native instructions were detected. Re-run with --adopt auto or choose fresh mode explicitly.")
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


def _json_data(plan: SetupPlan, *, apply_result: dict[str, object] | None = None) -> dict[str, Any]:
    data = plan.to_dict()
    if apply_result is not None:
        data["apply_result"] = apply_result
    data["message"] = _text_summary(plan, apply_result=apply_result)
    return data


def setup_plan(
    *,
    project_dir: str | Path,
    scope: str = "project",
    target: str = "auto",
    adopt: str | None = None,
    only: tuple[str, ...] | list[str] | None = None,
    output_format: str = "text",
    assume_fresh: bool = False,
) -> dict[str, Any]:
    try:
        plan = build_setup_plan(
            project_dir=project_dir,
            scope=scope,
            target=target,
            adopt=adopt,
            only=only,
            assume_fresh=assume_fresh,
        )
    except (KeyError, ValueError) as exc:
        return _err("haxaml_setup", "invalid_setup_args", str(exc))

    data = _json_data(plan)
    if output_format == "json":
        data["message"] = json.dumps(data, indent=2, sort_keys=True)
    return _ok("haxaml_setup", data, warnings=plan.warnings)


def execute_setup(
    *,
    project_dir: str | Path,
    scope: str = "project",
    target: str = "auto",
    adopt: str | None = None,
    only: tuple[str, ...] | list[str] | None = None,
    force: bool = False,
    dry_run: bool = False,
    output_format: str = "text",
    assume_fresh: bool = False,
) -> dict[str, Any]:
    try:
        plan = build_setup_plan(
            project_dir=project_dir,
            scope=scope,
            target=target,
            adopt=adopt,
            only=only,
            assume_fresh=assume_fresh,
        )
    except (KeyError, ValueError) as exc:
        return _err("haxaml_setup", "invalid_setup_args", str(exc))

    if plan.needs_adoption_confirmation:
        return _err(
            "haxaml_setup",
            "adoption_confirmation_required",
            "Native instruction files were detected. Re-run with --adopt auto or pass an explicit target.",
            plan.to_dict(),
        )

    apply_result = None if dry_run else apply_setup_plan(plan, force=force)
    data = _json_data(plan, apply_result=apply_result)
    if dry_run:
        data["message"] = _text_summary(plan)
    if output_format == "json":
        data["message"] = json.dumps(data, indent=2, sort_keys=True)
    return _ok("haxaml_setup", data, warnings=plan.warnings)


def print_plan(
    *,
    project_dir: str | Path,
    scope: str = "project",
    target: str = "auto",
    adopt: str | None = None,
    only: tuple[str, ...] | list[str] | None = None,
    output_format: str = "text",
    assume_fresh: bool = False,
) -> dict[str, Any]:
    result = setup_plan(
        project_dir=project_dir,
        scope=scope,
        target=target,
        adopt=adopt,
        only=only,
        output_format=output_format,
        assume_fresh=assume_fresh,
    )
    if result["ok"] and output_format == "text":
        payload = result["data"]
        previews = []
        for item in payload.get("planned_files", []):
            previews.append(f"=== {item['path']} ===\n{item['content']}".rstrip())
        payload["message"] = "\n\n".join(previews) if previews else "No planned files."
    return result


def doctor_plan(*, project_dir: str | Path, output_format: str = "text") -> dict[str, Any]:
    report = run_setup_doctor(project_dir)
    if output_format == "json":
        report["message"] = json.dumps(report, indent=2, sort_keys=True)
    else:
        lines = [report["message"]]
        for label in ("installed", "missing", "drifted"):
            entries = report.get(label, [])
            lines.append(f"{label.title()}:")
            if entries:
                lines.extend([f"- {item['path']} ({item['target']} {item['kind']})" for item in entries])
            else:
                lines.append("- none")
        manual = report.get("manual_actions", [])
        lines.append("Manual Actions:")
        if manual:
            lines.extend([f"- {item.get('target')} {item.get('kind')}: {item.get('reason')}" for item in manual])
        else:
            lines.append("- none")
        report["message"] = "\n".join(lines)
    return _ok("haxaml_setup_doctor", report)
