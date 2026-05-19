"""CLI-facing wrappers for canonical setup service operations."""

from __future__ import annotations

import json
from pathlib import Path
from pathlib import PurePosixPath
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


_INTERACTIVE_KIND_ORDER = ("skills", "agents", "instructions", "mcp", "workflow", "frame")
_INTERACTIVE_KIND_LABELS = {
    "skills": "skills",
    "agents": "agents",
    "instructions": "instructions",
    "mcp": "mcp",
    "workflow": "workflow",
    "frame": "frame",
}
_INTERACTIVE_ARROW = "→"


def _interactive_status_label(status: str) -> str:
    mapping = {
        "append_pointer": "updated",
        "merge": "merged",
        "update": "updated",
    }
    return mapping.get(status, status)


def _selection_source_text(selection_source: str) -> str:
    mapping = {
        "explicit_targets": "explicit --targets selection",
        "explicit_target": "explicit --target selection",
        "auto_strong_detection": "single strong native provider detection",
        "generic_fallback": "generic fallback",
    }
    return mapping.get(selection_source, selection_source or "auto")


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


def _collect_interactive_summary(data: dict[str, Any], *, dry_run: bool = False) -> dict[str, object]:
    if dry_run:
        items = [item for item in data.get("planned_files", []) if isinstance(item, dict)]
    else:
        apply_result = data.get("apply_result") or {}
        items = [item for item in apply_result.get("items", []) if isinstance(item, dict)]

    grouped: dict[str, list[str]] = {kind: [] for kind in _INTERACTIVE_KIND_ORDER}
    preserved_frame: list[str] = []
    skipped_paths: list[str] = []
    for item in items:
        kind = str(item.get("kind") or "")
        path = str(item.get("path") or "").strip()
        if not kind or not path:
            continue
        status = str(item.get("status") or item.get("action") or "").strip().lower()
        if status in {"skip", "skipped"}:
            if kind == "frame":
                preserved_frame.append(path)
            else:
                skipped_paths.append(path)
            continue
        label = path
        normalized_status = _interactive_status_label(status)
        if normalized_status in {"merged", "updated"}:
            label = f"{path} ({normalized_status})"
        grouped.setdefault(kind, []).append(label)

    return {
        "grouped": grouped,
        "preserved_frame": preserved_frame,
        "skipped_paths": skipped_paths,
        "next_steps": [str(step) for step in data.get("next_steps", []) if str(step).strip()],
    }


def _compact_path_line(paths: list[str], *, fold_prefix: bool = False) -> str:
    cleaned = [path.strip() for path in paths if path.strip()]
    if not fold_prefix or len(cleaned) < 2:
        return ", ".join(cleaned)
    if any(" (" in path for path in cleaned):
        return ", ".join(cleaned)

    parts_list = [PurePosixPath(path).parts for path in cleaned]
    prefix_parts: list[str] = []
    for part_group in zip(*parts_list, strict=False):
        if len(set(part_group)) != 1:
            break
        prefix_parts.append(part_group[0])
    if not prefix_parts:
        return ", ".join(cleaned)

    prefix = PurePosixPath(*prefix_parts).as_posix()
    suffixes: list[str] = []
    for path in cleaned:
        relative = PurePosixPath(path).relative_to(PurePosixPath(prefix))
        suffixes.append(relative.as_posix())
    if not all(suffixes):
        return ", ".join(cleaned)
    return f"{prefix}/{{{', '.join(suffixes)}}}"


