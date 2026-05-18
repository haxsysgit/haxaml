"""Interactive setup wizard for TTY CLI use."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from haxaml.setup.adoption import build_adoption_inventory
from haxaml.setup.planner import SETUP_KINDS
from haxaml.setup.registry import get_target, list_targets
from haxaml.setup.service import plan_setup, setup_message
from haxaml.setup.workflow import supports_workflow


CAPABILITY_KINDS = tuple(kind for kind in SETUP_KINDS if kind != "workflow")


class WizardBackend(Protocol):
    def select(self, *, message: str, choices: list[dict[str, object]], default: str | None = None) -> str: ...

    def checkbox(
        self,
        *,
        message: str,
        choices: list[dict[str, object]],
        defaults: list[str] | None = None,
    ) -> list[str]: ...

    def confirm(self, *, message: str, default: bool = True) -> bool: ...


class InquirerPyBackend:
    """Thin adapter over InquirerPy for the setup wizard."""

    def __init__(self) -> None:
        try:
            from InquirerPy import inquirer
            from InquirerPy.base import Choice
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "Interactive setup requires InquirerPy. Install or upgrade Haxaml with the interactive dependency set."
            ) from exc
        self._inquirer = inquirer
        self._choice = Choice

    def _choice_items(self, choices: list[dict[str, object]]) -> list[object]:
        return [
            self._choice(
                value=str(choice["value"]),
                name=str(choice["name"]),
                enabled=bool(choice.get("enabled", False)),
            )
            for choice in choices
        ]

    def select(self, *, message: str, choices: list[dict[str, object]], default: str | None = None) -> str:
        return str(
            self._inquirer.select(
                message=message,
                choices=self._choice_items(choices),
                default=default,
                instruction="Use arrow keys and enter.",
                cycle=False,
            ).execute()
        )

    def checkbox(
        self,
        *,
        message: str,
        choices: list[dict[str, object]],
        defaults: list[str] | None = None,
    ) -> list[str]:
        default_set = set(defaults or [])
        enabled_choices = []
        for choice in choices:
            enriched = dict(choice)
            enriched["enabled"] = str(choice["value"]) in default_set or bool(choice.get("enabled", False))
            enabled_choices.append(enriched)
        result = self._inquirer.checkbox(
            message=message,
            choices=self._choice_items(enabled_choices),
            instruction="Use arrow keys, space to toggle, and enter to confirm.",
            cycle=False,
        ).execute()
        return [str(item) for item in result]

    def confirm(self, *, message: str, default: bool = True) -> bool:
        return bool(
            self._inquirer.confirm(
                message=message,
                default=default,
                instruction="Press enter to confirm.",
            ).execute()
        )


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
    choices: list[dict[str, object]] = [
        {
            "value": "generic",
            "name": "Generic AGENTS / shared skill",
            "enabled": False,
        }
    ]
    for target in list_targets():
        if target.target_id == "generic":
            continue
        candidate = candidate_map.get(target.target_id, {})
        strong = [str(path) for path in candidate.get("strong_paths", []) or []]
        weak = [str(path) for path in candidate.get("weak_paths", []) or []]
        evidence_parts = []
        if strong:
            evidence_parts.append(f"strong: {', '.join(strong)}")
        if weak:
            evidence_parts.append(f"weak: {', '.join(weak)}")
        suffix = f" ({'; '.join(evidence_parts)})" if evidence_parts else ""
        choices.append(
            {
                "value": target.target_id,
                "name": f"{target.display_name}{suffix}",
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
    backend = backend or InquirerPyBackend()
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
    confirm_message = setup_message(preview_plan)
    if not backend.confirm(
        message=f"{confirm_message}\n\n{'Run dry-run with this plan?' if dry_run else 'Apply this setup?'}",
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
