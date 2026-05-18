"""Build deterministic setup plans."""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
from pathlib import Path
from typing import Any

from haxaml.setup.adoption import build_adoption_inventory, detect_target_files
from haxaml.setup.config_merge import managed_config_key_path, plan_managed_config_write
from haxaml.setup.registry import IntegrationPoint, TargetSpec, get_target, list_targets
from haxaml.setup.renderer import (
    RenderedArtifact,
    render_adapter_file,
    render_agent,
    render_instruction,
    render_mcp_config,
    render_pointer_block,
    render_skill,
)
from haxaml.setup.templates import render_frame_templates
from haxaml.setup.workflow import (
    build_workflow_artifacts,
    supports_workflow,
    workflow_absorbs_integration_point,
    workflow_adapter_file_path,
    workflow_manual_actions,
    workflow_entrypoints,
)
from haxaml.versioning import get_version
from haxaml.yaml_utils import dump_yaml


SETUP_KINDS = ("frame", "instructions", "skills", "agents", "mcp", "workflow")
MANIFEST_PATH = ".haxaml/setup/manifest.yaml"


@dataclass(frozen=True)
class ManualAction:
    target: str
    kind: str
    scope: str
    path: str | None
    docs_url: str
    reason: str
    preview: str = ""
    action_reason: str = ""
    candidate_targets: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "target": self.target,
            "kind": self.kind,
            "scope": self.scope,
            "path": self.path,
            "docs_url": self.docs_url,
            "reason": self.reason,
            "preview": self.preview,
            "action_reason": self.action_reason,
            "candidate_targets": self.candidate_targets,
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
    format: str = "markdown"
    preview: str = ""
    action_reason: str = ""
    merge_status: str = ""
    candidate_targets: list[str] = field(default_factory=list)
    managed_key_path: str = ""

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
            "format": self.format,
            "preview": self.preview,
            "action_reason": self.action_reason,
            "merge_status": self.merge_status,
            "candidate_targets": self.candidate_targets,
            "managed_key_path": self.managed_key_path,
        }


@dataclass
class SetupPlan:
    project_dir: Path
    scope: str
    mode: str
    requested_target: str
    selected_targets: list[str]
    detected_targets: list[str]
    requested_targets: list[str] = field(default_factory=list)
    selection_source: str = "auto_fallback"
    strong_detected_targets: list[str] = field(default_factory=list)
    weak_detected_targets: list[str] = field(default_factory=list)
    target_candidates: list[dict[str, object]] = field(default_factory=list)
    workflow_enabled: bool = False
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
            "requested_targets": self.requested_targets,
            "selected_targets": self.selected_targets,
            "selection_source": self.selection_source,
            "detected_targets": self.detected_targets,
            "strong_detected_targets": self.strong_detected_targets,
            "weak_detected_targets": self.weak_detected_targets,
            "target_candidates": self.target_candidates,
            "workflow_enabled": self.workflow_enabled,
            "planned_files": [item.to_dict() for item in self.planned_files],
            "manual_actions": [item.to_dict() for item in self.manual_actions],
            "warnings": self.warnings,
            "adoption_state": self.adoption_state,
        }


def parse_only_values(values: tuple[str, ...] | list[str] | None) -> set[str]:
    if not values:
        return set(SETUP_KINDS) - {"workflow"}
    selected: set[str] = set()
    for value in values:
        for chunk in str(value).split(","):
            chunk = chunk.strip().lower()
            if not chunk:
                continue
            if chunk not in SETUP_KINDS:
                supported = ", ".join(SETUP_KINDS)
                raise ValueError(f"Unknown setup kind '{chunk}'. Supported values: {supported}")
            selected.add(chunk)
    return selected or (set(SETUP_KINDS) - {"workflow"})


def _artifact_from_text(text: str) -> RenderedArtifact:
    return RenderedArtifact(content=text, recipe_hash=hashlib.sha256(text.encode("utf-8")).hexdigest())


