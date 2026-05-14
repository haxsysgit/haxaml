"""Setup-owned workflow adaptation helpers.

Workflow adaptation is intentionally separate from base setup. The setup stack
still owns planning, writing, and drift tracking, while this module provides
target-aware workflow bundles and the shared `workflow check` inspection path.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import re

from haxaml.setup.markdown import bullets, metadata_comment, metadata_json_document, metadata_line_comment, section
from haxaml.setup.registry import IntegrationPoint, get_target
from haxaml.setup.renderer import LIFECYCLE, RenderedArtifact, render_mcp_config
from haxaml.versioning import get_version
from haxaml.yaml_utils import load_yaml


SUPPORTED_WORKFLOW_CONTEXTS = ("entry", "hook", "agent", "background", "ci")
MANIFEST_PATH = ".haxaml/setup/manifest.yaml"
_MANAGED_BLOCK_RE = re.compile(r"<!-- HAXAML:MANAGED START .*?<!-- HAXAML:MANAGED END -->\n?", re.DOTALL)


@dataclass(frozen=True)
class WorkflowFileSpec:
    """One file that participates in workflow adaptation for a target."""

    path: str
    docs_url: str
    template: str
    audit_role: str
    required: bool = True
    is_workflow_entrypoint: bool = False
    context: str = "entry"
    note: str = ""


@dataclass(frozen=True)
class WorkflowManualActionSpec:
    """One advisory follow-up that setup cannot safely automate."""

    reason: str
    audit_role: str
    repair_hint: str = ""


@dataclass(frozen=True)
class WorkflowArtifact:
    """Rendered workflow artifact plus planning metadata."""

    path: str
    docs_url: str
    note: str
    artifact: RenderedArtifact
    required: bool = True


@dataclass(frozen=True)
class WorkflowTargetSpec:
    """Workflow adaptation support for one setup target."""

    target_id: str
    display_name: str
    audit_name: str
    docs_urls: tuple[str, ...]
    files: tuple[WorkflowFileSpec, ...]
    manual_actions: tuple[WorkflowManualActionSpec, ...] = ()
    supported_contexts: tuple[str, ...] = SUPPORTED_WORKFLOW_CONTEXTS


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _workflow_root(target_id: str) -> str:
    return f".haxaml/setup/workflows/{target_id}"


def _workflow_readme(target_id: str) -> str:
    return f"{_workflow_root(target_id)}/README.md"


def _script_path(target_id: str, name: str) -> str:
    return f"{_workflow_root(target_id)}/{name}"


WORKFLOW_TARGETS: tuple[WorkflowTargetSpec, ...] = (
    WorkflowTargetSpec(
        target_id="claude",
        display_name="Claude Code",
        audit_name="Claude",
        docs_urls=(
            "https://code.claude.com/docs/en/hooks",
            "https://code.claude.com/docs/en/settings",
        ),
        files=(
            WorkflowFileSpec(_workflow_readme("claude"), "https://code.claude.com/docs/en/hooks", "readme", "adapter file"),
            WorkflowFileSpec(
                _script_path("claude", "check.sh"),
                "https://code.claude.com/docs/en/hooks",
                "hook_script",
                "hook script",
                context="hook",
            ),
            WorkflowFileSpec(
                ".claude/settings.json",
                "https://code.claude.com/docs/en/settings",
                "claude_settings",
                "hook config",
                is_workflow_entrypoint=True,
            ),
        ),
    ),
    WorkflowTargetSpec(
        target_id="codex",
        display_name="OpenAI Codex",
        audit_name="Codex",
        docs_urls=(
            "https://developers.openai.com/codex/noninteractive",
            "https://developers.openai.com/codex/github-action",
        ),
        files=(
            WorkflowFileSpec(_workflow_readme("codex"), "https://developers.openai.com/codex/noninteractive", "readme", "adapter file"),
            WorkflowFileSpec(
                _script_path("codex", "run-local.sh"),
                "https://developers.openai.com/codex/noninteractive",
                "runner_script",
                "local runner",
                context="entry",
            ),
            WorkflowFileSpec(
                _script_path("codex", "run-ci.sh"),
                "https://developers.openai.com/codex/github-action",
                "runner_script",
                "CI runner",
                context="ci",
            ),
        ),
    ),
    WorkflowTargetSpec(
        target_id="gemini",
        display_name="Gemini CLI",
        audit_name="Gemini",
        docs_urls=(
            "https://github.com/google-gemini/gemini-cli/blob/main/docs/cli/cli-reference.md",
            "https://github.com/google-gemini/gemini-cli/blob/main/docs/cli/settings.md",
        ),
        files=(
            WorkflowFileSpec(
                _workflow_readme("gemini"),
                "https://github.com/google-gemini/gemini-cli/blob/main/docs/cli/cli-reference.md",
                "readme",
                "adapter file",
            ),
            WorkflowFileSpec(
                _script_path("gemini", "run-local.sh"),
                "https://github.com/google-gemini/gemini-cli/blob/main/docs/cli/cli-reference.md",
                "runner_script",
                "local runner",
                context="entry",
            ),
            WorkflowFileSpec(
                _script_path("gemini", "run-ci.sh"),
                "https://github.com/google-gemini/gemini-cli/blob/main/docs/cli/cli-reference.md",
                "runner_script",
                "CI runner",
                context="ci",
            ),
        ),
    ),
    WorkflowTargetSpec(
        target_id="cursor",
        display_name="Cursor",
        audit_name="Cursor",
        docs_urls=("https://docs.cursor.com/en/background-agents",),
        files=(
            WorkflowFileSpec(_workflow_readme("cursor"), "https://docs.cursor.com/en/background-agents", "readme", "adapter file"),
            WorkflowFileSpec(
                ".cursor/environment.json",
                "https://docs.cursor.com/en/background-agents",
                "cursor_environment",
                "background environment",
                is_workflow_entrypoint=True,
                context="background",
            ),
        ),
    ),
    WorkflowTargetSpec(
        target_id="copilot",
        display_name="GitHub Copilot",
        audit_name="Copilot",
        docs_urls=(
            "https://docs.github.com/en/copilot/how-tos/copilot-cli/use-copilot-cli-agents/overview",
            "https://docs.github.com/en/copilot/reference/custom-agents-configuration",
        ),
        files=(
            WorkflowFileSpec(
                _workflow_readme("copilot"),
                "https://docs.github.com/en/copilot/how-tos/copilot-cli/use-copilot-cli-agents/overview",
                "readme",
                "adapter file",
            ),
            WorkflowFileSpec(
                ".github/agents/haxaml-governor.md",
                "https://docs.github.com/en/copilot/reference/custom-agents-configuration",
                "agent_entry",
                "custom agent",
                is_workflow_entrypoint=True,
                context="agent",
            ),
            WorkflowFileSpec(
                ".mcp.json",
                "https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-mcp-servers",
                "copilot_mcp",
                "workflow MCP/config entrypoint",
                is_workflow_entrypoint=True,
            ),
        ),
    ),
    WorkflowTargetSpec(
        target_id="opencode",
        display_name="OpenCode",
        audit_name="OpenCode",
        docs_urls=(
            "https://dev.opencode.ai/docs/agents/",
            "https://dev.opencode.ai/docs/mcp-servers/",
        ),
        files=(
            WorkflowFileSpec(_workflow_readme("opencode"), "https://dev.opencode.ai/docs/agents/", "readme", "adapter file"),
            WorkflowFileSpec(
                ".opencode/agents/haxaml-governor.md",
                "https://dev.opencode.ai/docs/agents/",
                "agent_entry",
                "custom agent",
                is_workflow_entrypoint=True,
                context="agent",
            ),
        ),
        manual_actions=(
            WorkflowManualActionSpec(
                reason="Review `opencode.json` or `opencode.jsonc` and enable the workflow agent's MCP/tool access if your project scopes tools per agent.",
                audit_role="workflow MCP/config entrypoint",
            ),
        ),
    ),
    WorkflowTargetSpec(
        target_id="junie",
        display_name="Junie",
        audit_name="Junie",
        docs_urls=(
            "https://junie.jetbrains.com/docs/junie-cli-subagents.html",
            "https://junie.jetbrains.com/docs/agent-skills.html",
        ),
        files=(
            WorkflowFileSpec(_workflow_readme("junie"), "https://junie.jetbrains.com/docs/junie-cli-subagents.html", "readme", "adapter file"),
            WorkflowFileSpec(
                ".junie/agents/haxaml-governor.md",
                "https://junie.jetbrains.com/docs/junie-cli-subagents.html",
                "agent_entry",
                "custom agent",
                is_workflow_entrypoint=True,
                context="agent",
            ),
        ),
    ),
)


WORKFLOW_TARGET_IDS = tuple(target.target_id for target in WORKFLOW_TARGETS)


def list_workflow_targets() -> tuple[WorkflowTargetSpec, ...]:
    return WORKFLOW_TARGETS


def get_workflow_target(target_id: str) -> WorkflowTargetSpec:
    for target in WORKFLOW_TARGETS:
        if target.target_id == target_id:
            return target
    supported = ", ".join(WORKFLOW_TARGET_IDS)
    raise KeyError(f"Unknown workflow target '{target_id}'. Supported targets: {supported}")


def supports_workflow(target_id: str) -> bool:
    return target_id in WORKFLOW_TARGET_IDS


def _workflow_restore_hint(target_id: str) -> str:
    return f"Re-run `uv run haxaml setup --target {target_id} --with-workflow --force` to restore this Haxaml-managed workflow file."


def _workflow_audit_label(target: WorkflowTargetSpec, audit_role: str) -> str:
    return f"{target.audit_name} {audit_role}"


def workflow_file_audit_metadata(target_id: str, path: str, *, status: str = "installed") -> dict[str, str] | None:
    """Return provider-aware doctor metadata for one workflow-managed file."""

    if status not in {"installed", "missing", "drifted"}:
        raise ValueError(f"Unsupported workflow audit status '{status}'.")
    if not supports_workflow(target_id):
        return None

    target = get_workflow_target(target_id)
    for file in target.files:
        if file.path != path:
            continue
        metadata = {
            "category": "workflow",
            "label": _workflow_audit_label(target, file.audit_role),
        }
        if status != "installed":
            metadata["repair_hint"] = _workflow_restore_hint(target_id)
        return metadata
    return None


def workflow_manual_action_audit_metadata(target_id: str, reason: str) -> dict[str, str] | None:
    """Return provider-aware doctor metadata for one workflow manual action."""

    if not supports_workflow(target_id):
        return None

    target = get_workflow_target(target_id)
    for action in target.manual_actions:
        if action.reason != reason:
            continue
        return {
            "category": "workflow",
            "label": _workflow_audit_label(target, action.audit_role),
            "repair_hint": action.repair_hint or action.reason,
        }

    if reason:
        return {
            "category": "workflow",
            "label": _workflow_audit_label(target, "workflow follow-up"),
            "repair_hint": reason,
        }
    return None


def workflow_adapter_file_path(target_id: str) -> str:
    return _workflow_readme(target_id)


def workflow_entrypoints(target_id: str) -> tuple[str, ...]:
    if not supports_workflow(target_id):
        return ()
    target = get_workflow_target(target_id)
    return tuple(item.path for item in target.files if item.is_workflow_entrypoint)


def workflow_absorbs_integration_point(target_id: str, integration_point: IntegrationPoint, *, scope: str) -> bool:
    if scope != "project":
        return False
    return target_id == "copilot" and integration_point.kind == "mcp"


def _render_markdown(metadata: dict[str, object], body: str) -> RenderedArtifact:
    content = f"{metadata_comment(metadata)}\n\n{body.rstrip()}\n"
    return RenderedArtifact(content=content, recipe_hash=_hash(content))


def _workflow_metadata(target: WorkflowTargetSpec, path: str, template: str) -> dict[str, object]:
    return {
        "generator": "haxaml-setup",
        "target": target.target_id,
        "kind": "workflow",
        "path": path,
        "template": template,
        "version": get_version(),
    }


def _render_workflow_readme(target: WorkflowTargetSpec) -> RenderedArtifact:
    metadata = _workflow_metadata(target, _workflow_readme(target.target_id), "readme")
    entrypoint_paths = workflow_entrypoints(target.target_id)
    body_parts = [
        f"# {target.display_name} Workflow Adaptation",
        (
            "Workflow adaptation is separate from base setup. Base setup installs the normal project integration points. "
            "This pack adapts a target's tool-specific workflow entrypoints back into the governed Haxaml lifecycle."
        ),
        section(
            "Use It For",
            bullets(
                [
                    "Hook-driven steering and gating.",
                    "Custom agent or subagent entrypoints.",
                    "Background or CI entrypoints that should still check governed readiness.",
                ]
            ),
        ),
        section(
            "Installed Files",
            bullets([f"`{item.path}`" for item in target.files]),
        ),
        section(
            "Check Command",
            bullets(
                [
                    f"`uv run haxaml workflow check --target {target.target_id} --context entry` for local entry checks.",
                    f"`uv run haxaml workflow check --target {target.target_id} --context ci --strict` for machine-enforced checks.",
                ]
            ),
        ),
        section(
            "Lifecycle",
            " -> ".join(step.strip("`") for step in LIFECYCLE),
        ),
    ]
    if entrypoint_paths:
        body_parts.append(section("Workflow Entrypoints", bullets([f"`{path}`" for path in entrypoint_paths])))
    if target.manual_actions:
        body_parts.append(section("Manual Follow-Up", bullets([item.reason for item in target.manual_actions])))
    return _render_markdown(metadata, "\n\n".join(body_parts))


def _render_agent_entry(target: WorkflowTargetSpec) -> RenderedArtifact:
    metadata = _workflow_metadata(target, workflow_entrypoints(target.target_id)[0], "agent_entry")
    body = "\n\n".join(
        [
            f"# Haxaml Workflow Governor for {target.display_name}",
            (
                "This workflow entrypoint is intentionally small. "
                f"Use the adapter file at `{workflow_adapter_file_path(target.target_id)}` for the full runtime adaptation details."
            ),
            bullets(
                [
                    f"Run `uv run haxaml workflow check --target {target.target_id} --context agent` before long-running work.",
                    "Route implementation back into the normal Haxaml lifecycle after the entry check passes.",
                    "Return concrete verification evidence and remaining risks when handing work back.",
                ]
            ),
        ]
    )
    return _render_markdown(metadata, body)


def _render_shell_script(target: WorkflowTargetSpec, file: WorkflowFileSpec) -> RenderedArtifact:
    metadata = _workflow_metadata(target, file.path, file.template)
    lines = [
        "#!/usr/bin/env sh",
        metadata_line_comment(metadata),
        "set -eu",
        "",
        "# Respect a caller-provided project dir so nested entrypoints and CI jobs stay deterministic.",
        'ROOT="${HAXAML_PROJECT_DIR:-$(pwd)}"',
        "",
    ]
    if file.template == "hook_script":
        lines.append(
            f'exec uv run haxaml workflow check --dir "$ROOT" --target {target.target_id} --context {file.context} --strict "$@"'
        )
    else:
        lines.extend(
            [
                f'uv run haxaml workflow check --dir "$ROOT" --target {target.target_id} --context {file.context} --strict "$@"',
                "",
                "# Replace the echo below with the actual provider command used by your team.",
                f'echo "{target.display_name} workflow check passed. Add the provider invocation here."',
            ]
        )
    content = "\n".join(lines) + "\n"
    return RenderedArtifact(content=content, recipe_hash=_hash(content))


def _render_cursor_environment(target: WorkflowTargetSpec, project_dir: Path, file: WorkflowFileSpec) -> RenderedArtifact:
    metadata = _workflow_metadata(target, file.path, file.template)
    payload = {
        "env": {
            "HAXAML_PROJECT_DIR": str(project_dir.resolve()),
            "HAXAML_WORKFLOW_TARGET": target.target_id,
            "HAXAML_WORKFLOW_CONTEXT": file.context,
        }
    }
    content = metadata_json_document(metadata, payload)
    return RenderedArtifact(content=content, recipe_hash=_hash(content))


def _render_claude_settings(target: WorkflowTargetSpec) -> RenderedArtifact:
    metadata = _workflow_metadata(target, ".claude/settings.json", "claude_settings")
    payload = {
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "*",
                    "hooks": [
                        {
                            "type": "command",
                            "command": "./.haxaml/setup/workflows/claude/check.sh",
                        }
                    ],
                }
            ]
        }
    }
    content = metadata_json_document(metadata, payload)
    return RenderedArtifact(content=content, recipe_hash=_hash(content))


def _render_workflow_file(target: WorkflowTargetSpec, file: WorkflowFileSpec, project_dir: Path) -> RenderedArtifact:
    if file.template == "readme":
        return _render_workflow_readme(target)
    if file.template == "agent_entry":
        return _render_agent_entry(target)
    if file.template in {"hook_script", "runner_script"}:
        return _render_shell_script(target, file)
    if file.template == "cursor_environment":
        return _render_cursor_environment(target, project_dir, file)
    if file.template == "claude_settings":
        return _render_claude_settings(target)
    if file.template == "copilot_mcp":
        integration_point = IntegrationPoint("mcp", "project", ".mcp.json", file.docs_url, format="json")
        return render_mcp_config(get_target("copilot"), integration_point, project_dir)
    raise ValueError(f"Unknown workflow template '{file.template}'")


def build_workflow_artifacts(target_id: str, project_dir: str | Path) -> tuple[WorkflowArtifact, ...]:
    target = get_workflow_target(target_id)
    root = Path(project_dir).resolve()
    return tuple(
        WorkflowArtifact(
            path=file.path,
            docs_url=file.docs_url,
            note=file.note,
            artifact=_render_workflow_file(target, file, root),
            required=file.required,
        )
        for file in target.files
    )


def workflow_manual_actions(target_id: str) -> tuple[dict[str, str | None], ...]:
    target = get_workflow_target(target_id)
    docs_url = target.docs_urls[0] if target.docs_urls else ""
    return tuple(
        {
            "target": target.target_id,
            "kind": "workflow",
            "scope": "project",
            "path": None,
            "docs_url": docs_url,
            "reason": action.reason,
            "category": "workflow",
            "label": _workflow_audit_label(target, action.audit_role),
            "repair_hint": action.repair_hint or action.reason,
        }
        for action in target.manual_actions
    )


def resolve_workflow_targets(requested_target: str, manifest: dict[str, object] | None = None) -> list[str]:
    if requested_target != "auto":
        return [requested_target]
    if not manifest:
        return []

    selected = manifest.get("selected_targets", [])
    if not isinstance(selected, list):
        return []

    resolved = [item for item in selected if isinstance(item, str) and supports_workflow(item)]
    if resolved:
        return resolved

    managed_files = manifest.get("managed_files", [])
    if not isinstance(managed_files, list):
        return []
    discovered: list[str] = []
    for item in managed_files:
        if not isinstance(item, dict):
            continue
        target_id = item.get("target")
        if isinstance(target_id, str) and supports_workflow(target_id) and target_id not in discovered:
            discovered.append(target_id)
    return discovered


def _load_manifest(project_dir: Path) -> dict[str, object] | None:
    path = project_dir / MANIFEST_PATH
    if not path.exists():
        return None
    return load_yaml(path)


def _manifest_entry_map(manifest: dict[str, object], target_id: str) -> dict[str, dict[str, object]]:
    entries = {}
    for item in manifest.get("managed_files", []):
        if not isinstance(item, dict):
            continue
        if item.get("kind") != "workflow":
            continue
        if item.get("target") != target_id:
            continue
        path = item.get("path")
        if isinstance(path, str):
            entries[path] = item
    return entries


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _hash_managed_file(path: Path, management: str) -> str:
    content = path.read_text(encoding="utf-8", errors="ignore")
    if management == "pointer":
        block_match = _MANAGED_BLOCK_RE.search(content)
        block = block_match.group(0) if block_match is not None else None
        if block is not None:
            return _hash(block)
    return _hash(content)


def run_workflow_check(
    *,
    project_dir: str | Path,
    target: str = "auto",
    context: str = "entry",
    signal: str = "",
    strict: bool = False,
) -> dict[str, object]:
    if context not in SUPPORTED_WORKFLOW_CONTEXTS:
        allowed = ", ".join(SUPPORTED_WORKFLOW_CONTEXTS)
        raise ValueError(f"Unsupported workflow context '{context}'. Allowed values: {allowed}")

    root = Path(project_dir).resolve()
    manifest = _load_manifest(root)
    selected_targets = resolve_workflow_targets(target, manifest)

    issues: list[dict[str, str]] = []
    manual_actions: list[dict[str, str | None]] = []
    next_steps: list[str] = []

    if target != "auto":
        get_workflow_target(target)

    if manifest is None:
        issues.append(
            {
                "severity": "blocking",
                "target": target,
                "path": MANIFEST_PATH,
                "message": "No setup manifest found. Run `haxaml setup --with-workflow` first.",
            }
        )
        if target != "auto":
            next_steps.append(f"Run `haxaml setup --target {target} --with-workflow` from the project root.")
    elif not selected_targets:
        issues.append(
            {
                "severity": "blocking",
                "target": target,
                "path": "",
                "message": "No workflow-managed targets were detected in the setup manifest.",
            }
        )
        next_steps.append("Re-run setup with an explicit workflow-capable target, for example `haxaml setup --target claude --with-workflow`.")

    for target_id in selected_targets:
        target_spec = get_workflow_target(target_id)
        manifest_entries = _manifest_entry_map(manifest or {}, target_id)

        if not manifest_entries:
            issues.append(
                {
                    "severity": "blocking",
                    "target": target_id,
                    "path": "",
                    "message": "Workflow assets are not tracked in the setup manifest for this target.",
                }
            )
            next_steps.append(f"Run `haxaml setup --target {target_id} --with-workflow` to install tracked workflow assets.")
            continue

        for file in target_spec.files:
            resolved = root / file.path
            relative = _relative(resolved, root)
            if not resolved.exists():
                issues.append(
                    {
                        "severity": "blocking",
                        "target": target_id,
                        "path": relative,
                        "message": "Required workflow file is missing.",
                    }
                )
                continue

            entry = manifest_entries.get(relative)
            if entry is None:
                issues.append(
                    {
                        "severity": "warning",
                        "target": target_id,
                        "path": relative,
                        "message": "Workflow file exists but is not tracked by the current setup manifest.",
                    }
                )
                continue

            expected_hash = str(entry.get("recipe_hash", ""))
            if expected_hash and _hash_managed_file(resolved, str(entry.get("management", "file"))) != expected_hash:
                issues.append(
                    {
                        "severity": "warning",
                        "target": target_id,
                        "path": relative,
                        "message": "Workflow file has drifted from the last Haxaml-generated version.",
                    }
                )

        manual_actions.extend(workflow_manual_actions(target_id))
        if target_spec.manual_actions:
            next_steps.append(
                f"Review manual workflow follow-up for {target_spec.display_name} in `{workflow_adapter_file_path(target_id)}`."
            )

    if any(item["severity"] == "warning" for item in issues):
        next_steps.append("Re-run `haxaml setup --with-workflow --force` if you want to restore Haxaml-managed workflow files.")

    blocking_count = sum(1 for item in issues if item["severity"] == "blocking")
    warning_count = sum(1 for item in issues if item["severity"] == "warning")
    ready = blocking_count == 0

    lines = [
        f"Workflow target request: {target}",
        f"Resolved targets: {', '.join(selected_targets) if selected_targets else '(none)'}",
        f"Context: {context}",
        f"Signal: {signal or '(none)'}",
        f"Strict: {'yes' if strict else 'no'}",
        f"Ready: {'yes' if ready else 'no'}",
        f"Blocking issues: {blocking_count}",
        f"Warnings: {warning_count}",
    ]
    lines.append("Issues:")
    if issues:
        for item in issues:
            suffix = f" ({item['path']})" if item["path"] else ""
            lines.append(f"- [{item['severity']}] {item['target']}: {item['message']}{suffix}")
    else:
        lines.append("- none")
    lines.append("Manual Actions:")
    if manual_actions:
        lines.extend([f"- {item['target']}: {item['reason']}" for item in manual_actions])
    else:
        lines.append("- none")
    lines.append("Next Steps:")
    if next_steps:
        deduped = list(dict.fromkeys(next_steps))
        lines.extend([f"- {item}" for item in deduped])
    else:
        lines.append("- none")

    return {
        "target": target,
        "resolved_targets": selected_targets,
        "context": context,
        "signal": signal,
        "strict": strict,
        "ready": ready,
        "issues": issues,
        "manual_actions": manual_actions,
        "next_steps": list(dict.fromkeys(next_steps)),
        "blocking_count": blocking_count,
        "warning_count": warning_count,
        "message": "\n".join(lines),
    }
