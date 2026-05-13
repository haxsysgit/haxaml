"""Build deterministic setup plans."""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
from pathlib import Path
from typing import Any

from haxaml.setup.adoption import build_adoption_inventory, detect_target_files
from haxaml.setup.registry import Surface, TargetSpec, get_target, list_targets
from haxaml.setup.renderer import (
    RenderedArtifact,
    render_agent,
    render_instruction,
    render_mcp_config,
    render_pointer_block,
    render_sidecar,
    render_skill,
)
from haxaml.setup.templates import render_frame_templates
from haxaml.versioning import get_version
from haxaml.yaml_utils import dump_yaml


FRAME_KINDS = ("frame", "instructions", "skills", "agents", "mcp")
MANIFEST_PATH = ".haxaml/setup/manifest.yaml"


@dataclass(frozen=True)
class ManualAction:
    target: str
    kind: str
    scope: str
    path: str | None
    docs_url: str
    reason: str

    def to_dict(self) -> dict[str, str | None]:
        return {
            "target": self.target,
            "kind": self.kind,
            "scope": self.scope,
            "path": self.path,
            "docs_url": self.docs_url,
            "reason": self.reason,
        }


@dataclass
class PlannedFile:
    target: str
    kind: str
    scope: str
    path: str
    content: str
    recipe_hash: str
    management: str
    docs_url: str
    exists: bool = False
    action: str = "create"
    note: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "target": self.target,
            "kind": self.kind,
            "scope": self.scope,
            "path": self.path,
            "content": self.content,
            "recipe_hash": self.recipe_hash,
            "management": self.management,
            "docs_url": self.docs_url,
            "exists": self.exists,
            "action": self.action,
            "note": self.note,
        }


@dataclass
class SetupPlan:
    project_dir: Path
    scope: str
    mode: str
    requested_target: str
    selected_targets: list[str]
    detected_targets: list[str]
    planned_files: list[PlannedFile] = field(default_factory=list)
    manual_actions: list[ManualAction] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    adoption_state: dict[str, object] | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "project_dir": str(self.project_dir),
            "scope": self.scope,
            "mode": self.mode,
            "requested_target": self.requested_target,
            "selected_targets": self.selected_targets,
            "detected_targets": self.detected_targets,
            "planned_files": [item.to_dict() for item in self.planned_files],
            "manual_actions": [item.to_dict() for item in self.manual_actions],
            "warnings": self.warnings,
            "adoption_state": self.adoption_state,
        }


def parse_only_values(values: tuple[str, ...] | list[str] | None) -> set[str]:
    if not values:
        return set(FRAME_KINDS)
    selected: set[str] = set()
    for value in values:
        for chunk in str(value).split(","):
            chunk = chunk.strip().lower()
            if not chunk:
                continue
            if chunk not in FRAME_KINDS:
                supported = ", ".join(FRAME_KINDS)
                raise ValueError(f"Unknown setup kind '{chunk}'. Supported values: {supported}")
            selected.add(chunk)
    return selected or set(FRAME_KINDS)


def _artifact_from_text(text: str) -> RenderedArtifact:
    return RenderedArtifact(content=text, recipe_hash=hashlib.sha256(text.encode("utf-8")).hexdigest())


def _relative(path: Path, project_dir: Path, scope: str) -> str:
    if scope == "user":
        return str(path.expanduser())
    return path.relative_to(project_dir).as_posix()


def _managed_action(path: Path, project_dir: Path, scope: str, management: str) -> tuple[bool, str]:
    exists = path.exists()
    if not exists:
        return False, "create"
    if management == "pointer":
        return True, "append_pointer"
    return True, "update"


def _add_file(
    store: dict[str, PlannedFile],
    *,
    project_dir: Path,
    scope: str,
    target: str,
    kind: str,
    path: Path,
    artifact: RenderedArtifact,
    management: str,
    docs_url: str,
    note: str = "",
) -> None:
    relative = _relative(path, project_dir, scope)
    exists, action = _managed_action(path, project_dir, scope, management)
    current = store.get(relative)
    if current is not None:
        if current.management == "file" and management == "pointer":
            return
        if current.kind == "skills" and kind == "skills":
            return
    store[relative] = PlannedFile(
        target=target,
        kind=kind,
        scope=scope,
        path=relative,
        content=artifact.content,
        recipe_hash=artifact.recipe_hash,
        management=management,
        docs_url=docs_url,
        exists=exists,
        action=action,
        note=note,
    )