def _preview_text(content: str, *, max_lines: int = 10) -> str:
    lines = content.rstrip().splitlines()
    if len(lines) <= max_lines:
        return "\n".join(lines).rstrip() + ("\n" if content.endswith("\n") else "")
    return "\n".join(lines[:max_lines]).rstrip() + "\n..."


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
    if management == "merge":
        return True, "merge"
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
    format: str = "markdown",
    preview: str = "",
    action_reason: str = "",
    merge_status: str = "",
    candidate_targets: list[str] | None = None,
    managed_key_path: str = "",
    action_override: str | None = None,
) -> None:
    relative = _relative(path, project_dir, scope)
    exists, action = _managed_action(path, project_dir, scope, management)
    if action_override is not None:
        action = action_override
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
        format=format,
        preview=preview or _preview_text(artifact.content),
        action_reason=action_reason,
        merge_status=merge_status,
        candidate_targets=list(candidate_targets or []),
        managed_key_path=managed_key_path,
    )


def _candidate_summary(candidates: list[dict[str, object]]) -> str:
    parts: list[str] = []
    for item in candidates:
        label = str(item.get("label") or item.get("target") or "unknown")
        evidence = [str(path) for path in item.get("strong_paths", []) or []]
        if not evidence:
            evidence = [str(path) for path in item.get("weak_paths", []) or []]
        joined = ", ".join(evidence) if evidence else "no file evidence"
        parts.append(f"{label} via {joined}")
    return "; ".join(parts)


def _select_targets(
    target: str,
    mode: str,
    strong_detected: list[str],
    explicit_targets: list[str] | None = None,
) -> list[str]:
    if explicit_targets:
        return explicit_targets
    if target != "auto":
        return [target]
    if mode == "adopted" and len(strong_detected) == 1:
        return [strong_detected[0]]
    return ["generic"]


def _selection_source(
    *,
    target: str,
    explicit_targets: list[str],
    resolved_mode: str,
    strong_detected: list[str],
) -> str:
    if explicit_targets:
        return "explicit_targets"
    if target != "auto":
        return "explicit_target"
    if resolved_mode == "adopted" and len(strong_detected) == 1:
        return "auto_strong_detection"
    return "generic_fallback"


def _target_single_instruction_integration_point(target: TargetSpec, scope: str) -> IntegrationPoint | None:
    for integration_point in target.integration_points_for(scope, {"instructions"}):
        if integration_point.path is not None and "*" not in integration_point.path and "?" not in integration_point.path:
            return integration_point
    return None


def _target_single_skill_integration_point(target: TargetSpec, scope: str) -> IntegrationPoint | None:
    for integration_point in target.integration_points_for(scope, {"skills"}):
        if integration_point.path is not None and "*" not in integration_point.path and "?" not in integration_point.path:
            return integration_point
    return None


