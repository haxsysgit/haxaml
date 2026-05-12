"""Target registry for Haxaml setup."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


CORE_SUPPORT = "core"
PARTIAL_SUPPORT = "partial"
GENERIC_SUPPORT = "shared"


@dataclass(frozen=True)
class Surface:
    """A documented target-native surface Haxaml can manage or report on."""

    kind: str
    scope: str
    path: str | None
    docs_url: str
    writable: bool = True
    manual_only: bool = False
    note: str = ""
    format: str = "markdown"

    def resolve(self, project_dir: Path) -> Path | None:
        if self.path is None:
            return None
        if self.scope == "user":
            return Path(self.path).expanduser()
        return project_dir / self.path


@dataclass(frozen=True)
class TargetSpec:
    """One agent/editor target supported by setup."""

    target_id: str
    display_name: str
    support_tier: str
    docs_urls: tuple[str, ...]
    detect_patterns: tuple[str, ...] = ()
    surfaces: tuple[Surface, ...] = ()
    manual_notes: tuple[str, ...] = ()
    project_capabilities: dict[str, bool] = field(default_factory=dict)
    user_capabilities: dict[str, bool] = field(default_factory=dict)

    def surfaces_for(self, scope: str, kinds: set[str] | None = None) -> tuple[Surface, ...]:
        selected = [surface for surface in self.surfaces if surface.scope == scope]
        if kinds is not None:
            selected = [surface for surface in selected if surface.kind in kinds]
        return tuple(selected)


def _caps(*enabled: str) -> dict[str, bool]:
    base = {kind: False for kind in ("instructions", "skills", "agents", "mcp")}
    for kind in enabled:
        base[kind] = True
    return base


TARGETS: tuple[TargetSpec, ...] = (
    TargetSpec(
        target_id="generic",
        display_name="Generic AGENTS",
        support_tier=GENERIC_SUPPORT,
        docs_urls=(),
        surfaces=(
            Surface(
                kind="instructions",
                scope="project",
                path="AGENTS.md",
                docs_url="https://developers.openai.com/codex/guides/agents-md",
            ),
            Surface(
                kind="skills",
                scope="project",
                path=".agents/skills/haxaml/SKILL.md",
                docs_url="https://developers.openai.com/codex/skills",
            ),
        ),
        project_capabilities=_caps("instructions", "skills"),
        user_capabilities=_caps(),
    ),
    TargetSpec(
        target_id="claude",
        display_name="Claude Code",
        support_tier=CORE_SUPPORT,
        docs_urls=(
            "https://code.claude.com/docs/en/memory",
            "https://code.claude.com/docs/en/skills",
            "https://code.claude.com/docs/en/subagents",
            "https://code.claude.com/docs/en/settings",
        ),
        detect_patterns=("CLAUDE.md", ".claude/skills/*/SKILL.md", ".claude/agents/*.md", ".mcp.json"),
        surfaces=(
            Surface("instructions", "project", "CLAUDE.md", "https://code.claude.com/docs/en/memory"),
            Surface("skills", "project", ".claude/skills/haxaml/SKILL.md", "https://code.claude.com/docs/en/skills"),
            Surface("agents", "project", ".claude/agents/haxaml-governor.md", "https://code.claude.com/docs/en/subagents"),
            Surface("mcp", "project", ".mcp.json", "https://code.claude.com/docs/en/settings", format="json"),
            Surface("instructions", "user", "~/.claude/CLAUDE.md", "https://code.claude.com/docs/en/memory"),
            Surface("skills", "user", "~/.claude/skills/haxaml/SKILL.md", "https://code.claude.com/docs/en/skills"),
            Surface("agents", "user", "~/.claude/agents/haxaml-governor.md", "https://code.claude.com/docs/en/subagents"),
            Surface("mcp", "user", "~/.claude.json", "https://code.claude.com/docs/en/settings", format="json"),
        ),
        project_capabilities=_caps("instructions", "skills", "agents", "mcp"),
        user_capabilities=_caps("instructions", "skills", "agents", "mcp"),
    ),
    TargetSpec(
        target_id="codex",
        display_name="OpenAI Codex",
        support_tier=CORE_SUPPORT,
        docs_urls=(
            "https://developers.openai.com/codex/guides/agents-md",
            "https://developers.openai.com/codex/skills",
            "https://developers.openai.com/codex/config-reference",
        ),
        detect_patterns=("AGENTS.md", "AGENTS.override.md", ".agents/skills/*/SKILL.md", ".codex/config.toml"),
        surfaces=(
            Surface("instructions", "project", "AGENTS.md", "https://developers.openai.com/codex/guides/agents-md"),
            Surface("skills", "project", ".agents/skills/haxaml/SKILL.md", "https://developers.openai.com/codex/skills"),
            Surface("mcp", "project", ".codex/config.toml", "https://developers.openai.com/codex/config-reference", format="toml"),
            Surface("instructions", "user", "~/.codex/AGENTS.md", "https://developers.openai.com/codex/guides/agents-md"),
            Surface("skills", "user", "~/.agents/skills/haxaml/SKILL.md", "https://developers.openai.com/codex/skills"),
            Surface("mcp", "user", "~/.codex/config.toml", "https://developers.openai.com/codex/config-reference", format="toml"),
        ),
        project_capabilities=_caps("instructions", "skills", "mcp"),
        user_capabilities=_caps("instructions", "skills", "mcp"),
    ),
    TargetSpec(
        target_id="cursor",
        display_name="Cursor",
        support_tier=CORE_SUPPORT,
        docs_urls=(
            "https://docs.cursor.com/context/rules",
            "https://docs.cursor.com/advanced/model-context-protocol",
        ),
        detect_patterns=(".cursor/rules/*.mdc", ".cursorrules", ".cursor/mcp.json"),
        surfaces=(
            Surface("instructions", "project", ".cursor/rules/haxaml.mdc", "https://docs.cursor.com/context/rules"),
            Surface("mcp", "project", ".cursor/mcp.json", "https://docs.cursor.com/advanced/model-context-protocol", format="json"),
            Surface(
                "instructions",
                "user",
                None,
                "https://docs.cursor.com/context/rules",
                writable=False,
                manual_only=True,
                note="User rules are configured in Cursor Settings, not a stable file path.",
            ),
            Surface("mcp", "user", "~/.cursor/mcp.json", "https://docs.cursor.com/advanced/model-context-protocol", format="json"),
        ),
        manual_notes=("User rules are settings-backed; setup prints guidance instead of guessing a file.",),
        project_capabilities=_caps("instructions", "mcp"),
        user_capabilities=_caps("instructions", "mcp"),
    ),
    TargetSpec(
        target_id="windsurf",
        display_name="Windsurf",
        support_tier=PARTIAL_SUPPORT,
        docs_urls=(
            "https://docs.windsurf.com/windsurf/cascade/agents-md",
            "https://docs.windsurf.com/windsurf/cascade/skills",
            "https://docs.windsurf.com/windsurf/cascade/mcp",
        ),
        detect_patterns=("AGENTS.md", ".windsurf/skills/*/SKILL.md", ".windsurfrules"),
        surfaces=(
            Surface("instructions", "project", "AGENTS.md", "https://docs.windsurf.com/windsurf/cascade/agents-md"),
            Surface("skills", "project", ".agents/skills/haxaml/SKILL.md", "https://docs.windsurf.com/windsurf/cascade/skills"),
            Surface(
                "mcp",
                "project",
                None,
                "https://docs.windsurf.com/windsurf/cascade/mcp",
                writable=False,
                manual_only=True,
                note="Official docs document user-level mcp_config.json; project-local MCP remains guidance-only.",
            ),
            Surface("skills", "user", "~/.agents/skills/haxaml/SKILL.md", "https://docs.windsurf.com/windsurf/cascade/skills"),
            Surface("mcp", "user", "~/.codeium/windsurf/mcp_config.json", "https://docs.windsurf.com/windsurf/cascade/mcp", format="json"),
        ),
        manual_notes=("Project-local Windsurf MCP is not written automatically in 0.7.0.",),
        project_capabilities=_caps("instructions", "skills", "mcp"),
        user_capabilities=_caps("skills", "mcp"),
    ),
    TargetSpec(
        target_id="copilot",
        display_name="GitHub Copilot",
        support_tier=CORE_SUPPORT,
        docs_urls=(
            "https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-custom-instructions",
            "https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-mcp-servers",
            "https://docs.github.com/en/copilot/how-tos/copilot-on-github/customize-copilot/customize-cloud-agent/add-skills",
        ),
        detect_patterns=(".github/copilot-instructions.md", ".github/skills/*/SKILL.md", "~/.copilot/mcp-config.json"),
        surfaces=(
            Surface("instructions", "project", ".github/copilot-instructions.md", "https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-custom-instructions"),
            Surface("skills", "project", ".github/skills/haxaml/SKILL.md", "https://docs.github.com/en/copilot/how-tos/copilot-on-github/customize-copilot/customize-cloud-agent/add-skills"),
            Surface(
                "mcp",
                "project",
                None,
                "https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-mcp-servers",
                writable=False,
                manual_only=True,
                note="Official Copilot CLI docs document the user MCP config path.",
            ),
            Surface("instructions", "user", "~/.copilot/copilot-instructions.md", "https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-custom-instructions"),
            Surface("skills", "user", "~/.copilot/skills/haxaml/SKILL.md", "https://docs.github.com/en/copilot/how-tos/copilot-on-github/customize-copilot/customize-cloud-agent/add-skills"),
            Surface("mcp", "user", "~/.copilot/mcp-config.json", "https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-mcp-servers", format="json"),
        ),
        manual_notes=("Project-level Copilot MCP stays manual until a stable file-backed surface is documented.",),
        project_capabilities=_caps("instructions", "skills", "mcp"),
        user_capabilities=_caps("instructions", "skills", "mcp"),
    ),
    TargetSpec(
        target_id="gemini",
        display_name="Gemini CLI",
        support_tier=CORE_SUPPORT,
        docs_urls=(
            "https://github.com/google-gemini/gemini-cli/blob/main/docs/cli/settings.md",
            "https://github.com/google-gemini/gemini-cli/blob/main/docs/tools/mcp-server.md",
            "https://github.com/google-gemini/gemini-cli/blob/main/docs/cli/cli-reference.md",
        ),
        detect_patterns=("GEMINI.md", ".gemini/settings.json", ".gemini/skills/*/SKILL.md"),
        surfaces=(
            Surface("instructions", "project", "GEMINI.md", "https://github.com/google-gemini/gemini-cli/blob/main/docs/cli/cli-reference.md"),
            Surface("skills", "project", ".gemini/skills/haxaml/SKILL.md", "https://github.com/google-gemini/gemini-cli/blob/main/docs/cli/cli-reference.md"),
            Surface("mcp", "project", ".gemini/settings.json", "https://github.com/google-gemini/gemini-cli/blob/main/docs/tools/mcp-server.md", format="json"),
            Surface("mcp", "user", "~/.gemini/settings.json", "https://github.com/google-gemini/gemini-cli/blob/main/docs/cli/settings.md", format="json"),
            Surface("skills", "user", "~/.gemini/skills/haxaml/SKILL.md", "https://github.com/google-gemini/gemini-cli/blob/main/docs/cli/cli-reference.md"),
        ),
        project_capabilities=_caps("instructions", "skills", "mcp"),
        user_capabilities=_caps("skills", "mcp"),
    ),
    TargetSpec(
        target_id="continue",
        display_name="Continue",
        support_tier=PARTIAL_SUPPORT,
        docs_urls=(
            "https://docs.continue.dev/reference/config",
            "https://docs.continue.dev/customize/deep-dives/mcp",
            "https://docs.continue.dev/customize/rules",
        ),
        detect_patterns=(".continue/rules/*", ".continue/config.yaml"),
        surfaces=(
            Surface("instructions", "project", ".continue/rules/haxaml.md", "https://docs.continue.dev/customize/rules"),
            Surface(
                "mcp",
                "project",
                ".continue/config.yaml",
                "https://docs.continue.dev/customize/deep-dives/mcp",
                manual_only=True,
                note="Continue workspace config is evolving; setup can print a config block but leaves merges to the user.",
                writable=False,
                format="yaml",
            ),
            Surface("instructions", "user", "~/.continue/rules/haxaml.md", "https://docs.continue.dev/customize/rules"),
            Surface("mcp", "user", "~/.continue/config.yaml", "https://docs.continue.dev/reference/config", format="yaml"),
        ),
        manual_notes=("Continue project config merges are manual in 0.7.0.",),
        project_capabilities=_caps("instructions", "mcp"),
        user_capabilities=_caps("instructions", "mcp"),
    ),
    TargetSpec(
        target_id="cline",
        display_name="Cline",
        support_tier=PARTIAL_SUPPORT,
        docs_urls=(
            "https://docs.cline.bot/customization/skills",
            "https://docs.cline.bot/mcp/mcp-overview",
        ),
        detect_patterns=(".clinerules", ".cline/skills/*/SKILL.md"),
        surfaces=(
            Surface("instructions", "project", ".clinerules/haxaml.md", "https://docs.cline.bot/customization/skills"),
            Surface("skills", "project", ".cline/skills/haxaml/SKILL.md", "https://docs.cline.bot/customization/skills"),
            Surface("skills", "user", "~/.cline/skills/haxaml/SKILL.md", "https://docs.cline.bot/customization/skills"),
            Surface(
                "mcp",
                "user",
                "~/.cline/data/settings/cline_mcp_settings.json",
                "https://docs.cline.bot/mcp/mcp-overview",
                format="json",
                manual_only=True,
                writable=False,
                note="Cline MCP file path support needs hardening before automatic writes.",
            ),
        ),
        manual_notes=("Cline support is partial in 0.7.0 and favors printed guidance for MCP.",),
        project_capabilities=_caps("instructions", "skills"),
        user_capabilities=_caps("skills", "mcp"),
    ),
    TargetSpec(
        target_id="opencode",
        display_name="OpenCode",
        support_tier=PARTIAL_SUPPORT,
        docs_urls=(
            "https://opencode.ai/docs/config",
            "https://opencode.ai/docs/skills",
        ),
        detect_patterns=("AGENTS.md", ".opencode/skills/*/SKILL.md", "opencode.json", "opencode.jsonc"),
        surfaces=(
            Surface("instructions", "project", "AGENTS.md", "https://opencode.ai/docs/config"),
            Surface("skills", "project", ".opencode/skills/haxaml/SKILL.md", "https://opencode.ai/docs/skills"),
            Surface("instructions", "user", "~/.config/opencode/AGENTS.md", "https://opencode.ai/docs/config"),
            Surface("skills", "user", "~/.config/opencode/skills/haxaml/SKILL.md", "https://opencode.ai/docs/skills"),
            Surface(
                "mcp",
                "user",
                "~/.config/opencode/opencode.json",
                "https://opencode.ai/docs/config",
                format="json",
                manual_only=True,
                writable=False,
                note="OpenCode MCP config stays manual until the official schema is locked down.",
            ),
        ),
        manual_notes=("OpenCode MCP config is manual-only in 0.7.0.",),
        project_capabilities=_caps("instructions", "skills"),
        user_capabilities=_caps("instructions", "skills", "mcp"),
    ),
    TargetSpec(
        target_id="junie",
        display_name="Junie",
        support_tier=PARTIAL_SUPPORT,
        docs_urls=(
            "https://junie.jetbrains.com/docs/agent-skills.html",
            "https://junie.jetbrains.com/docs/junie-cli-subagents.html",
            "https://junie.jetbrains.com/docs/junie-cli-mcp-configuration.html",
        ),
        detect_patterns=(".junie/AGENTS.md", ".junie/skills/*/SKILL.md", ".junie/agents/*.md", ".junie/mcp/mcp.json"),
        surfaces=(
            Surface("instructions", "project", ".junie/AGENTS.md", "https://junie.jetbrains.com/docs/junie-cli-configuration.html"),
            Surface("skills", "project", ".junie/skills/haxaml/SKILL.md", "https://junie.jetbrains.com/docs/agent-skills.html"),
            Surface("agents", "project", ".junie/agents/haxaml-governor.md", "https://junie.jetbrains.com/docs/junie-cli-subagents.html"),
            Surface("mcp", "project", ".junie/mcp/mcp.json", "https://junie.jetbrains.com/docs/junie-cli-mcp-configuration.html", format="json"),
            Surface("skills", "user", "~/.junie/skills/haxaml/SKILL.md", "https://junie.jetbrains.com/docs/agent-skills.html"),
            Surface("agents", "user", "~/.junie/agents/haxaml-governor.md", "https://junie.jetbrains.com/docs/junie-cli-subagents.html"),
            Surface("mcp", "user", "~/.junie/mcp/mcp.json", "https://junie.jetbrains.com/docs/junie-cli-mcp-configuration.html", format="json"),
        ),
        manual_notes=("Junie registry coverage is partial until official path docs are hardened.",),
        project_capabilities=_caps("instructions", "skills", "agents", "mcp"),
        user_capabilities=_caps("skills", "agents", "mcp"),
    ),
)


SUPPORTED_TARGET_IDS = tuple(target.target_id for target in TARGETS)


def list_targets() -> tuple[TargetSpec, ...]:
    return TARGETS


def get_target(target_id: str) -> TargetSpec:
    for target in TARGETS:
        if target.target_id == target_id:
            return target
    supported = ", ".join(SUPPORTED_TARGET_IDS)
    raise KeyError(f"Unknown target '{target_id}'. Supported targets: {supported}")
