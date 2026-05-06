"""Deterministic adoption helpers for existing projects.

Haxaml does not infer project truth. Adoption scans native agent instruction
files and creates a governed place for an AI agent to derive FRAME from them.
"""

from dataclasses import dataclass
import re
from pathlib import Path
from typing import Iterable

import yaml

from haxaml.paths import frame_dir, frame_path, resolve_frame_file
from haxaml.versioning import get_version


FRAME_FILES = ("facts.yaml", "rules.yaml", "acts.yaml", "expect.yaml")
ADOPTION_REPORT = "ADOPTION.md"

NATIVE_FILE_SPECS = (
    ("claude", "Claude Code", ("CLAUDE.md",)),
    ("codex", "OpenAI Codex", ("AGENTS.md",)),
    ("copilot", "GitHub Copilot", (".github/copilot-instructions.md",)),
    ("cursor", "Cursor", (".cursor/rules/*", ".cursorrules")),
    ("windsurf", "Windsurf / Cascade", (".windsurf/rules/*", ".windsurfrules")),
    ("gemini", "Gemini CLI", ("GEMINI.md",)),
)

CONTEXT_FILE_SPECS = (
    ("README.md",),
    ("package.json",),
    ("setup.py",),
    ("pyproject.toml",),
    ("requirements.txt",),
    ("Cargo.toml",),
    ("go.mod",),
)

_DIRECTIVE_MARKERS = (
    "must",
    "should",
    "do not",
    "don't",
    "never",
    "always",
    "only",
    "must not",
)
_NEGATION_MARKERS = ("do not", "don't", "never", "must not", "cannot", "can't", "no ")
_README_AGENT_HEADING_MARKERS = (
    "agent",
    "ai",
    "instruction",
    "copilot",
    "claude",
    "codex",
    "cursor",
    "windsurf",
    "gemini",
)
_RECOMMENDED_NEXT_ACTION = "decide_authoritative_source_then_update_frame"


@dataclass(frozen=True)
class FoundFile:
    """A discovered project file relevant to adoption."""

    kind: str
    label: str
    path: str


@dataclass(frozen=True)
class AdoptionPlan:
    """Result of scanning a project for existing AI-native context."""

    project_dir: Path
    native_files: tuple[FoundFile, ...]
    context_files: tuple[FoundFile, ...]
    existing_frame_files: tuple[str, ...]

    @property
    def has_sources(self) -> bool:
        return bool(self.native_files or self.context_files)

    @property
    def has_existing_frame(self) -> bool:
        return bool(self.existing_frame_files)


@dataclass(frozen=True)
class InstructionDirective:
    normalized: str
    topic: str
    polarity: str
    source: FoundFile
    scope: str


def analyze_adoption_instructions(plan: AdoptionPlan) -> dict:
    """Return deterministic metadata-only instruction analysis for adoption."""
    directives = _collect_directives(plan)
    groups: dict[str, list[InstructionDirective]] = {}
    for item in directives:
        groups.setdefault(item.normalized, []).append(item)

    duplicates = []
    dup_counter = 0
    for normalized in sorted(groups):
        items = groups[normalized]
        unique_sources = {_source_key(d.source, d.scope) for d in items}
        if len(unique_sources) < 2:
            continue
        dup_counter += 1
        duplicates.append(
            {
                "id": f"adopt-duplicate-{dup_counter:03d}",
                "rule_summary": normalized,
                "sources": _sorted_source_refs(items),
            }
        )

    # Duplicates look for the same normalized rule repeated across sources,
    # while conflicts look for the same topic expressed with opposing polarity.
    topic_groups: dict[str, list[InstructionDirective]] = {}
    for item in directives:
        if item.topic:
            topic_groups.setdefault(item.topic, []).append(item)

    conflicts = []
    conflict_counter = 0
    for topic in sorted(topic_groups):
        items = topic_groups[topic]
        polarities = {item.polarity for item in items}
        if len(polarities) < 2:
            continue
        unique_sources = {_source_key(d.source, d.scope) for d in items}
        if len(unique_sources) < 2:
            continue
        conflict_counter += 1
        conflicts.append(
            {
                "id": f"adopt-conflict-{conflict_counter:03d}",
                "category": "precedence_conflict",
                "severity": "warning",
                "rule_summary": topic,
                "sources": _sorted_source_refs(items),
                "requires_user_choice": True,
                "why_it_matters": "Conflicting instruction sources can cause inconsistent agent behavior unless one source is chosen as authoritative.",
                "recommended_next_action": _RECOMMENDED_NEXT_ACTION,
            }
        )

    precedence_candidates = []
    seen = set()
    for conflict in conflicts:
        for source in conflict["sources"]:
            key = (source["kind"], source["path"], source["scope"])
            if key in seen:
                continue
            seen.add(key)
            precedence_candidates.append(source)

    readme_sections_scanned = len(_readme_agent_sections(plan.project_dir))
    sources_scanned = len(plan.native_files) + readme_sections_scanned
    return {
        "conflicts": conflicts,
        "duplicates": duplicates,
        "precedence_decision_required": bool(conflicts),
        "precedence_candidates": precedence_candidates,
        "counts": {
            "conflicts": len(conflicts),
            "duplicates": len(duplicates),
            "sources_scanned": sources_scanned,
            "readme_sections_scanned": readme_sections_scanned,
        },
    }


