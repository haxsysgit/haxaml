"""Render setup-owned files and pointer blocks."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path

from haxaml.setup.markdown import (
    MANAGED_BLOCK_END,
    bullets,
    code_block,
    managed_block_start,
    metadata_comment,
    numbered,
    section,
)
from haxaml.setup.registry import Surface, TargetSpec
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


def _base_instruction_body(target: TargetSpec, scope: str, project_dir: Path) -> str:
    repo_name = project_dir.resolve().name
    scope_label = "repository" if scope == "project" else "user environment"
    docs = bullets([f"[{url}]({url})" for url in target.docs_urls]) if target.docs_urls else "- Shared Haxaml setup policy"
    return "\n\n".join(
        [
            f"# Haxaml Setup for {target.display_name}",
            (
                f"Haxaml governs this {scope_label}. Treat `.haxaml/` as the source of workflow state and "
                "use target-native instructions only as adapters into that governed flow."
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
                        "Prefer sidecars and managed pointer blocks when adopting an existing codebase.",
                    ]
                ),
            ),
            section("Docs", docs),
        ]
    )


def render_instruction(target: TargetSpec, scope: str, project_dir: Path) -> RenderedArtifact:
    body = _base_instruction_body(target, scope, project_dir)
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


def render_sidecar(target: TargetSpec, project_dir: Path) -> RenderedArtifact:
    body = "\n\n".join(
        [
            f"# Haxaml Managed Adapter for {target.display_name}",
            (
                "This file is the full Haxaml-managed adapter that native instruction files can point to "
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
        "kind": "sidecar",
        "scope": "project",
        "version": get_version(),
        "recipe_hash": body_hash,
    }
    content = f"{metadata_comment(metadata)}\n\n{body}\n"
    return RenderedArtifact(content=content, recipe_hash=_hash(content))


def render_skill(target: TargetSpec, scope: str) -> RenderedArtifact:
    body = "\n".join(
        [
            "---",
            "name: haxaml-governed-flow",
            "description: Use when work changes repository code, config, or governed docs and you must follow the Haxaml lifecycle.",
            "---",
            "",
            f"This skill is installed for `{target.display_name}` in `{scope}` scope.",
            "",
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


def render_agent(target: TargetSpec, scope: str) -> RenderedArtifact:
    body = "\n\n".join(
        [
            f"# Haxaml Governor for {target.display_name}",
            bullets(
                [
                    "Take delegated implementation tasks that fit inside the current repo boundaries.",
                    "Read the current Haxaml sidecar or skill before acting.",
                    "Return concrete changes, verification evidence, and remaining risks.",
                ]
            ),
        ]
    )
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


def render_mcp_config(target: TargetSpec, surface: Surface, project_dir: Path) -> RenderedArtifact:
    payload = _mcp_payload(project_dir)
    if surface.format == "toml":
        body = "\n".join(
            [
                "[mcp_servers.haxaml]",
                'command = "uvx"',
                'args = ["haxaml-mcp"]',
                f'env = {{ HAXAML_PROJECT_DIR = "{project_dir.resolve()}" }}',
                "",
            ]
        )
    else:
        body = json.dumps({"mcpServers": {"haxaml": payload}}, indent=2, sort_keys=True) + "\n"
    return RenderedArtifact(content=body, recipe_hash=_hash(body))


def render_pointer_block(target: TargetSpec, sidecar_path: str) -> RenderedArtifact:
    body = "\n".join(
        [
            "## Haxaml Managed Workflow",
            "",
            (
                "This repository uses Haxaml as the workflow governor. Keep your existing native instructions, "
                f"but follow the managed adapter in `{sidecar_path}` and the skill at `.agents/skills/haxaml/SKILL.md`."
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
    sidecars = state.get("sidecars", [])
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
            "Managed Sidecars",
            bullets([f"`{path}`" for path in sidecars]) if sidecars else "- None created.",
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