def interactive_setup_message(data: dict[str, Any], *, dry_run: bool = False) -> str:
    """Render a compact grouped summary for the interactive wizard flow."""
    summary = _collect_interactive_summary(data, dry_run=dry_run)
    grouped = summary["grouped"]
    preserved_frame = summary["preserved_frame"]
    skipped_paths = summary["skipped_paths"]
    next_steps = summary["next_steps"]

    lines = [
        "┌  Haxaml Setup",
        "│",
        f"│  {'Dry run summary' if dry_run else 'Setup summary'}",
        f"│  mode: {data.get('mode', 'auto')}",
        f"│  scope: {data.get('scope', 'project')}",
        f"│  targets: {', '.join(data.get('selected_targets', []) or []) or '(none)'}",
    ]
    selection_source = str(data.get("selection_source") or "")
    if selection_source:
        lines.append(f"│  selection: {_selection_source_text(selection_source)}")
    lines.append("│")

    for kind in _INTERACTIVE_KIND_ORDER:
        paths = grouped.get(kind) or []
        if not paths:
            continue
        lines.append(
            f"│  {_INTERACTIVE_KIND_LABELS.get(kind, kind)} {_INTERACTIVE_ARROW} "
            f"{_compact_path_line(paths, fold_prefix=(kind == 'frame'))}"
        )

    if preserved_frame:
        lines.append(
            f"│  preserved frame {_INTERACTIVE_ARROW} "
            f"{_compact_path_line(preserved_frame, fold_prefix=True)}"
        )

    if skipped_paths:
        lines.append(f"│  skipped {_INTERACTIVE_ARROW} {_compact_path_line(skipped_paths)}")

    if next_steps:
        lines.append("│")
        lines.append("│  next:")
        for step in next_steps[:3]:
            lines.append(f"│    {step}")

    lines.append("└")
    return "\n".join(lines)


def print_interactive_summary(data: dict[str, Any], *, dry_run: bool = False) -> bool:
    """Render the interactive setup summary in the same card style as review."""
    try:
        from rich import box
        from rich.console import Console
        from rich.panel import Panel
        from rich.text import Text
    except ModuleNotFoundError:
        return False

    summary = _collect_interactive_summary(data, dry_run=dry_run)
    grouped = summary["grouped"]
    preserved_frame = summary["preserved_frame"]
    skipped_paths = summary["skipped_paths"]
    next_steps = summary["next_steps"]

    console = Console()
    project_dir = str(data.get("project_dir") or ".")
    console.print()

    text = Text()
    text.append(
        f"{'Planning' if dry_run else 'Scaffolding'} Haxaml setup in {project_dir}...\n",
        style="bold #f8fafc",
    )
    text.append("\n")
    text.append(f"mode {_INTERACTIVE_ARROW} ", style="bold #93c5fd")
    text.append(f"{data.get('mode', 'auto')}\n", style="#f8fafc")
    text.append(f"scope {_INTERACTIVE_ARROW} ", style="bold #93c5fd")
    text.append(f"{data.get('scope', 'project')}\n", style="#f8fafc")
    text.append(f"targets {_INTERACTIVE_ARROW} ", style="bold #93c5fd")
    text.append(f"{', '.join(data.get('selected_targets', []) or []) or '(none)'}\n", style="#f8fafc")
    selection_source = str(data.get("selection_source") or "")
    if selection_source:
        text.append(f"selection {_INTERACTIVE_ARROW} ", style="bold #93c5fd")
        text.append(f"{_selection_source_text(selection_source)}\n", style="#f8fafc")
    text.append("\n")

    for kind in _INTERACTIVE_KIND_ORDER:
        paths = grouped.get(kind) or []
        if not paths:
            continue
        label = _INTERACTIVE_KIND_LABELS.get(kind, kind)
        text.append(f"{label} {_INTERACTIVE_ARROW} ", style="bold #34d399")
        text.append(f"{_compact_path_line(paths, fold_prefix=(kind == 'frame'))}\n", style="#dce7f3")

    if preserved_frame:
        text.append(f"preserved frame {_INTERACTIVE_ARROW} ", style="bold #f59e0b")
        text.append(f"{_compact_path_line(preserved_frame, fold_prefix=True)}\n", style="#dce7f3")

    if skipped_paths:
        text.append(f"skipped {_INTERACTIVE_ARROW} ", style="bold #f59e0b")
        text.append(f"{_compact_path_line(skipped_paths)}\n", style="#dce7f3")
    text.append("\n")
    text.append("Done.\n", style="bold #22d3ee")
    text.append("\n")
    text.append("\n")
    text.append("Next:\n", style="bold #c084fc")
    for step in next_steps[:3]:
        text.append(f"{step}\n", style="#dce7f3")

    console.print(
        Panel.fit(
            text,
            border_style="#475569",
            box=box.ROUNDED,
            padding=(1, 2),
        )
    )
    return True


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
