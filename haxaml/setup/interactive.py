"""Interactive setup wizard for TTY CLI use."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from haxaml.setup.adoption import build_adoption_inventory
from haxaml.setup.planner import SETUP_KINDS
from haxaml.setup.registry import get_target, list_targets
from haxaml.setup.service import plan_setup
from haxaml.setup.workflow import supports_workflow


CAPABILITY_KINDS = tuple(kind for kind in SETUP_KINDS if kind != "workflow")


class WizardBackend(Protocol):
    def select(self, *, message: str, choices: list[dict[str, object]], default: str | None = None) -> str | None: ...

    def checkbox(
        self,
        *,
        message: str,
        choices: list[dict[str, object]],
        defaults: list[str] | None = None,
    ) -> list[str] | None: ...

    def confirm(self, *, message: str, default: bool = True) -> bool: ...


_TARGET_PROMPT_ORDER = {
    "claude": 0,
    "codex": 1,
    "gemini": 2,
    "copilot": 3,
    "cursor": 4,
    "windsurf": 5,
    "opencode": 6,
    "junie": 7,
    "continue": 8,
    "cline": 9,
    "generic": 99,
}


class QuestionaryBackend:
    """Minimal scaffold-style backend for the setup wizard."""

    _TITLE_ART_LINES = (
        "██╗  ██╗ █████╗ ██╗  ██╗ █████╗ ███╗   ███╗██╗     ",
        "██║  ██║██╔══██╗╚██╗██╔╝██╔══██╗████╗ ████║██║     ",
        "███████║███████║ ╚███╔╝ ███████║██╔████╔██║██║     ",
        "██╔══██║██╔══██║ ██╔██╗ ██╔══██║██║╚██╔╝██║██║     ",
        "██║  ██║██║  ██║██╔╝ ██╗██║  ██║██║ ╚═╝ ██║███████╗",
        "╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝     ╚═╝╚══════╝",
    )

    def __init__(self) -> None:
        try:
            import questionary
            from prompt_toolkit.styles import Style
            from rich import box
            from rich.console import Console
            from rich.panel import Panel
            from rich.text import Text
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "Interactive setup requires questionary and rich. Reinstall or upgrade Haxaml so the setup wizard runtime is available."
            ) from exc
        self._questionary = questionary
        self._questionary.prompts.common.INDICATOR_SELECTED = "◼"
        self._questionary.prompts.common.INDICATOR_UNSELECTED = "◻"
        self._choice = questionary.Choice
        self._console = Console()
        self._box = box
        self._panel = Panel
        self._text = Text
        self._style = Style.from_dict(
            {
                "qmark": "fg:#22d3ee bold noreverse noinherit",
                "question": "fg:#f5f7fb bold noreverse noinherit",
                "answer": "fg:#8df2cf bold",
                "pointer": "fg:#93c5fd noreverse noinherit",
                "highlighted": "fg:#93c5fd bold noreverse noinherit",
                "selected": "fg:#34d399 bold noreverse noinherit",
                "instruction": "fg:#94a3b8 noreverse noinherit",
                "text": "fg:#dce7f3 noreverse noinherit",
                "separator": "fg:#64748b noreverse noinherit",
            }
        )
        self._printed_header = False

    def _title_art(self) -> object:
        gradient = ("#7dd3fc", "#60a5fa", "#38bdf8", "#22d3ee", "#2dd4bf", "#34d399")
        art = self._text()
        for index, line in enumerate(self._TITLE_ART_LINES):
            art.append(line, style=f"bold {gradient[index % len(gradient)]}")
            if index < len(self._TITLE_ART_LINES) - 1:
                art.append("\n")
        return art

    def _ensure_header(self) -> None:
        if self._printed_header:
            return
        self._console.print(self._title_art())
        heading = self._text()
        heading.append("┌  ", style="#60a5fa")
        heading.append("Haxaml Setup", style="bold #f8fafc")
        heading.append(" - ", style="#64748b")
        heading.append("governed agent installs", style="bold #f59e0b")
        self._console.print(heading)
        self._console.print(self._text("│", style="#64748b"))
        self._printed_header = True

    def _prompt_spacing(self) -> None:
        self._console.print(self._text("│", style="#64748b"))
        self._console.print(self._text("│", style="#64748b"))

    def show_block(self, title: str, body: str) -> None:
        self._ensure_header()
        self._console.print()
        block = self._text()
        for index, line in enumerate(body.splitlines()):
            block.append(line or " ", style="#dce7f3")
            if index < len(body.splitlines()) - 1:
                block.append("\n")
        self._console.print(
            self._panel.fit(
                block,
                title=f"[bold #22d3ee]{title}[/bold #22d3ee]",
                border_style="#475569",
                box=self._box.ROUNDED,
                padding=(1, 2),
            )
        )
        self._console.print()

    def _select_choices(self, choices: list[dict[str, object]]) -> list[dict[str, object]]:
        return [{"name": str(choice["name"]), "value": str(choice["value"])} for choice in choices]

    def _checkbox_choices(
        self,
        choices: list[dict[str, object]],
        *,
        defaults: list[str] | None = None,
    ) -> list[object]:
        default_values = {str(item) for item in (defaults or [])}
        return [
            self._choice(
                title=str(choice["name"]),
                value=str(choice["value"]),
                checked=str(choice["value"]) in default_values,
            )
            for choice in choices
        ]

    def select(self, *, message: str, choices: list[dict[str, object]], default: str | None = None) -> str | None:
        self._ensure_header()
        try:
            result = self._questionary.select(
                message,
                choices=self._select_choices(choices),
                qmark="◇",
                pointer=None,
                instruction=None,
                style=self._style,
            ).ask()
        except KeyboardInterrupt:
            return None
        if result is not None:
            self._prompt_spacing()
        return None if result is None else str(result)

    def checkbox(
        self,
        *,
        message: str,
        choices: list[dict[str, object]],
        defaults: list[str] | None = None,
    ) -> list[str] | None:
        self._ensure_header()
        try:
            result = self._questionary.checkbox(
                message,
                choices=self._checkbox_choices(choices, defaults=defaults),
                qmark="◆",
                pointer=None,
                instruction="(↑/↓ to navigate, space to select, a to toggle all, enter to confirm)",
                style=self._style,
            ).ask()
        except KeyboardInterrupt:
            return None
        if result is None:
            return None
        self._prompt_spacing()
        return [str(item) for item in result]

    def confirm(self, *, message: str, default: bool = True) -> bool:
        self._ensure_header()
        try:
            result = self._questionary.confirm(
                message,
                default=default,
                qmark="◇",
                style=self._style,
            ).ask()
        except KeyboardInterrupt:
            return False
        self._prompt_spacing()
        return bool(result)


@dataclass(frozen=True)
class SetupWizardResult:
    scope: str
    mode: str
    targets: list[str]
    only: list[str]
    with_workflow: bool


def _is_prefilled(prefilled: set[str], name: str) -> bool:
    return name in prefilled


def _project_candidates(project_dir: Path) -> tuple[list[dict[str, object]], list[str], list[str]]:
    inventory = build_adoption_inventory(project_dir)
    return (
        list(inventory.target_candidates),
        list(inventory.strong_detected_targets),
        list(inventory.weak_detected_targets),
    )


def _recommended_mode(scope: str, strong_targets: list[str], weak_targets: list[str]) -> str:
    if scope != "project":
        return "fresh"
    if strong_targets or weak_targets:
        return "adopted"
    return "fresh"


def _target_choices(candidate_targets: list[dict[str, object]]) -> list[dict[str, object]]:
    candidate_map = {str(item["target"]): item for item in candidate_targets}
    choices: list[dict[str, object]] = []
    ordered_targets = sorted(
        list_targets(),
        key=lambda target: (_TARGET_PROMPT_ORDER.get(target.target_id, 50), target.display_name.lower()),
    )
    for target in ordered_targets:
        candidate = candidate_map.get(target.target_id, {})
        strong = [str(path) for path in candidate.get("strong_paths", []) or []]
        weak = [str(path) for path in candidate.get("weak_paths", []) or []]
        evidence_parts = []
        if strong:
            evidence_parts.append(f"strong: {', '.join(strong)}")
        if weak:
            evidence_parts.append(f"weak: {', '.join(weak)}")
        suffix = f" ({'; '.join(evidence_parts)})" if evidence_parts else ""
        base_name = "Generic AGENTS / shared skill" if target.target_id == "generic" else target.display_name
        choices.append(
            {
                "value": target.target_id,
                "name": f"{base_name}{suffix}",
                "enabled": bool(strong),
            }
        )
    return choices


def _capability_choices(selected_targets: list[str], scope: str) -> list[dict[str, object]]:
    choices: list[dict[str, object]] = []
    for kind in CAPABILITY_KINDS:
        if kind == "frame" and scope == "project":
            choices.append({"value": kind, "name": "FRAME files", "enabled": True})
            continue
        if kind == "frame":
            continue
        if any(get_target(target_id).integration_points_for(scope, {kind}) for target_id in selected_targets if target_id != "generic"):
            choices.append({"value": kind, "name": kind, "enabled": True})
            continue
        if kind in {"instructions", "skills"} and "generic" in selected_targets and scope == "project":
            choices.append({"value": kind, "name": kind, "enabled": True})
    return choices


def _wizard_review_message(
    *,
    scope: str,
    mode: str,
    selected_targets: list[str],
    selected_only: list[str],
    selected_workflow: bool,
    preview_plan: Any,
    dry_run: bool,
) -> str:
    planned_files = [item for item in preview_plan.planned_files]
    create_count = sum(1 for item in planned_files if item.action == "create")
    update_count = sum(1 for item in planned_files if item.action in {"update", "append_pointer"})
    merge_count = sum(1 for item in planned_files if item.action == "merge")
    skip_count = sum(1 for item in planned_files if item.action == "skip")
    lines = [
        f"Mode: {mode}",
        f"Scope: {scope}",
        f"Targets: {', '.join(selected_targets) if selected_targets else '(none)'}",
        f"Capabilities: {', '.join(selected_only) if selected_only else '(none)'}",
        f"Workflow adapters: {'yes' if selected_workflow else 'no'}",
        "",
        "Planned actions:",
        f"- create: {create_count}",
        f"- update: {update_count}",
        f"- merge: {merge_count}",
        f"- skip: {skip_count}",
        f"- manual follow-up: {len(preview_plan.manual_actions)}",
    ]
    if preview_plan.strong_detected_targets:
        lines.append(f"Strong evidence: {', '.join(preview_plan.strong_detected_targets)}")
    if preview_plan.weak_detected_targets:
        lines.append(f"Weak evidence: {', '.join(preview_plan.weak_detected_targets)}")
    if preview_plan.warnings:
        lines.extend(["", "Warnings:"])
        lines.extend(f"- {item}" for item in preview_plan.warnings[:4])
    return "\n".join(lines)


def run_setup_wizard(
    *,
    project_dir: str | Path,
    scope: str,
    target: str,
    targets: tuple[str, ...] | list[str] | None = None,
    mode: str,
    only: tuple[str, ...] | list[str] | None,
    with_workflow: bool,
    prefilled: set[str] | None = None,
    dry_run: bool = False,
    backend: WizardBackend | None = None,
) -> SetupWizardResult | None:
    """Run the interactive setup wizard and return resolved CLI-equivalent args."""
    backend = backend or QuestionaryBackend()
    prefilled = prefilled or set()
    project = Path(project_dir).resolve()

    selected_scope = scope
    if not _is_prefilled(prefilled, "scope"):
        selected_scope = backend.select(
            message="Setup scope:",
            choices=[
                {"value": "project", "name": "Project"},
                {"value": "user", "name": "User home"},
            ],
            default=scope,
        )
        if selected_scope is None:
            return None

    candidate_targets: list[dict[str, object]] = []
    strong_targets: list[str] = []
    weak_targets: list[str] = []
    if selected_scope == "project":
        candidate_targets, strong_targets, weak_targets = _project_candidates(project)

    selected_mode = mode
    if mode == "auto":
        selected_mode = _recommended_mode(selected_scope, strong_targets, weak_targets)
    if selected_scope != "project":
        selected_mode = "fresh"
    elif not _is_prefilled(prefilled, "mode"):
        selected_mode = backend.select(
            message=f"Setup mode (recommended: {_recommended_mode(selected_scope, strong_targets, weak_targets)}):",
            choices=[
                {"value": "fresh", "name": "Fresh setup"},
                {"value": "adopted", "name": "Adopt existing native files"},
            ],
            default=selected_mode,
        )
        if selected_mode is None:
            return None

    selected_targets = [item for item in (targets or []) if str(item).strip()]
    if not selected_targets and target != "auto":
        selected_targets = [target]
    if not _is_prefilled(prefilled, "target"):
        if selected_scope == "project":
            target_choices = _target_choices(candidate_targets)
            defaults = strong_targets or ["generic"]
        else:
            target_choices = _target_choices([])
            defaults = [target] if target != "auto" else ["codex"]
        selected_targets = backend.checkbox(
            message="Target providers:",
            choices=target_choices,
            defaults=defaults,
        )
        if selected_targets is None:
            return None
        if not selected_targets:
            selected_targets = ["generic"] if selected_scope == "project" else ["codex"]

    selected_only = [kind for kind in CAPABILITY_KINDS if kind != "frame"]
    if selected_scope == "project":
        selected_only = list(CAPABILITY_KINDS)
    if only:
        selected_only = []
        for value in only:
            selected_only.extend([chunk.strip().lower() for chunk in str(value).split(",") if chunk.strip()])
    if not _is_prefilled(prefilled, "only"):
        capability_choices = _capability_choices(selected_targets, selected_scope)
        defaults = [choice["value"] for choice in capability_choices if choice.get("enabled")]
        if selected_scope == "project" and "frame" not in defaults:
            defaults.insert(0, "frame")
        selected_only = backend.checkbox(
            message="Capabilities to install:",
            choices=capability_choices,
            defaults=selected_only or defaults,
        )
        if selected_only is None:
            return None
        if not selected_only:
            selected_only = defaults

    selected_workflow = with_workflow
    workflow_eligible = selected_scope == "project" and any(supports_workflow(target_id) for target_id in selected_targets)
    if workflow_eligible and not _is_prefilled(prefilled, "with_workflow"):
        selected_workflow = backend.confirm(
            message="Add workflow adaptation files for the selected targets?",
            default=with_workflow,
        )

    preview_plan = plan_setup(
        project_dir=project,
        scope=selected_scope,
        target="auto",
        targets=selected_targets,
        mode=selected_mode,
        only=selected_only,
        with_workflow=selected_workflow,
    )
    confirm_message = _wizard_review_message(
        scope=selected_scope,
        mode=selected_mode,
        selected_targets=selected_targets,
        selected_only=selected_only,
        selected_workflow=selected_workflow,
        preview_plan=preview_plan,
        dry_run=dry_run,
    )
    if hasattr(backend, "show_block"):
        backend.show_block("Review setup plan", confirm_message)
    if not backend.confirm(
        message="Apply this setup now?" if not dry_run else "Run this dry run?",
        default=True,
    ):
        return None

    return SetupWizardResult(
        scope=selected_scope,
        mode=selected_mode,
        targets=selected_targets,
        only=selected_only,
        with_workflow=selected_workflow,
    )