def _select_targets(target: str, mode: str, detected: list[str]) -> list[str]:
    if target != "auto":
        return [target]
    if mode == "adopted" and detected:
        return detected
    return ["generic"]


def _target_single_instruction_surface(target: TargetSpec, scope: str) -> Surface | None:
    for surface in target.surfaces_for(scope, {"instructions"}):
        if surface.path is not None and "*" not in surface.path and "?" not in surface.path:
            return surface
    return None


def build_setup_plan(
    *,
    project_dir: str | Path,
    scope: str = "project",
    target: str = "auto",
    mode: str = "auto",
    only: tuple[str, ...] | list[str] | None = None,
) -> SetupPlan:
    root = Path(project_dir).resolve()
    kinds = parse_only_values(only)
    adoption_inventory = build_adoption_inventory(root) if scope == "project" else None
    detected = list(adoption_inventory.detected_targets) if adoption_inventory else []
    normalized_mode = str(mode or "auto").strip().lower()
    if normalized_mode not in {"auto", "fresh", "adopted"}:
        raise ValueError("mode must be one of: auto, fresh, adopted")

    if scope == "user" and normalized_mode == "adopted":
        raise ValueError("Adopted mode is only supported for project scope.")

    if normalized_mode == "auto":
        resolved_mode = "adopted" if scope == "project" and detected else "fresh"
    else:
        resolved_mode = normalized_mode

    if resolved_mode == "adopted" and scope == "project":
        if target == "auto":
            if not detected:
                raise ValueError("No native instruction files detected for adopted mode.")
        else:
            target_spec = get_target(target)
            if not detect_target_files(root, target_spec):
                raise ValueError(
                    f"Adopted mode requires an existing native {target_spec.display_name} surface in the project."
                )

    selected_targets = _select_targets(target, resolved_mode, detected)

    if target != "auto" and target not in {item.target_id for item in list_targets()}:
        get_target(target)
    for item in selected_targets:
        get_target(item)

    plan = SetupPlan(
        project_dir=root,
        scope=scope,
        mode=resolved_mode,
        requested_target=target,
        selected_targets=selected_targets,
        detected_targets=detected,
    )

    files: dict[str, PlannedFile] = {}

    if scope == "project" and "frame" in kinds:
        for filename, content in render_frame_templates(mode=resolved_mode, include_origin=True).items():
            path = root / ".haxaml" / filename
            docs = "https://github.com/haxsysgit/haxaml/blob/main/learn/FRAME.md"
            _add_file(
                files,
                project_dir=root,
                scope=scope,
                target="haxaml",
                kind="frame",
                path=path,
                artifact=_artifact_from_text(content),
                management="file",
                docs_url=docs,
            )

    if scope == "project" and "skills" in kinds:
        generic_skill_target = get_target("generic")
        generic_skill_surface = generic_skill_target.surfaces_for("project", {"skills"})[0]
        _add_file(
            files,
            project_dir=root,
            scope=scope,
            target="generic",
            kind="skills",
            path=generic_skill_surface.resolve(root),
            artifact=render_skill(generic_skill_target, scope),
            management="file",
            docs_url=generic_skill_surface.docs_url,
        )

    sidecars: list[str] = []
    skipped_files: list[str] = []

    for target_id in selected_targets:
        target_spec = get_target(target_id)
        if target_spec.target_id == "generic" and scope == "project":
            pass
        for surface in target_spec.surfaces_for(scope):
            if surface.kind not in kinds:
                continue
            if surface.manual_only or not surface.writable or surface.path is None:
                plan.manual_actions.append(
                    ManualAction(
                        target=target_spec.target_id,
                        kind=surface.kind,
                        scope=surface.scope,
                        path=surface.path,
                        docs_url=surface.docs_url,
                        reason=surface.note or "Manual-only surface.",
                    )
                )
                continue

            path = surface.resolve(root)
            assert path is not None

            if surface.kind == "instructions":
                if plan.mode == "adopted" and scope == "project" and path.exists() and target_spec.target_id != "cursor":
                    sidecar_path = root / ".haxaml" / "setup" / "targets" / f"{target_spec.target_id}.md"
                    sidecars.append(sidecar_path.relative_to(root).as_posix())
                    _add_file(
                        files,
                        project_dir=root,
                        scope=scope,
                        target=target_spec.target_id,
                        kind="instructions",
                        path=sidecar_path,
                        artifact=render_sidecar(target_spec, root),
                        management="file",
                        docs_url=surface.docs_url,
                        note="Managed sidecar for adopted native instructions.",
                    )
                    _add_file(
                        files,
                        project_dir=root,
                        scope=scope,
                        target=target_spec.target_id,
                        kind="instructions",
                        path=path,
                        artifact=render_pointer_block(target_spec, sidecar_path.relative_to(root).as_posix()),
                        management="pointer",
                        docs_url=surface.docs_url,
                        note="Managed pointer block appended to an adopted native instruction file.",
                    )
                    continue
                if plan.mode == "fresh" and path.exists() and target_spec.target_id != "generic":
                    skipped_files.append(_relative(path, root, scope))
                _add_file(
                    files,
                    project_dir=root,
                    scope=scope,
                    target=target_spec.target_id,
                    kind="instructions",
                    path=path,
                    artifact=render_instruction(target_spec, scope, root),
                    management="file",
                    docs_url=surface.docs_url,
                )
                continue

            if surface.kind == "skills":
                _add_file(
                    files,
                    project_dir=root,
                    scope=scope,
                    target=target_spec.target_id,
                    kind="skills",
                    path=path,
                    artifact=render_skill(target_spec, scope),
                    management="file",
                    docs_url=surface.docs_url,
                )
                continue

            if surface.kind == "agents":
                _add_file(
                    files,
                    project_dir=root,
                    scope=scope,
                    target=target_spec.target_id,
                    kind="agents",
                    path=path,
                    artifact=render_agent(target_spec, scope),
                    management="file",
                    docs_url=surface.docs_url,
                )
                continue

            if surface.kind == "mcp":
                _add_file(
                    files,
                    project_dir=root,
                    scope=scope,
                    target=target_spec.target_id,
                    kind="mcp",
                    path=path,
                    artifact=render_mcp_config(target_spec, surface, root),
                    management="file",
                    docs_url=surface.docs_url,
                )

    if scope == "project" and plan.mode == "adopted" and adoption_inventory is not None:
        from haxaml.setup.adoption import ADOPTION_REPORT_PATH, ADOPTION_STATE_PATH, dump_adoption_state
        from haxaml.setup.renderer import render_adoption_report

        state = adoption_inventory.to_state(
            selected_targets=selected_targets,
            sidecars=sorted(set(sidecars)),
            skipped_files=sorted(set(skipped_files)),
        )
        plan.adoption_state = state
        _add_file(
            files,
            project_dir=root,
            scope=scope,
            target="adoption",
            kind="frame",
            path=root / ADOPTION_STATE_PATH,
            artifact=_artifact_from_text(dump_adoption_state(state)),
            management="file",
            docs_url="https://github.com/haxsysgit/haxaml/blob/main/0.7.x_Roadmap.md",
            note="Detailed adoption state is stored outside core FRAME files.",
        )
        _add_file(
            files,
            project_dir=root,
            scope=scope,
            target="adoption",
            kind="frame",
            path=root / ADOPTION_REPORT_PATH,
            artifact=_artifact_from_text(render_adoption_report(state)),
            management="file",
            docs_url="https://github.com/haxsysgit/haxaml/blob/main/0.7.x_Roadmap.md",
            note="Human-readable adoption report.",
        )

    managed_files = []
    for item in files.values():
        managed_files.append(
            {
                "path": item.path,
                "target": item.target,
                "kind": item.kind,
                "scope": item.scope,
                "management": item.management,
                "docs_url": item.docs_url,
                "recipe_hash": item.recipe_hash,
            }
        )

    manifest = {
        "version": get_version(),
        "generator": "haxaml-setup",
        "scope": plan.scope,
        "mode": plan.mode,
        "requested_target": plan.requested_target,
        "selected_targets": plan.selected_targets,
        "detected_targets": plan.detected_targets,
        "managed_files": managed_files,
        "manual_actions": [item.to_dict() for item in plan.manual_actions],
    }
    if scope == "project":
        _add_file(
            files,
            project_dir=root,
            scope=scope,
            target="haxaml",
            kind="frame",
            path=root / MANIFEST_PATH,
            artifact=_artifact_from_text(dump_yaml(manifest, sort_keys=False)),
            management="file",
            docs_url="https://github.com/haxsysgit/haxaml/blob/main/0.7.x_Roadmap.md",
            note="Setup manifest for doctor and drift checks.",
        )

    plan.planned_files = sorted(files.values(), key=lambda item: item.path)
    return plan