def scan_native_sources(project_dir: str | Path) -> AdoptionPlan:
    """Scan a project for native agent files and basic repo context files."""
    project = Path(project_dir).resolve()
    native = []
    context = []

    for agent, label, patterns in NATIVE_FILE_SPECS:
        for path in _find_patterns(project, patterns):
            native.append(FoundFile(agent, label, _relative(project, path)))

    for patterns in CONTEXT_FILE_SPECS:
        for path in _find_patterns(project, patterns):
            context.append(FoundFile("context", "Repository context", _relative(project, path)))

    existing_frame = tuple(
        _relative(project, path)
        for name in FRAME_FILES
        for path in [resolve_frame_file(project, name)]
        if path
    )

    return AdoptionPlan(
        project_dir=project,
        native_files=tuple(sorted(native, key=lambda f: f.path)),
        context_files=tuple(sorted(context, key=lambda f: f.path)),
        existing_frame_files=existing_frame,
    )


def write_adoption_scaffold(plan: AdoptionPlan, force: bool = False) -> list[Path]:
    """Write an adoption report and missing FRAME files.

    Existing FRAME files are left untouched unless force=True.
    """
    project = plan.project_dir
    written = []

    haxaml_dir = frame_dir(project)
    haxaml_dir.mkdir(parents=True, exist_ok=True)

    report_path = haxaml_dir / ADOPTION_REPORT
    if force or not report_path.exists():
        report_path.write_text(render_adoption_report(plan), encoding="utf-8")
        written.append(report_path)

    templates = {
        "facts.yaml": _facts_template(plan),
        "rules.yaml": _rules_template(plan),
        "acts.yaml": _acts_template(plan),
        "expect.yaml": _expect_template(plan),
    }
    for filename, data in templates.items():
        path = frame_path(project, filename)
        existing = resolve_frame_file(project, filename)
        # Adoption should not silently overwrite already-curated FRAME unless
        # the caller explicitly chose a forceful reset.
        if existing and not force:
            continue
        _write_yaml(path, data)
        written.append(path)

    return written


def render_adoption_report(plan: AdoptionPlan) -> str:
    """Render a human-readable adoption report."""
    analysis = analyze_adoption_instructions(plan)
    lines = [
        "# Haxaml Adoption Report",
        "",
        "This report is deterministic. Haxaml scanned for known project context files; it did not infer project facts.",
        "",
        "## Native Agent Files",
        "",
    ]

    if plan.native_files:
        for found in plan.native_files:
            lines.append(f"- {found.label}: `{found.path}`")
    else:
        lines.append("- None found.")

    lines.extend(["", "## Repository Context Files", ""])
    if plan.context_files:
        for found in plan.context_files:
            lines.append(f"- `{found.path}`")
    else:
        lines.append("- None found.")

    lines.extend(["", "## Instruction Analysis", ""])
    counts = analysis["counts"]
    lines.append(
        f"- Conflicts: {counts['conflicts']} | Duplicates: {counts['duplicates']} | "
        f"Sources scanned: {counts['sources_scanned']}"
    )
    if analysis["precedence_decision_required"]:
        lines.append("- Precedence decision required: yes")
    else:
        lines.append("- Precedence decision required: no")
    if analysis["conflicts"]:
        lines.append("")
        lines.append("Conflicts:")
        for conflict in analysis["conflicts"]:
            sources = ", ".join(
                f"{source['path']} ({source['scope']})" for source in conflict["sources"]
            )
            lines.append(f"- [{conflict['id']}] {conflict['rule_summary']} -> {sources}")
    if analysis["duplicates"]:
        lines.append("")
        lines.append("Duplicates:")
        for duplicate in analysis["duplicates"]:
            sources = ", ".join(
                f"{source['path']} ({source['scope']})" for source in duplicate["sources"]
            )
            lines.append(f"- [{duplicate['id']}] {duplicate['rule_summary']} -> {sources}")

    lines.extend(["", "## Existing FRAME Files", ""])
    if plan.existing_frame_files:
        for filename in plan.existing_frame_files:
            lines.append(f"- `{filename}`")
    else:
        lines.append("- None found.")

    lines.extend(
        [
            "",
            "## Adoption Runs",
            "",
            "1. AI agent reads the native files and repo context listed above.",
            "2. AI agent derives real FRAME facts, rules, acts, and expectations from the evidence.",
            "3. Haxaml validates the FRAME files with `haxaml validate --dir .`.",
            "4. Haxaml exports a neutral shared file with `haxaml export` and optionally per-agent files when explicitly requested.",
            "",
            "## Guardrail",
            "",
            "Do not treat this report as project understanding. It is only an evidence inventory and adoption checklist.",
            "",
        ]
    )

    return "\n".join(lines)


