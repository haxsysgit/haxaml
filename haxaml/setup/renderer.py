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
    metadata_line_comment,
    numbered,
    section,
)
from haxaml.setup.registry import IntegrationPoint, TargetSpec
from haxaml.versioning import get_version
from haxaml.yaml_utils import dump_yaml


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
    provider_notes = {
        "codex": (
            "Codex expectations",
            bullets(
                [
                    "Use the local workspace, shell tools, and targeted edits instead of describing unexecuted code changes.",
                    "Keep user-facing progress updates concise and factual while work is in flight.",
                    "Prefer repo evidence, tests, and command output over assumptions before you patch files.",
                ]
            ),
        ),
        "claude": (
            "Claude Code expectations",
            bullets(
                [
                    "Start from the smallest relevant file slice and expand only when the evidence is incomplete.",
                    "Use the setup-managed adapter or skill as the governing source before following tool-native memory.",
                    "Return changed files, verification evidence, and remaining risks in compact public language.",
                ]
            ),
        ),
        "gemini": (
            "Gemini CLI expectations",
            bullets(
                [
                    "Treat repo-local instructions and settings as authoritative before relying on session memory.",
                    "When config is involved, show the exact file path and the narrow merged block you intend to touch.",
                    "Keep lifecycle evidence explicit so later agents can resume without replaying the full repo state.",
                ]
            ),
        ),
        "opencode": (
            "OpenCode expectations",
            bullets(
                [
                    "Use the skill as the workflow contract before switching into agent-specific or per-agent config behavior.",
                    "Keep MCP and tool access scoped to the task and report when manual config follow-up is still required.",
                    "Prefer small verified patches over large speculative rewrites.",
                ]
            ),
        ),
    }
    expectation_title, expectation_body = provider_notes.get(
        target.target_id,
        (
            f"{target.display_name} expectations",
            bullets(
                [
                    "Treat this skill as the local workflow contract when work changes repository code, config, or governed docs.",
                    "Read only the files needed for the current task, then verify with direct evidence before claiming success.",
                    "Keep changes narrow, reported publicly, and easy for the next agent to continue.",
                ]
            ),
        ),
    )
    workflow_section = None
    if workflow_adapter_path is not None or workflow_entrypoint_paths:
        workflow_items = []
        if workflow_adapter_path is not None:
            workflow_items.append(
                f"Start with the adapter file at `{workflow_adapter_path}` when this target enters through hooks, agents, CI, or background runs."
            )
        if workflow_entrypoint_paths:
            workflow_items.append(
                "Workflow entrypoints are installed at " + ", ".join(f"`{path}`" for path in workflow_entrypoint_paths) + "."
            )
        workflow_items.append("Use workflow assets to route tool-native entrypoints back into the same Haxaml lifecycle.")
        workflow_section = section("Workflow Adaptation", bullets(workflow_items))

    examples = {
        "generic": "\n\n".join(
            [
                "### Example 1",
                bullets(
                    [
                        "Task: add a small feature in one module.",
                        "Behavior: inspect the module and the closest tests, make the narrowest safe edit, verify it directly, and report the concrete evidence plus remaining risk.",
                    ]
                ),
                "### Example 2",
                bullets(
                    [
                        "Task: update an MCP config entry.",
                        "Behavior: merge only the Haxaml-owned config block, preserve unrelated keys or tables, preview the exact block, and escalate if the file shape is unsafe to edit automatically.",
                    ]
                ),
            ]
        ),
        "codex": "\n\n".join(
            [
                "### Example 1",
                bullets(
                    [
                        "Task: fix a failing repo test in `tests/test_cli.py`.",
                        "Behavior: inspect the failing test and the smallest setup module first, patch the narrowest files, run the targeted test, then report what changed and what still needs attention.",
                    ]
                ),
                "### Example 2",
                bullets(
                    [
                        "Task: add a Codex MCP server entry.",
                        "Behavior: merge only `[mcp_servers.haxaml]` into `.codex/config.toml`, preserve unrelated config, preview the block, and escalate if the existing shape is unsafe to merge.",
                    ]
                ),
            ]
        ),
        "gemini": "\n\n".join(
            [
                "### Example 1",
                bullets(
                    [
                        "Task: adopt an existing `GEMINI.md` repository into governed flow.",
                        "Behavior: inspect the native file, keep user-authored guidance intact, add the managed adapter or pointer behavior only where the setup policy allows it, and verify the resulting paths.",
                    ]
                ),
                "### Example 2",
                bullets(
                    [
                        "Task: update `.gemini/settings.json` for MCP access.",
                        "Behavior: merge only `mcpServers.haxaml`, keep unrelated settings untouched, preview the merged entry, and flag manual follow-up if the file shape conflicts.",
                    ]
                ),
            ]
        ),
    }
    body = "\n\n".join(
        [
            "# Haxaml Governed Flow",
            f"This skill is installed for `{target.display_name}` in `{scope}` scope and governs repository-changing work through the Haxaml lifecycle.",
            section(
                "Use When",
                bullets(
                    [
                        "The task changes repository code, configuration, or governed documentation.",
                        "You need a deterministic flow for materials, planning, verification, and recorded outcomes.",
                        "The repo has setup-managed instructions, skills, or workflow entrypoints that should stay aligned.",
                    ]
                ),
            ),
            section(
                "Do Not Use",
                bullets(
                    [
                        "The request is casual, off-topic, or does not touch governed repo state.",
                        "A one-off answer can be given safely without entering the repo workflow.",
                        "The task belongs to a different specialized skill or tool contract that explicitly owns the work.",
                    ]
                ),
            ),
            section(
                "Required Inputs",
                bullets(
                    [
                        "A concrete task statement, the relevant repository path, and any known target files or tests.",
                        "Any owner-provided materials, credentials, schema details, or environment constraints needed before building.",
                        "Whether workflow adaptation is involved through hooks, agents, background runs, or CI entrypoints.",
                    ]
                ),
            ),
            section(
                "Lifecycle Flow",
                numbered(
                    [
                        "Read the active setup-managed instructions and the smallest relevant repository slice.",
                        "Use the Haxaml lifecycle when it is available: about, guidance, prebuild, context_pack, build, verify, record, expect_sync.",
                        "If lifecycle tooling is unavailable, follow the manual fallback checklist exactly.",
                        "Gather missing materials before building, then make the smallest safe change that satisfies the task.",
                        "Verify with direct evidence and report what changed, what was checked, and what still risks failure.",
                    ]
                ),
            ),
            workflow_section or "",
            section(expectation_title, expectation_body),
            section(
                "Success Criteria",
                bullets(
                    [
                        "The change follows the lifecycle or documented fallback path instead of skipping straight to edits.",
                        "Required materials, assumptions, verification evidence, and residual risks are explicit in the final report.",
                        "Edits stay narrow, reversible, and aligned with setup-managed instructions for this target.",
                    ]
                ),
            ),
            section(
                "Output Contract",
                bullets(
                    [
                        "Summarize the task, relevant assumptions, and the concrete files or configs touched.",
                        "State what was verified and cite the command, test, or direct inspection that produced the evidence.",
                        "Call out any remaining risks, manual follow-up, or unresolved ambiguity before claiming completion.",
                    ]
                ),
            ),
            section(
                "Escalation Rules",
                bullets(
                    [
                        "Ask before destructive operations, broad refactors, policy changes, or replacing user-authored native instructions.",
                        "Escalate when required materials are missing, the config shape is unsafe to merge, or target ownership is ambiguous.",
                        "Do not silently drop provider-native files that setup is supposed to preserve or adopt.",
                    ]
                ),
            ),
            section("Fallback Path", numbered(FALLBACK_STEPS)),
            section("Examples", examples.get(target.target_id, examples["generic"])),
        ]
    ).replace("\n\n\n", "\n\n")
    body_hash = _hash(body)
    frontmatter = {
        "name": "haxaml-governed-flow",
        "description": "Use when work changes repository code, config, or governed docs and you must follow the Haxaml lifecycle.",
        "metadata": {
            "generator": "haxaml-setup",
            "target": target.target_id,
            "kind": "skills",
            "scope": scope,
            "version": get_version(),
            "recipe_hash": body_hash,
        },
    }
    frontmatter_text = dump_yaml(frontmatter, sort_keys=False).strip()
    content = f"---\n{frontmatter_text}\n---\n\n{body}\n"
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
    payload = _mcp_payload(project_dir)
    if integration_point.format == "toml":
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
        body = json.dumps({"mcpServers": {"haxaml": payload}}, indent=2) + "\n"
    return RenderedArtifact(content=body, recipe_hash=_hash(body))


def render_pointer_block(target: TargetSpec, adapter_path: str, skill_path: str | None = None) -> RenderedArtifact:
    skill_note = (
        f" and the governed skill at `{skill_path}`"
        if skill_path
        else ""
    )
    body = "\n".join(
        [
            "## Haxaml Managed Workflow",
            "",
            (
                "This repository uses Haxaml as the workflow governor. Keep your existing native instructions, "
                f"but follow the managed adapter file at `{adapter_path}`{skill_note}."
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