def build_setup_plan(
    *,
    project_dir: str | Path,
    scope: str = "project",
    target: str = "auto",
    targets: tuple[str, ...] | list[str] | None = None,
    mode: str = "auto",
    only: tuple[str, ...] | list[str] | None = None,
    with_workflow: bool = False,
) -> SetupPlan:
    root = Path(project_dir).resolve()
    kinds = parse_only_values(only)
    if with_workflow:
        kinds.add("workflow")
    adoption_inventory = build_adoption_inventory(root) if scope == "project" else None
    detected = list(adoption_inventory.detected_targets) if adoption_inventory else []
    strong_detected = list(adoption_inventory.strong_detected_targets) if adoption_inventory else []
    weak_detected = list(adoption_inventory.weak_detected_targets) if adoption_inventory else []
    target_candidates = list(adoption_inventory.target_candidates) if adoption_inventory else []
    explicit_targets = [item for item in (targets or []) if str(item).strip()]
    normalized_mode = str(mode or "auto").strip().lower()
    if normalized_mode not in {"auto", "fresh", "adopted"}:
        raise ValueError("mode must be one of: auto, fresh, adopted")

    if scope == "user" and normalized_mode == "adopted":
        raise ValueError("Adopted mode is only supported for project scope.")

    for item in explicit_targets:
        get_target(item)
    explicit_targets = list(dict.fromkeys(explicit_targets))

    if normalized_mode == "auto":
        mode_targets = list(explicit_targets)
        if not mode_targets and target != "auto":
            mode_targets = [target]
        if mode_targets:
            resolved_mode = (
                "adopted"
                if scope == "project" and any(detect_target_files(root, get_target(item)) for item in mode_targets)
                else "fresh"
            )
        elif scope == "project" and target == "auto" and len(strong_detected) == 1:
            resolved_mode = "adopted"
        else:
            resolved_mode = "fresh"
    else:
        resolved_mode = normalized_mode

    if resolved_mode == "adopted" and scope == "project":
        if explicit_targets:
            pass
        elif target == "auto":
            if len(strong_detected) != 1:
                if strong_detected:
                    raise ValueError(
                        "Adopted mode with `target=auto` needs exactly one strong native target. "
                        f"Candidates: {_candidate_summary(target_candidates)}"
                    )
                raise ValueError("No strong native instruction files detected for adopted mode.")
        else:
            target_spec = get_target(target)
            if not detect_target_files(root, target_spec):
                raise ValueError(
                    f"Adopted mode requires an existing {target_spec.display_name} integration point in the project."
                )

    selected_targets = _select_targets(target, resolved_mode, strong_detected, explicit_targets)

    if target != "auto" and target not in {item.target_id for item in list_targets()}:
        get_target(target)
    for item in selected_targets:
        get_target(item)

    plan = SetupPlan(
        project_dir=root,
        scope=scope,
        mode=resolved_mode,
        requested_target=target,
        requested_targets=list(explicit_targets),
        selected_targets=selected_targets,
        selection_source=_selection_source(
            target=target,
            explicit_targets=explicit_targets,
            resolved_mode=resolved_mode,
            strong_detected=strong_detected,
        ),
        detected_targets=detected,
        strong_detected_targets=strong_detected,
        weak_detected_targets=weak_detected,
        target_candidates=target_candidates,
        workflow_enabled="workflow" in kinds and scope == "project",
    )

    if scope == "project" and target == "auto" and not explicit_targets:
        if len(strong_detected) > 1:
            plan.warnings.append(
                "Auto target resolution found multiple strong provider candidates and did not guess. "
                f"Defaulting to fresh generic setup. Candidates: {_candidate_summary(target_candidates)}"
            )
        elif not strong_detected and weak_detected:
            weak_candidates = [item for item in target_candidates if item.get("weak_paths") and not item.get("strong_paths")]
            plan.warnings.append(
                "Auto target resolution found only weak shared signals and did not guess. "
                f"Defaulting to fresh generic setup. Candidates: {_candidate_summary(weak_candidates)}"
            )

    if "workflow" in kinds and scope != "project":
        plan.warnings.append("Workflow adaptation is project-only in 0.7.x. User-scope workflow assets are ignored.")
        kinds.discard("workflow")
        plan.workflow_enabled = False

    if plan.workflow_enabled and not any(supports_workflow(item) for item in selected_targets):
        plan.warnings.append(
            "Workflow adaptation needs an explicit workflow-capable target. Auto mode resolved to setup-only targets."
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

    selected_skill_paths = {
        point.resolve(root)
        for target_id in selected_targets
        for point in get_target(target_id).integration_points_for(scope, {"skills"})
        if point.resolve(root) is not None
    }
    if scope == "project" and "skills" in kinds:
        generic_skill_target = get_target("generic")
        generic_skill_integration_point = generic_skill_target.integration_points_for("project", {"skills"})[0]
        generic_skill_path = generic_skill_integration_point.resolve(root)
        if "generic" in selected_targets or generic_skill_path not in selected_skill_paths:
            _add_file(
                files,
                project_dir=root,
                scope=scope,
                target="generic",
                kind="skills",
                path=generic_skill_path,
                artifact=render_skill(generic_skill_target, scope),
                management="file",
                docs_url=generic_skill_integration_point.docs_url,
            )

    adapter_files: list[str] = []
    skipped_files: list[str] = []

    for target_id in selected_targets:
        target_spec = get_target(target_id)
        workflow_adapter_path = workflow_adapter_file_path(target_id) if plan.workflow_enabled and supports_workflow(target_id) else None
        workflow_entrypoint_paths = workflow_entrypoints(target_id) if workflow_adapter_path else ()
        if target_spec.target_id == "generic" and scope == "project":
            pass
        for integration_point in target_spec.integration_points_for(scope):
            if integration_point.kind not in kinds:
                continue
            if integration_point.manual_only or not integration_point.writable or integration_point.path is None:
                if plan.workflow_enabled and workflow_absorbs_integration_point(
                    target_spec.target_id, integration_point, scope=scope
                ):
                    continue
                plan.manual_actions.append(
                    ManualAction(
                        target=target_spec.target_id,
                        kind=integration_point.kind,
                        scope=integration_point.scope,
                        path=integration_point.path,
                        docs_url=integration_point.docs_url,
                        reason=integration_point.note or "Manual-only integration point.",
                        action_reason="Setup can report this integration point, but it does not write it automatically.",
                    )
                )
                continue

            path = integration_point.resolve(root)
            assert path is not None

            if integration_point.kind == "instructions":
                if plan.mode == "adopted" and scope == "project" and path.exists() and target_spec.target_id != "cursor":
                    adapter_file_path = root / ".haxaml" / "setup" / "targets" / f"{target_spec.target_id}.md"
                    skill_point = _target_single_skill_integration_point(target_spec, scope) if "skills" in kinds else None
                    skill_relative = (
                        _relative(skill_point.resolve(root), root, scope)
                        if skill_point is not None and skill_point.resolve(root) is not None
                        else None
                    )
                    adapter_files.append(adapter_file_path.relative_to(root).as_posix())
                    _add_file(
                        files,
                        project_dir=root,
                        scope=scope,
                        target=target_spec.target_id,
                        kind="instructions",
                        path=adapter_file_path,
                        artifact=render_adapter_file(target_spec, root),
                        management="file",
                        docs_url=integration_point.docs_url,
                        note="Managed adapter file for adopted native instructions.",
                        action_reason="Write the full governed adapter alongside the adopted native instruction file.",
                    )
                    _add_file(
                        files,
                        project_dir=root,
                        scope=scope,
                        target=target_spec.target_id,
                        kind="instructions",
                        path=path,
                        artifact=render_pointer_block(
                            target_spec,
                            adapter_file_path.relative_to(root).as_posix(),
                            skill_relative,
                        ),
                        management="pointer",
                        docs_url=integration_point.docs_url,
                        note="Managed pointer block appended to an adopted native instruction file.",
                        action_reason="Append or refresh the managed pointer block inside the adopted native instruction file.",
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
                    artifact=render_instruction(
                        target_spec,
                        scope,
                        root,
                        workflow_adapter_path=workflow_adapter_path,
                        workflow_entrypoint_paths=workflow_entrypoint_paths,
                    ),
                    management="file",
                    docs_url=integration_point.docs_url,
                    action_reason="Write the target-native instruction file managed by Haxaml.",
                )
                continue

            if integration_point.kind == "skills":
                _add_file(
                    files,
                    project_dir=root,
                    scope=scope,
                    target=target_spec.target_id,
                    kind="skills",
                    path=path,
                    artifact=render_skill(
                        target_spec,
                        scope,
                        workflow_adapter_path=workflow_adapter_path,
                        workflow_entrypoint_paths=workflow_entrypoint_paths,
                    ),
                    management="file",
                    docs_url=integration_point.docs_url,
                    action_reason="Write the governed skill file for this target.",
                )
                continue

            if integration_point.kind == "agents":
                _add_file(
                    files,
                    project_dir=root,
                    scope=scope,
                    target=target_spec.target_id,
                    kind="agents",
                    path=path,
                    artifact=render_agent(
                        target_spec,
                        scope,
                        workflow_adapter_path=workflow_adapter_path,
                        workflow_entrypoint_paths=workflow_entrypoint_paths,
                    ),
                    management="file",
                    docs_url=integration_point.docs_url,
                    action_reason="Write the governed agent definition for this target.",
                )
                continue

            if integration_point.kind == "mcp":
                artifact = render_mcp_config(target_spec, integration_point, root)
                if integration_point.format in {"json", "toml"}:
                    existing_text = path.read_text(encoding="utf-8", errors="ignore") if path.exists() else None
                    merge_plan = plan_managed_config_write(
                        existing_text=existing_text,
                        config_format=integration_point.format,
                        desired_content=artifact.content,
                    )
                    if merge_plan.action == "manual":
                        plan.manual_actions.append(
                            ManualAction(
                                target=target_spec.target_id,
                                kind="mcp",
                                scope=integration_point.scope,
                                path=_relative(path, root, scope),
                                docs_url=integration_point.docs_url,
                                reason=merge_plan.reason,
                                preview=merge_plan.preview,
                                action_reason="Manual merge required because the existing config shape is unsafe to edit automatically.",
                            )
                        )
                        continue
                    _add_file(
                        files,
                        project_dir=root,
                        scope=scope,
                        target=target_spec.target_id,
                        kind="mcp",
                        path=path,
                        artifact=artifact,
                        management="merge",
                        docs_url=integration_point.docs_url,
                        format=integration_point.format,
                        preview=merge_plan.preview,
                        action_reason=merge_plan.reason,
                        merge_status=merge_plan.merge_status,
                        managed_key_path=managed_config_key_path(integration_point.format),
                        action_override=merge_plan.action,
                    )
                    continue
                _add_file(
                    files,
                    project_dir=root,
                    scope=scope,
                    target=target_spec.target_id,
                    kind="mcp",
                    path=path,
                    artifact=artifact,
                    management="file",
                    docs_url=integration_point.docs_url,
                    format=integration_point.format,
                    action_reason="Write the target-native MCP config file managed by Haxaml.",
                )

        if plan.workflow_enabled and supports_workflow(target_id):
            for artifact in build_workflow_artifacts(target_id, root):
                _add_file(
                    files,
                    project_dir=root,
                    scope=scope,
                    target=target_id,
                    kind="workflow",
                    path=root / artifact.path,
                    artifact=artifact.artifact,
                    management="file",
                    docs_url=artifact.docs_url,
                    note=artifact.note or "Managed workflow adaptation file.",
                    action_reason="Write the workflow adapter or entrypoint file for this target.",
                )
            for item in workflow_manual_actions(target_id):
                plan.manual_actions.append(
                    ManualAction(
                        target=str(item["target"]),
                        kind=str(item["kind"]),
                        scope=str(item["scope"]),
                        path=item["path"],
                        docs_url=str(item["docs_url"]),
                        reason=str(item["reason"]),
                        action_reason="Workflow follow-up is still manual for this target or entrypoint.",
                    )
                )

    if scope == "project" and plan.mode == "adopted" and adoption_inventory is not None:
        from haxaml.setup.adoption import ADOPTION_REPORT_PATH, ADOPTION_STATE_PATH, dump_adoption_state
        from haxaml.setup.renderer import render_adoption_report

        state = adoption_inventory.to_state(
            selected_targets=selected_targets,
            adapter_files=sorted(set(adapter_files)),
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
                "format": item.format,
                "managed_key_path": item.managed_key_path,
            }
        )

    manifest = {
        "version": get_version(),
        "generator": "haxaml-setup",
        "scope": plan.scope,
        "mode": plan.mode,
        "requested_target": plan.requested_target,
        "requested_targets": plan.requested_targets,
        "selected_targets": plan.selected_targets,
        "selection_source": plan.selection_source,
        "detected_targets": plan.detected_targets,
        "workflow_enabled": plan.workflow_enabled,
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