def _find_patterns(project: Path, patterns: Iterable[str]) -> list[Path]:
    found = []
    for pattern in patterns:
        if any(char in pattern for char in "*?[]"):
            found.extend(path for path in project.glob(pattern) if path.is_file())
            continue
        path = project / pattern
        if path.is_file():
            found.append(path)
    return found


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return ""


def _readme_agent_sections(project: Path) -> list[tuple[str, str]]:
    readme = project / "README.md"
    if not readme.is_file():
        return []
    content = _read_text(readme)
    if not content:
        return []

    sections = []
    current_heading = ""
    current_lines: list[str] = []

    def _flush() -> None:
        nonlocal current_heading, current_lines
        heading = current_heading.strip()
        # README is only treated as agent evidence when the heading itself
        # signals agent instructions; generic prose should not become rules.
        if heading and _is_agent_heading(heading):
            scope = f"README.md#{_slugify(heading)}"
            sections.append((scope, "\n".join(current_lines).strip()))
        current_lines = []

    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            _flush()
            current_heading = stripped.lstrip("#").strip()
            continue
        current_lines.append(line)
    _flush()
    return sections


def _is_agent_heading(heading: str) -> bool:
    lowered = heading.lower()
    return any(marker in lowered for marker in _README_AGENT_HEADING_MARKERS)


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "section"


def _collect_directives(plan: AdoptionPlan) -> list[InstructionDirective]:
    directives: list[InstructionDirective] = []
    project = plan.project_dir
    for found in plan.native_files:
        content = _read_text(project / found.path)
        if not content:
            continue
        for directive in _extract_directives(content):
            directives.append(
                InstructionDirective(
                    normalized=directive["normalized"],
                    topic=directive["topic"],
                    polarity=directive["polarity"],
                    source=found,
                    scope="file",
                )
            )

    for scope, content in _readme_agent_sections(project):
        source = FoundFile("context", "Repository context", "README.md")
        for directive in _extract_directives(content):
            directives.append(
                InstructionDirective(
                    normalized=directive["normalized"],
                    topic=directive["topic"],
                    polarity=directive["polarity"],
                    source=source,
                    scope=scope,
                )
            )
    return directives


def _extract_directives(content: str) -> list[dict[str, str]]:
    out = []
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        cleaned = re.sub(r"^([-*+]\s+|\d+\.\s+|\[[ xX]\]\s+)", "", stripped).strip()
        lowered = cleaned.lower()
        # The adoption scan intentionally stays conservative: if a line does not
        # contain directive markers, we do not treat it as governance evidence.
        if not any(marker in lowered for marker in _DIRECTIVE_MARKERS):
            continue
        normalized = _normalize_rule(cleaned)
        if len(normalized) < 8:
            continue
        topic = _normalize_rule(_topic_from_rule(normalized))
        polarity = "negative" if _is_negative(normalized) else "positive"
        out.append({"normalized": normalized, "topic": topic, "polarity": polarity})
    return out


def _normalize_rule(text: str) -> str:
    norm = text.lower().replace("`", "")
    norm = re.sub(r"\s+", " ", norm).strip()
    norm = norm.strip(" .;,:")
    return norm


def _is_negative(text: str) -> bool:
    return any(marker in text for marker in _NEGATION_MARKERS)


def _topic_from_rule(rule: str) -> str:
    topic = rule
    # Strip modal phrasing so "must update acts" and "do not update acts" can
    # be compared as the same topic with different polarity.
    topic = re.sub(r"\b(do not|don't|never|must not|cannot|can't|must|should|always|only)\b", "", topic)
    topic = re.sub(r"\s+", " ", topic).strip(" .;,:")
    return topic or rule


def _source_key(source: FoundFile, scope: str) -> tuple[str, str, str]:
    return source.kind, source.path, scope


