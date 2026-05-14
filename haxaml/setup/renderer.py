"""Render setup-owned files and pointer blocks."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path

from haxaml.setup.markdown import (
    MANAGED_BLOCK_END,
    bullets,
    managed_block_start,
    metadata_comment,
    metadata_json_document,
    metadata_line_comment,
    numbered,
    section,
)
from haxaml.setup.registry import IntegrationPoint, TargetSpec
from haxaml.versioning import get_version


LIFECYCLE = [
    "`about`",
    "`guidance`",
    "`prebuild`",
    "`context_pack`",
    "`build`",
    "`verify`",
    "`record`",
    "`expect_sync`",
]

FALLBACK_STEPS = [
    "Read the local instructions and the relevant source files before editing.",
    "Classify the task, note risks, and state assumptions publicly.",
    "Make the smallest safe change that satisfies the request.",
    "Verify with commands, tests, or direct inspection and report evidence.",
    "Record what changed and any remaining risks before claiming completion.",
]


@dataclass(frozen=True)
class RenderedArtifact:
    """Rendered setup content plus deterministic recipe metadata."""

    content: str
    recipe_hash: str


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _workflow_section(workflow_adapter_path: str | None, workflow_entrypoint_paths: tuple[str, ...]) -> str | None:
    if workflow_adapter_path is None and not workflow_entrypoint_paths:
        return None

    bullets_list = []
    if workflow_adapter_path is not None:
        bullets_list.append(
            "Workflow adaptation lives separately from the base setup. "
            f"Start with the adapter file at `{workflow_adapter_path}` when you need hook, agent, CI, or background-entry behavior."
        )
    if workflow_entrypoint_paths:
        joined = ", ".join(f"`{path}`" for path in workflow_entrypoint_paths)
        bullets_list.append(f"Tool-specific workflow entrypoints are installed at {joined}.")
    bullets_list.append("Use workflow assets to adapt tool-specific runtime behavior back into the Haxaml lifecycle.")
    return section("Workflow Adaptation", bullets(bullets_list))


def _base_instruction_body(
    target: TargetSpec,
    scope: str,
    project_dir: Path,
    *,
    workflow_adapter_path: str | None = None,
    workflow_entrypoint_paths: tuple[str, ...] = (),
) -> str:
    repo_name = project_dir.resolve().name
    scope_label = "repository" if scope == "project" else "user environment"
    docs = bullets([f"[{url}]({url})" for url in target.docs_urls]) if target.docs_urls else "- Shared Haxaml setup policy"
    workflow_section = _workflow_section(workflow_adapter_path, workflow_entrypoint_paths)
    sections = [
            f"# Haxaml Setup for {target.display_name}",
            (
                f"Haxaml governs this {scope_label}. Treat `.haxaml/` as the source of workflow state and "
                "use tool-specific instructions only as adapters into that governed flow."
            ),
        section(
            "Persona",
            bullets(
                [
                    "Act like a pragmatic software engineer working inside an existing codebase.",
                    "Read the smallest relevant slice of the repository before editing.",
                    "Give concise public rationale, not private chain-of-thought transcripts.",
                ]
            ),
        ),
        section(
            "Operating Contract",
            bullets(
                [
                    f"Project root: `{repo_name}`.",
                    "Use Haxaml when the task changes project code, configuration, or governed documentation.",
                    "Treat skipped lifecycle steps as blockers to fix, not warnings to ignore.",
                ]
            ),
        ),
        section("Lifecycle Checklist", numbered(LIFECYCLE)),
    ]
    if workflow_section is not None:
        sections.append(workflow_section)
    sections.extend(
        [
            section(
                "Context Policy",
                bullets(
                    [
                        "Read only the files needed for the current task, then expand outward if the evidence is incomplete.",
                        "Prefer repository facts and tests over prompt assumptions.",
                        "When Haxaml context tools are unavailable, follow the fallback checklist exactly.",
                    ]
                ),
            ),
            section(
                "Output Contract",
                bullets(
                    [
                        "Summarize the task and relevant assumptions in public language.",
                        "State what changed, what was verified, and what risks remain.",
                        "Keep explanations compact and directly checkable from the repository or command output.",
                    ]
                ),
            ),
            section(
                "Reference Examples",
                "\n\n".join(
                    [
                        "### Example 1",
                        bullets(
                            [
                                "Task: add a small feature in one module.",
                                "Behavior: inspect the module, update the narrowest files, run targeted tests, record risks.",
                            ]
                        ),
                        "### Example 2",
                        bullets(
                            [
                                "Task: fix a regression with unclear scope.",
                                "Behavior: classify the risk, inspect callers and tests, keep the fix local, verify before record.",
                            ]
                        ),
                    ]
                ),
            ),
            section("Fallback Path", numbered(FALLBACK_STEPS)),
            section(
                "Escalation Rules",
                bullets(
                    [
                        "Ask before destructive operations, broad refactors, or policy changes.",
                        "Do not overwrite user-authored instruction files unless they are already Haxaml-managed or the user explicitly forces replacement.",
                        "Prefer adapter files and managed pointer blocks when adopting an existing codebase.",
                    ]
                ),
            ),
            section("Docs", docs),
        ]
    )
    return "\n\n".join(sections)


def render_instruction(
    target: TargetSpec,
    scope: str,
    project_dir: Path,
    *,
    workflow_adapter_path: str | None = None,
    workflow_entrypoint_paths: tuple[str, ...] = (),
) -> RenderedArtifact:
    body = _base_instruction_body(
        target,
        scope,
        project_dir,
        workflow_adapter_path=workflow_adapter_path,
        workflow_entrypoint_paths=workflow_entrypoint_paths,
    )
    body_hash = _hash(body)
    metadata = {
        "generator": "haxaml-setup",
        "target": target.target_id,
        "kind": "instructions",
        "scope": scope,
        "version": get_version(),
        "recipe_hash": body_hash,
    }
    content = f"{metadata_comment(metadata)}\n\n{body}\n"
    return RenderedArtifact(content=content, recipe_hash=_hash(content))


def render_adapter_file(target: TargetSpec, project_dir: Path) -> RenderedArtifact:
    body = "\n\n".join(
        [
            f"# Haxaml Managed Adapter for {target.display_name}",
            (
                "This file is the full Haxaml-managed adapter file that native instruction files can point to "
                "during adoption. Keep user-authored native files small and stable by delegating workflow "
                "details here."
            ),
            _base_instruction_body(target, "project", project_dir),
        ]
    )
    body_hash = _hash(body)
    metadata = {
        "generator": "haxaml-setup",
        "target": target.target_id,
        "kind": "adapter_file",
        "scope": "project",
        "version": get_version(),
        "recipe_hash": body_hash,
    }
    content = f"{metadata_comment(metadata)}\n\n{body}\n"
    return RenderedArtifact(content=content, recipe_hash=_hash(content))


def render_skill(
    target: TargetSpec,
    scope: str,
    *,
    workflow_adapter_path: str | None = None,
    workflow_entrypoint_paths: tuple[str, ...] = (),
) -> RenderedArtifact:
    lines = [
        "---",
        "name: haxaml-governed-flow",
        "description: Use when work changes repository code, config, or governed docs and you must follow the Haxaml lifecycle.",
        "---",
        "",
        f"This skill is installed for `{target.display_name}` in `{scope}` scope.",
        "",
    ]
    if workflow_adapter_path is not None or workflow_entrypoint_paths:
        lines.extend(
            [
                "Workflow adaptation:",
                bullets(
                    [
                        item
                        for item in (
                            (
                                f"Start with the adapter file at `{workflow_adapter_path}` when this target enters through hooks, agents, CI, or background runs."
                                if workflow_adapter_path is not None
                                else None
                            ),
                            (
                                "Workflow entrypoints are installed at "
                                + ", ".join(f"`{path}`" for path in workflow_entrypoint_paths)
                                + "."
                                if workflow_entrypoint_paths
                                else None
                            ),
                        )
                        if item is not None
                    ]
                ),
                "",
            ]
        )
    lines.extend(
        [
            "Follow this order:",
            numbered(
                [
                    "Read the active instructions and the relevant repository files.",
                    "Use the Haxaml lifecycle when it is available.",
                    "If lifecycle tooling is unavailable, fall back to the manual checklist.",
                    "Keep edits small, verify them, and report evidence plus risks.",
                ]
            ),
            "",
            "Manual checklist:",
            bullets(FALLBACK_STEPS),
        ]
    )
    body = "\n".join(lines)
    body_hash = _hash(body)
    metadata = {
        "generator": "haxaml-setup",
        "target": target.target_id,
        "kind": "skills",
        "scope": scope,
        "version": get_version(),
        "recipe_hash": body_hash,
    }
    content = f"{metadata_comment(metadata)}\n\n{body}\n"
    return RenderedArtifact(content=content, recipe_hash=_hash(content))


def render_agent(
    target: TargetSpec,
    scope: str,
    *,
    workflow_adapter_path: str | None = None,
    workflow_entrypoint_paths: tuple[str, ...] = (),
) -> RenderedArtifact:
    bullets_list = [
        "Take delegated implementation tasks that fit inside the current repo boundaries.",
        "Read the current Haxaml adapter file or skill before acting.",
        "Return concrete changes, verification evidence, and remaining risks.",
    ]
    if workflow_adapter_path is not None:
        bullets_list.insert(2, f"Use `{workflow_adapter_path}` for tool-specific runtime adaptation before changing repo code.")
    if workflow_entrypoint_paths:
        bullets_list.append("Workflow entrypoints installed for this target: " + ", ".join(f"`{path}`" for path in workflow_entrypoint_paths))
    body = "\n\n".join([f"# Haxaml Governor for {target.display_name}", bullets(bullets_list)])
    body_hash = _hash(body)
    metadata = {
        "generator": "haxaml-setup",
        "target": target.target_id,
        "kind": "agents",
        "scope": scope,
        "version": get_version(),
        "recipe_hash": body_hash,
    }
    content = f"{metadata_comment(metadata)}\n\n{body}\n"
    return RenderedArtifact(content=content, recipe_hash=_hash(content))


def _mcp_payload(project_dir: Path) -> dict[str, object]:
    return {
        "command": "uvx",
        "args": ["haxaml-mcp"],
        "env": {"HAXAML_PROJECT_DIR": str(project_dir.resolve())},
    }


def render_mcp_config(target: TargetSpec, integration_point: IntegrationPoint, project_dir: Path) -> RenderedArtifact:
    metadata = {
        "generator": "haxaml-setup",
        "target": target.target_id,
        "kind": "mcp",
        "scope": integration_point.scope,
        "version": get_version(),
    }
    payload = _mcp_payload(project_dir)
    if integration_point.format == "toml":
        body = "\n".join(
            [
                metadata_line_comment(metadata),
                "[mcp_servers.haxaml]",
                'command = "uvx"',
                'args = ["haxaml-mcp"]',
                f'env = {{ HAXAML_PROJECT_DIR = "{project_dir.resolve()}" }}',
                "",
            ]
        )
    else:
        body = metadata_json_document(metadata, {"mcpServers": {"haxaml": payload}})
    return RenderedArtifact(content=body, recipe_hash=_hash(body))


def render_pointer_block(target: TargetSpec, adapter_path: str) -> RenderedArtifact:
    body = "\n".join(
        [
            "## Haxaml Managed Workflow",
            "",
            (
                "This repository uses Haxaml as the workflow governor. Keep your existing native instructions, "
                f"but follow the managed adapter file at `{adapter_path}` and the skill at `.agents/skills/haxaml/SKILL.md`."
            ),
            "",
            f"Lifecycle: {' -> '.join(step.strip('`') for step in LIFECYCLE)}",
            "",
            "Fallback when tooling is unavailable:",
            bullets(FALLBACK_STEPS),
        ]
    )
    body_hash = _hash(body)
    metadata = {
        "generator": "haxaml-setup",
        "target": target.target_id,
        "kind": "pointer",
        "scope": "project",
        "version": get_version(),
        "recipe_hash": body_hash,
    }
    content = f"{managed_block_start(metadata)}\n{body}\n{MANAGED_BLOCK_END}\n"
    return RenderedArtifact(content=content, recipe_hash=_hash(content))


def render_adoption_report(state: dict[str, object]) -> str:
    detected = state.get("detected_targets", [])
    native_files = state.get("native_files", [])
    conflicts = state.get("analysis", {}).get("conflicts", [])
    adapter_files = state.get("adapter_files", state.get("sidecars", []))
    skipped = state.get("skipped_files", [])
    sections = [
        "# Haxaml Adoption Report",
        "",
        "This report inventories existing native instruction sources and records how Haxaml setup adopted them.",
        "",
        section(
            "Detected Targets",
            bullets([str(item) for item in detected]) if detected else "- None detected.",
        ),
        section(
            "Discovered Files",
            bullets([f"`{item['path']}` ({item['kind']})" for item in native_files]) if native_files else "- None found.",
        ),
        section(
            "Managed Adapter Files",
            bullets([f"`{path}`" for path in adapter_files]) if adapter_files else "- None created.",
        ),
        section(
            "Skipped Files",
            bullets([f"`{item}`" for item in skipped]) if skipped else "- None skipped.",
        ),
        section(
            "Conflicts",
            bullets([f"{item['id']}: {item['rule_summary']}" for item in conflicts]) if conflicts else "- No conflicts detected.",
        ),
        section(
            "Guardrail",
            "Detailed adoption inventory lives under `.haxaml/adoption/`. Core FRAME files only receive the small origin signal.",
        ),
    ]
    return "\n\n".join(sections) + "\n"