def _sorted_source_refs(items: list[InstructionDirective]) -> list[dict[str, str]]:
    refs = {}
    for item in items:
        key = _source_key(item.source, item.scope)
        refs[key] = {
            "kind": item.source.kind,
            "label": item.source.label,
            "path": item.source.path,
            "scope": item.scope,
        }
    return [refs[key] for key in sorted(refs)]


def _relative(project: Path, path: Path) -> str:
    return path.relative_to(project).as_posix()


def _source_paths(plan: AdoptionPlan) -> list[str]:
    return [found.path for found in plan.native_files] + [found.path for found in plan.context_files]


def _facts_template(plan: AdoptionPlan) -> dict:
    source_paths = _source_paths(plan)
    version = get_version()
    return {
        "identity": {
            "name": plan.project_dir.name,
            "version": version,
            "description": "Existing project adopted into FRAME governance by Haxaml.",
        },
        "goal": {
            "purpose": "Adopt the existing project into explicit FRAME governance.",
            "scope": "Derive project facts, rules, current acts, and expected runs from existing native AI files and repository context.",
            "out_of_scope": [
                "Changing application behavior during adoption",
                "Treating Haxaml as an AI inference engine",
            ],
        },
        "stack": {
            "language": "unknown",
            "backend": "unknown",
            "frontend": "unknown",
            "runtime": "unknown",
            "package_manager": "unknown",
        },
        "architecture": {
            "pattern": "unknown",
            "reasoning": "Must be derived by the AI agent from repository evidence.",
            "boundaries": [],
        },
        "database": {
            "type": "unknown",
            "connection": "unknown",
            "migrations": "unknown",
        },
        "tools": {
            "testing": "unknown",
            "mcp": [],
            "ci": "unknown",
            "other": source_paths,
        },
        "services": [],
        "constraints": [
            "Haxaml must not infer project truth; the AI agent must derive it from evidence.",
            "Do not change application behavior during FRAME adoption unless explicitly requested.",
        ],
        "success_criteria": [
            "FRAME files contain real project decisions and validate.",
            "Native agent files can be regenerated from FRAME exports.",
        ],
        "roles": [
            {
                "name": "AI agent",
                "responsibility": "Reads evidence and derives real FRAME content.",
            },
            {
                "name": "Haxaml",
                "responsibility": "Scans files, validates FRAME, exports native instructions, and records governed runs.",
            },
        ],
        "features": [
            {
                "name": "native-file-adoption",
                "description": "Adopt existing AI-native instruction files into FRAME governance.",
                "status": "in_progress",
                "priority": "critical",
            }
        ],
        "unresolved": [
            {
                "item": "Project identity, stack, architecture, database, tools, and success criteria",
                "reason": "Haxaml only found source files; the AI agent must derive actual facts from those files and code.",
                "blocking": True,
            }
        ],
    }


def _rules_template(plan: AdoptionPlan) -> dict:
    source_paths = _source_paths(plan)
    then_read = [".haxaml/ADOPTION.md", ".haxaml/expect.yaml"] + source_paths
    version = get_version()
    return {
        "governance": {"system": "haxaml", "version": version},
        "before_task": {
            "read_first": [".haxaml/facts.yaml", ".haxaml/rules.yaml", ".haxaml/acts.yaml"],
            "then_read": then_read,
            "check": [
                "Confirm whether this is an adoption run or a normal implementation run.",
                "Use native agent files and repository context as evidence, not as unquestioned truth.",
                "Do not proceed with implementation while blocking facts remain unresolved.",
            ],
        },
        "boundaries": {
            "modules": {},
            "rules": [
                "During adoption, edit FRAME and generated instruction files before touching application source.",
                "Only change application source after the user requests implementation work.",
            ],
        },
        "while_coding": {
            "constraints": [
                "Keep adoption changes separate from feature or bug-fix changes.",
                "Record unknowns explicitly instead of guessing.",
            ],
            "discipline": [
                "Run haxaml validate after FRAME edits.",
                "Regenerate native files only after FRAME is coherent.",
                "Use accurate commit messages in plain language.",
                "Do not use commit prefixes like fix:, feat:, refactor:, chore:, or docs:.",
            ],
        },
        "after_task": {
            "report": ["What evidence was used", "What FRAME files changed", "Remaining unresolved facts"],
            "update": [".haxaml/acts.yaml", ".haxaml/expect.yaml"],
            "verify": ["haxaml validate --dir ."],
        },
        "forbidden": [
            "Do not claim Haxaml inferred project intent.",
            "Do not use README.md as the primary operating target when native agent files exist.",
            "Do not overwrite existing FRAME files unless --force was intentionally used.",
        ],
        "escalation": {
            "act_independently": ["Inventory native agent files and draft FRAME adoption scaffolds."],
            "ask_first": ["Application architecture changes", "New dependencies", "Destructive operations"],
        },
    }


def _acts_template(plan: AdoptionPlan) -> dict:
    return {
        "current_phase": "Adoption",
        "active_task": {
            "name": "Derive FRAME from native agent files",
            "description": "Use the adoption report and discovered project context to replace scaffolded unknowns with real project decisions.",
        },
        "completed_tasks": [],
        "blocked_tasks": [],
        "decisions": [
            {
                "decision": "Adopt existing project through native AI-agent files and repository context.",
                "reasoning": "Existing projects already communicate with agents through their supported native instruction files.",
                "reversible": True,
            }
        ],
        "unresolved_dependencies": [
            {
                "item": "AI-derived project facts from discovered sources",
                "blocking": True,
                "owner": "AI agent / user",
            }
        ],
        "runs": [],
        "compaction": {
            "last_compacted": None,
            "total_runs_compacted": 0,
            "summary": "No adoption runs have been compacted yet.",
        },
    }


def _expect_template(plan: AdoptionPlan) -> dict:
    uses_map = len(plan.native_files) > 3
    return {
        "planning": {
            "goal": "Adopt the existing project into FRAME governance without changing application behavior.",
            "strategy": "First inventory evidence, then derive real FRAME files, validate them, and export normalized native agent files.",
            "estimated_runs": 2,
            "project_size": "small",
            "map_required": uses_map,
            "map_reason": (
                "Many native agent files were found; .haxaml/map.yaml can help preserve boundaries during adoption."
                if uses_map
                else "Adoption is small enough to start with facts, rules, acts, and expect."
            ),
        },
        "map_policy": {
            "small_project_max_runs": 5,
            "medium_project_max_runs": 12,
            "require_map_when": [
                "estimated_runs is greater than 12",
                "the project has 10 or more modules",
                "multiple runs touch three or more modules at once",
                "native files contain conflicting module ownership or cross-module rules",
            ],
            "agent_instruction": "When map_required is true or a run has uses_map=true, read .haxaml/map.yaml before touching source files.",
        },
        "phases": [
            {
                "name": "Adoption",
                "status": "active",
                "run_range": "1-2",
                "target_runs": 2,
                "description": "Convert existing AI-native project context into validated FRAME.",
                "done_when": "FRAME validates and native files can be regenerated from it.",
            }
        ],
        "runbook": [
            {
                "run": 1,
                "phase": "Adoption",
                "status": "active",
                "goal": "Derive real project facts and rules from discovered evidence.",
                "outcome": ".haxaml/facts.yaml and .haxaml/rules.yaml no longer contain blocking unknowns.",
                "depends_on": [],
                "touches": ["facts", "rules"],
                "requires": _source_paths(plan) or ["Repository context"],
                "uses_map": uses_map,
                "verify": ["haxaml validate --dir .", "haxaml doctor --dir ."],
                "done_when": "Project facts and agent rules are explicit and evidence-backed.",
                "risks": ["Conflicting native instructions may require user decisions."],
            },
            {
                "run": 2,
                "phase": "Adoption",
                "status": "planned",
                "goal": "Validate FRAME and export native agent files.",
                "outcome": "Native agent files are generated from FRAME as the source of truth.",
                "depends_on": [1],
                "touches": ["acts", "expect", "exports"],
                "requires": ["Completed run 1", "Validated FRAME files"],
                "uses_map": uses_map,
                "verify": ["haxaml validate --dir .", "haxaml export"],
                "done_when": "FRAME validates and generated native files match supported agent conventions.",
                "risks": ["Generated files may replace hand-written instructions if the user chooses to export over them."],
            },
        ],
        "upcoming": [
            {
                "task": "Replace adoption scaffold unknowns with project-specific truth",
                "priority": "critical",
                "phase": "Adoption",
                "description": "AI agent derives actual project facts from the discovered files and source tree.",
            }
        ],
        "milestones": [
            {
                "name": "Existing project adopted into FRAME",
                "status": "pending",
                "criteria": "haxaml validate passes and native agent files are exportable from FRAME.",
            }
        ],
        "open_questions": [
            {
                "question": "Which native file should be treated as authoritative if existing instructions conflict?",
                "blocking": True,
                "phase": "Adoption",
            }
        ],
    }


def _write_yaml(path: Path, data: dict) -> None:
    path.write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=False),
        encoding="utf-8",
    )
