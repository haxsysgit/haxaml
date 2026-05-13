"""Context builder — task-scoped context for AI agent consumption."""

from __future__ import annotations

from typing import Any

import yaml

from haxaml.context_memory import DEFAULT_CONTEXT_FETCH_SOURCES, search_context_memory
from haxaml.runtime_cache import runtime_cache, stable_fingerprint
from haxaml.utils import clean_str_list, normalized_text


CONTEXT_SECTION_ORDER = [
    "essential_facts",
    "relevant_rules",
    "recent_decisions",
    "affected_modules",
    "expectations",
    "unresolved",
    "task_risks",
    "retrieval_hints",
]


def load_frame_data(project_dir: str) -> dict[str, Any]:
    """Load available FRAME files into a dict."""
    return runtime_cache().get_frame_bundle(project_dir)["data"]


def build_context(project_dir: str, include_state: bool = True) -> str:
    """Build compact whole-project context from canonical FRAME files."""
    parts = []
    frame = load_frame_data(project_dir)

    facts = frame.get("facts")
    if isinstance(facts, dict):
        parts.append(_format_facts_context(facts))
    else:
        parts.append("⚠ facts.yaml not found — project facts are missing.")

    rules = frame.get("rules")
    if isinstance(rules, dict):
        parts.append(_format_rules_context(rules))

    if include_state:
        acts = frame.get("acts")
        if isinstance(acts, dict):
            parts.append(_format_acts_context(acts))

    expect = frame.get("expect")
    if isinstance(expect, dict):
        parts.append(_format_expect_context(expect))

    return "\n\n---\n\n".join(parts)


def build_context_pack(
    project_dir: str,
    task: str,
    pack: str = "balanced",
    include_state: bool = True,
    frame_data: dict[str, Any] | None = None,
    sections_override: dict[str, Any] | None = None,
    refresh_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a deterministic task-specific context pack.

    Packs include:
    - essential facts
    - relevant rules
    - recent decisions
    - affected modules
    - current expectations
    - unresolved questions/dependencies
    - task risks
    """
    frame = frame_data if isinstance(frame_data, dict) else load_frame_data(project_dir)
    sections, build_meta = build_context_pack_sections(
        project_dir,
        task=task,
        pack=pack,
        include_state=include_state,
        frame_data=frame,
        sections_override=sections_override,
    )

    pack_data: dict[str, Any] = {
        "task": task,
        "pack": build_meta["resolved_pack"],
        **sections,
    }
    pack_text = format_context_pack(pack_data)
    token_count = count_tokens(pack_text)
    refresh = refresh_meta or {}
    pack_data["_meta"] = {
        "token_count": token_count,
        "context_window_usage": _token_window_usage(token_count),
        "compaction_notes": build_meta["notes"],
        "included_sections": build_meta["included_sections"],
        "omitted_sections": build_meta["omitted_sections"],
        "omitted_context": build_meta["omitted_context"],
        "limits": build_meta["limits"],
        "state_included": include_state,
        "requested_pack": pack,
        "resolved_pack": build_meta["resolved_pack"],
        "likely_relevant_sources": build_meta["retrieval_hints"].get("likely_relevant_sources", []),
        "candidate_file_refs": build_meta["retrieval_hints"].get("candidate_file_refs", []),
        "archive_available": build_meta["retrieval_hints"].get("archive_available", False),
        "refresh_mode": refresh.get("refresh_mode", "full"),
        "refresh_summary": refresh.get("refresh_summary", "Initial full context pack."),
        "changed_sections": refresh.get("changed_sections", list(build_meta["included_sections"])),
        "unchanged_sections": refresh.get("unchanged_sections", []),
        "token_delta": int(refresh.get("token_delta", token_count) or 0),
    }
    return pack_data


def format_context_pack(pack_data: dict[str, Any]) -> str:
    """Render a context pack to compact markdown text."""
    meta = pack_data.get("_meta", {}) if isinstance(pack_data.get("_meta"), dict) else {}
    refresh_mode = str(meta.get("refresh_mode", "full"))
    lines: list[str] = ["## Context Pack Refresh" if refresh_mode != "full" else "## Context Pack"]
    lines.append(f"Task: {pack_data.get('task', '')}")
    lines.append(f"Pack: {pack_data.get('pack', 'balanced')}")
    if refresh_mode != "full":
        lines.append(f"Refresh mode: {refresh_mode}")
        if meta.get("refresh_summary"):
            lines.append(f"Refresh summary: {meta['refresh_summary']}")
        changed_sections = meta.get("changed_sections", [])
        unchanged_sections = meta.get("unchanged_sections", [])
        if changed_sections:
            lines.append(f"Changed sections: {', '.join(changed_sections)}")
        if unchanged_sections:
            lines.append(f"Unchanged sections: {', '.join(unchanged_sections)}")
        lines.append(f"Token delta: {int(meta.get('token_delta', 0) or 0)}")

    for section_name in CONTEXT_SECTION_ORDER:
        section_lines = _render_context_section(section_name, pack_data.get(section_name))
        if section_lines:
            lines.append("")
            lines.extend(section_lines)

    notes = meta.get("compaction_notes", [])
    if notes:
        lines.append("\n### Compaction")
        for note in notes:
            lines.append(f"- {note}")

    return "\n".join(lines)


def build_context_pack_sections(
    project_dir: str,
    *,
    task: str,
    pack: str,
    include_state: bool,
    frame_data: dict[str, Any] | None = None,
    sections_override: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    frame = frame_data if isinstance(frame_data, dict) else load_frame_data(project_dir)
    facts = frame.get("facts") or {}
    rules = frame.get("rules") or {}
    acts = frame.get("acts") or {}
    expect = frame.get("expect") or {}
    map_data = frame.get("map") or {}

    policy = _context_policy(rules)
    default_pack = _resolve_pack_name(str(policy.get("default_pack", "balanced")))
    resolved_pack = _resolve_pack_name(pack, default_pack)
    limits = _pack_limits(pack, policy)
    overrides = sections_override or {}
    notes: list[str] = []
    sections: dict[str, Any] = {}
    section_markers = context_pack_section_markers(
        project_dir,
        task=task,
        pack=resolved_pack,
        include_state=include_state,
        frame_data=frame,
    )

    if "essential_facts" in overrides:
        sections["essential_facts"] = overrides["essential_facts"]
    else:
        sections["essential_facts"] = {
            "project": _clean_str((facts.get("identity") or {}).get("name", "unknown"), "unknown"),
            "purpose": _clean_str((facts.get("goal") or {}).get("purpose", "")),
            "scope": _clean_str((facts.get("goal") or {}).get("scope", "")),
            "stack": facts.get("stack", {}),
            "architecture": {
                "pattern": _clean_str((facts.get("architecture") or {}).get("pattern", "")),
                "boundaries": (facts.get("architecture") or {}).get("boundaries", []),
            },
            "database": _clean_str((facts.get("database") or {}).get("type", "")),
        }

    if "relevant_rules" in overrides:
        sections["relevant_rules"] = overrides["relevant_rules"]
    else:
        relevant_rules = {
            "read_first": _clean_str_list(((rules.get("before_task") or {}).get("read_first", []) or [])),
            "checks": _clean_str_list(((rules.get("before_task") or {}).get("check", []) or [])),
            "boundaries": _clean_str_list(((rules.get("boundaries") or {}).get("rules", []) or [])),
            "forbidden": _clean_str_list((rules.get("forbidden", []) or [])),
            "after_verify": _clean_str_list(((rules.get("after_task") or {}).get("verify", []) or [])),
        }
        for key, note_key in (
            ("checks", "rules.checks"),
            ("boundaries", "rules.boundaries"),
            ("forbidden", "rules.forbidden"),
        ):
            relevant_rules[key], note = _limit_list(relevant_rules[key], limits["max_items"], limits["max_chars"])
            if note:
                notes.append(f"{note_key}: {note}")
        sections["relevant_rules"] = relevant_rules

    if "recent_decisions" in overrides:
        sections["recent_decisions"] = overrides["recent_decisions"]
    else:
        recent_decisions = _normalize_decisions(acts.get("decisions", [])) if include_state else []
        recent_decisions, note = _limit_list(recent_decisions, limits["max_items"], limits["max_chars"])
        if note:
            notes.append(f"recent_decisions: {note}")
        sections["recent_decisions"] = recent_decisions

    if "affected_modules" in overrides:
        affected_modules = overrides["affected_modules"]
    else:
        affected_modules = _detect_affected_modules(task, facts, rules, map_data)
        affected_modules, note = _limit_list(affected_modules, limits["max_items"], limits["max_chars"])
        if note:
            notes.append(f"affected_modules: {note}")
    sections["affected_modules"] = affected_modules

    if "expectations" in overrides:
        sections["expectations"] = overrides["expectations"]
    else:
        sections["expectations"] = {
            "goal": ((expect.get("planning") or {}).get("goal", "")),
            "active_phase": _active_phase(expect),
            "active_runs": _active_runs(expect.get("runbook", [])),
        }

    if "unresolved" in overrides:
        unresolved = overrides["unresolved"]
    else:
        unresolved = {
            "facts": _normalize_unresolved_facts(facts.get("unresolved", [])),
            "acts": _normalize_unresolved_acts(acts.get("unresolved_dependencies", [])) if include_state else [],
            "expect": _normalize_open_questions(expect.get("open_questions", [])),
        }
        for key in ("facts", "acts", "expect"):
            unresolved[key], note = _limit_list(unresolved[key], limits["max_items"], limits["max_chars"])
            if note:
                notes.append(f"unresolved.{key}: {note}")
    sections["unresolved"] = unresolved

    if "task_risks" in overrides:
        sections["task_risks"] = overrides["task_risks"]
    else:
        sections["task_risks"] = _task_risks(task, rules, sections["affected_modules"])

    if "retrieval_hints" in overrides:
        retrieval_hints = overrides["retrieval_hints"]
    else:
        retrieval_hints = build_context_hints(project_dir, task=task, frame_data=frame)
    sections["retrieval_hints"] = retrieval_hints

    included_sections = [name for name in CONTEXT_SECTION_ORDER if _has_section_data(sections.get(name))]
    omitted_sections = [name for name in CONTEXT_SECTION_ORDER if name not in included_sections]
    omitted_context = list(notes)
    if not include_state:
        omitted_context.append("recent_decisions: omitted (include_state=False)")
    if omitted_sections:
        omitted_context.append(f"empty sections omitted: {', '.join(omitted_sections)}")

    section_tokens = {
        name: count_tokens("\n".join(_render_context_section(name, sections.get(name))))
        for name in included_sections
    }
    return sections, {
        "resolved_pack": resolved_pack,
        "limits": limits,
        "notes": notes,
        "included_sections": included_sections,
        "omitted_sections": omitted_sections,
        "omitted_context": omitted_context,
        "retrieval_hints": retrieval_hints,
        "section_markers": section_markers,
        "section_tokens": section_tokens,
    }


def context_pack_section_markers(
    project_dir: str,
    *,
    task: str,
    pack: str,
    include_state: bool,
    frame_data: dict[str, Any] | None = None,
) -> dict[str, str]:
    """Generate SHA-1 fingerprints for each context section.

    Haxaml uses these markers to detect 'drift' between context packs. By
    fingerprinting each top-level section of the FRAME files, we can determine
    exactly which parts of the agent's context have changed since the last
    `haxaml_context_pack` call. This enables efficient incremental refreshes
    (returning only deltas) to minimize token usage.
    """
    bundle = runtime_cache().get_frame_bundle(project_dir)
    files = bundle["files"]
    archive_index = bundle["archive_index"]
    frame = frame_data if isinstance(frame_data, dict) else bundle["data"]

    def file_fp(name: str, *section: str) -> str:
        snapshot = files.get(name)
        if snapshot is None:
            return stable_fingerprint(None)
        return snapshot.section_fingerprint(*section)

    affected_input = {
        "task": task,
        "pack": pack,
        "include_state": include_state,
        "facts": file_fp("facts"),
        "rules": file_fp("rules"),
        "map": file_fp("map"),
    }
    affected_modules = _detect_affected_modules(task, frame.get("facts") or {}, frame.get("rules") or {}, frame.get("map") or {})
    return {
        "essential_facts": stable_fingerprint({"pack": pack, "facts": file_fp("facts")}),
        "relevant_rules": stable_fingerprint({"pack": pack, "rules": file_fp("rules")}),
        "recent_decisions": stable_fingerprint(
            {"pack": pack, "include_state": include_state, "acts.decisions": file_fp("acts", "decisions")}
        ),
        "expectations": stable_fingerprint({"pack": pack, "expect": file_fp("expect")}),
        "unresolved": stable_fingerprint(
            {
                "pack": pack,
                "include_state": include_state,
                "facts.unresolved": file_fp("facts", "unresolved"),
                "acts.unresolved_dependencies": file_fp("acts", "unresolved_dependencies"),
                "expect.open_questions": file_fp("expect", "open_questions"),
            }
        ),
        "affected_modules": stable_fingerprint(affected_input),
        "task_risks": stable_fingerprint(
            {
                "task": task,
                "pack": pack,
                "rules": file_fp("rules"),
                "affected_modules": affected_modules,
            }
        ),
        "retrieval_hints": stable_fingerprint(
            {
                "task": task,
                "pack": pack,
                "include_state": include_state,
                "sources": ["facts", "rules", "acts", "archived_acts", "expect", "map"],
                "archive_available": archive_index.exists,
                "archive_signature": archive_index.signature,
            }
        ),
    }


def _render_context_section(section_name: str, value: Any) -> list[str]:
    if section_name == "essential_facts":
        facts = value if isinstance(value, dict) else {}
        lines = ["### Essential Facts", f"Project: {facts.get('project', 'unknown')}", f"Purpose: {facts.get('purpose', '')}"]
        if facts.get("scope"):
            lines.append(f"Scope: {facts.get('scope')}")
        stack = facts.get("stack", {})
        if isinstance(stack, dict) and stack:
            stack_text = ", ".join(f"{k}: {v}" for k, v in stack.items() if v)
            if stack_text:
                lines.append(f"Stack: {stack_text}")
        return lines
    if section_name == "relevant_rules":
        rules = value if isinstance(value, dict) else {}
        lines = ["### Relevant Rules"]
        for label, values in (
            ("Read first", rules.get("read_first", [])),
            ("Checks", rules.get("checks", [])),
            ("Boundary", rules.get("boundaries", [])),
            ("Forbidden", rules.get("forbidden", [])),
            ("After verify", rules.get("after_verify", [])),
        ):
            if values:
                lines.append(f"{label}:")
                for item in values:
                    lines.append(f"- {item}")
        return lines if len(lines) > 1 else []
    if section_name == "recent_decisions":
        if not value:
            return []
        return ["### Recent Decisions", *[f"- {item}" for item in value]]
    if section_name == "affected_modules":
        if not value:
            return []
        return ["### Affected Modules", *[f"- {item}" for item in value]]
    if section_name == "expectations":
        expect = value if isinstance(value, dict) else {}
        lines = ["### Expectations"]
        if expect.get("goal"):
            lines.append(f"Goal: {expect['goal']}")
        if expect.get("active_phase"):
            lines.append(f"Active phase: {expect['active_phase']}")
        for run in expect.get("active_runs", []):
            lines.append(f"- Run {run.get('run', '?')} [{run.get('status', '?')}]: {run.get('goal', '')}")
        return lines if len(lines) > 1 else []
    if section_name == "unresolved":
        unresolved = value if isinstance(value, dict) else {}
        if not any(unresolved.values()):
            return []
        lines = ["### Unresolved"]
        for label, items in (("Facts", unresolved.get("facts", [])), ("Acts", unresolved.get("acts", [])), ("Expect", unresolved.get("expect", []))):
            if items:
                lines.append(f"{label}:")
                for item in items:
                    lines.append(f"- {item}")
        return lines
    if section_name == "task_risks":
        if not value:
            return []
        return ["### Task Risks", *[f"- {item}" for item in value]]
    if section_name == "retrieval_hints":
        hints = value if isinstance(value, dict) else {}
        sources = hints.get("likely_relevant_sources", [])
        file_refs = hints.get("candidate_file_refs", [])
        archive_available = bool(hints.get("archive_available"))
        if not (sources or file_refs or archive_available):
            return []
        lines = ["### Retrieval Hints"]
        if sources:
            lines.append(f"Likely sources: {', '.join(sources)}")
        if file_refs:
            lines.extend(f"- {item}" for item in file_refs[:6])
        if archive_available:
            lines.append("Archive history exists and may contain relevant prior context.")
        return lines
    return []


def _context_policy(rules: dict[str, Any]) -> dict[str, Any]:
    policy = (rules.get("context_policy") or {}) if isinstance(rules, dict) else {}
    if not isinstance(policy, dict):
        return {}
    return policy


def _resolve_pack_name(pack: str, default: str = "balanced") -> str:
    """Normalize pack names and fallback to a safe default."""
    normalized = str(pack or "").strip().lower()
    if normalized in {"minimal", "balanced", "full"}:
        return normalized
    fallback = str(default or "balanced").strip().lower()
    return fallback if fallback in {"minimal", "balanced", "full"} else "balanced"


def _pack_limits(pack: str, policy: dict[str, Any]) -> dict[str, int]:
    default_pack = _resolve_pack_name(str(policy.get("default_pack", "balanced")))
    resolved = _resolve_pack_name(pack, default_pack)
    max_items = policy.get("max_items_per_section", 5)
    max_chars = policy.get("max_chars_per_item", 240)

    if not isinstance(max_items, int) or max_items < 1:
        max_items = 5
    if not isinstance(max_chars, int) or max_chars < 40:
        max_chars = 240

    # "minimal" is allowed to further shrink policy defaults, while "full"
    # can only widen them within deterministic hard caps.
    if resolved == "minimal":
        return {"max_items": min(max_items, 3), "max_chars": min(max_chars, 180)}
    if resolved == "full":
        return {"max_items": max(max_items, 8), "max_chars": max(max_chars, 420)}
    return {"max_items": max_items, "max_chars": max_chars}


def _normalize_decisions(items: list[Any]) -> list[str]:
    out: list[str] = []
    for item in items[-8:]:
        if isinstance(item, dict):
            decision = str(item.get("decision", "")).strip()
            reasoning = str(item.get("reasoning", "")).strip()
            if decision and reasoning:
                out.append(f"{decision} — {reasoning}")
            elif decision:
                out.append(decision)
        elif isinstance(item, str) and item.strip():
            out.append(item.strip())
    return out


def _clean_str(value: Any, default: str = "") -> str:
    return normalized_text(value) or default


def _clean_str_list(items: list[Any]) -> list[str]:
    return clean_str_list(items if isinstance(items, list) else [])


def _detect_affected_modules(task: str, facts: dict[str, Any], rules: dict[str, Any], map_data: dict[str, Any]) -> list[str]:
    task_l = task.lower()
    candidates: list[str] = []

    boundaries = (facts.get("architecture") or {}).get("boundaries", [])
    if isinstance(boundaries, list):
        for item in boundaries:
            if isinstance(item, str) and item.strip():
                candidates.append(item.strip())

    rule_modules = (rules.get("boundaries") or {}).get("modules", {})
    if isinstance(rule_modules, dict):
        candidates.extend(str(k).strip() for k in rule_modules.keys() if str(k).strip())

    map_modules = map_data.get("modules", [])
    if isinstance(map_modules, list):
        for mod in map_modules:
            if isinstance(mod, dict) and str(mod.get("name", "")).strip():
                candidates.append(str(mod.get("name")).strip())

    seen = set()
    unique = []
    for name in candidates:
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(name)

    # This remains a lightweight heuristic: prefer explicit task-name matches,
    # otherwise fall back to a small stable list so packs stay predictable.
    matched = [name for name in unique if name.lower() in task_l]
    return matched if matched else unique[:5]


def _active_phase(expect: dict[str, Any]) -> str:
    phases = expect.get("phases", []) if isinstance(expect, dict) else []
    if not isinstance(phases, list):
        return ""
    for phase in phases:
        if isinstance(phase, dict) and phase.get("status") == "active":
            return str(phase.get("name", ""))
    return ""


def _active_runs(runbook: list[Any]) -> list[dict[str, Any]]:
    if not isinstance(runbook, list):
        return []
    out = []
    for run in runbook:
        if not isinstance(run, dict):
            continue
        if run.get("status") in ("active", "planned", "blocked"):
            out.append({
                "run": run.get("run"),
                "status": run.get("status"),
                "goal": run.get("goal", ""),
            })
    return out[:4]


def _normalize_unresolved_facts(items: list[Any]) -> list[str]:
    out = []
    for item in items:
        if isinstance(item, dict):
            label = str(item.get("item", "")).strip()
            reason = str(item.get("reason", "")).strip()
            if label:
                out.append(f"{label}: {reason}".strip(": "))
    return out


def _normalize_unresolved_acts(items: list[Any]) -> list[str]:
    out = []
    for item in items:
        if isinstance(item, dict):
            label = str(item.get("item", "")).strip()
            owner = str(item.get("owner", "")).strip()
            if label:
                suffix = f" (owner: {owner})" if owner else ""
                out.append(f"{label}{suffix}")
    return out


def _normalize_open_questions(items: list[Any]) -> list[str]:
    out = []
    for item in items:
        if isinstance(item, dict):
            question = str(item.get("question", "")).strip()
            if question:
                out.append(question)
    return out


def _task_risks(task: str, rules: dict[str, Any], affected_modules: list[str]) -> list[str]:
    risks = []
    task_l = task.lower()

    high_risk_words = [
        "delete", "drop", "migrate", "auth", "security", "payment", "billing", "database", "schema", "prod"
    ]
    if any(word in task_l for word in high_risk_words):
        risks.append("Task includes high-impact domain keywords.")

    if len(affected_modules) >= 3:
        risks.append("Task appears to touch multiple modules; check cross-impact.")

    forbidden_raw = rules.get("forbidden", []) if isinstance(rules, dict) else []
    forbidden = _clean_str_list(forbidden_raw) if isinstance(forbidden_raw, list) else []
    if forbidden:
        risks.append("Review forbidden rules before acting.")

    return risks


def _limit_list(items: list[Any], max_items: int, max_chars: int) -> tuple[list[Any], str]:
    trimmed = []
    truncated_items = 0

    for idx, item in enumerate(items):
        # Packs should stay deterministic: once the item budget is spent we stop,
        # rather than trying to rebalance across later sections.
        if idx >= max_items:
            break
        if isinstance(item, str):
            if len(item) > max_chars:
                trimmed.append(item[: max_chars - 1].rstrip() + "…")
                truncated_items += 1
            else:
                trimmed.append(item)
        else:
            trimmed.append(item)

    omitted = max(0, len(items) - len(trimmed))
    notes = []
    if omitted:
        notes.append(f"omitted {omitted} item(s)")
    if truncated_items:
        notes.append(f"truncated {truncated_items} item(s)")

    return trimmed, "; ".join(notes)


def _has_section_data(value: Any) -> bool:
    if isinstance(value, dict):
        return any(_has_section_data(v) for v in value.values())
    if isinstance(value, list):
        return any(_has_section_data(v) for v in value)
    if isinstance(value, str):
        return bool(value.strip())
    return bool(value)


def _token_window_usage(tokens: int) -> dict[str, float]:
    budgets = [4000, 8000, 32000, 128000]
    return {f"pct_{size}": round((tokens / size) * 100, 2) for size in budgets}


def build_context_hints(
    project_dir: str,
    *,
    task: str,
    frame_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return lightweight hints for guided follow-up retrieval."""
    frame = frame_data if isinstance(frame_data, dict) else load_frame_data(project_dir)
    hits = search_context_memory(
        project_dir,
        task=task,
        query=task,
        sources=[source for source in DEFAULT_CONTEXT_FETCH_SOURCES if source != "file_refs"],
        limit=4,
        frame_data=frame,
    )
    likely_sources: list[str] = []
    candidate_file_refs: list[str] = []
    for hit in hits["hits"]:
        source = str(hit.get("source", "")).strip()
        if source and source not in likely_sources:
            likely_sources.append(source)
        for ref in hit.get("file_refs", []):
            if ref not in candidate_file_refs:
                candidate_file_refs.append(ref)
    return {
        "likely_relevant_sources": likely_sources,
        "candidate_file_refs": candidate_file_refs[:8],
        "archive_available": bool(hits.get("archive_available")),
    }


def _format_facts_context(facts: dict) -> str:
    """Format facts into a compact context block."""
    lines = ["## Project Facts"]

    identity = facts.get("identity", {})
    lines.append(f"**Project:** {identity.get('name', 'unknown')}")
    lines.append(f"**Version:** {identity.get('version', 'unknown')}")
    if identity.get("description"):
        lines.append(f"**Description:** {identity['description']}")

    goal = facts.get("goal", {})
    lines.append(f"\n**Purpose:** {goal.get('purpose', 'not defined')}")
    if goal.get("scope"):
        lines.append(f"**Scope:** {goal['scope']}")

    stack = facts.get("stack", {})
    stack_items = [f"{k}: {v}" for k, v in stack.items()]
    lines.append(f"\n**Stack:** {', '.join(stack_items)}")

    arch = facts.get("architecture", {})
    lines.append(f"**Architecture:** {arch.get('pattern', 'not defined')} — {arch.get('reasoning', '')}")

    db = facts.get("database", {})
    lines.append(f"**Database:** {db.get('type', 'not defined')} ({db.get('connection', 'no connection')})")

    constraints = facts.get("constraints", [])
    if constraints:
        lines.append("\n**Constraints:**")
        for c in constraints:
            lines.append(f"- {c}")

    criteria = facts.get("success_criteria", [])
    if criteria:
        lines.append("\n**Success Criteria:**")
        for c in criteria:
            lines.append(f"- {c}")

    return "\n".join(lines)


def _format_rules_context(rules_data: dict) -> str:
    """Format rules.yaml into a compact conventions block."""
    lines = ["## Agent Rules"]

    before = rules_data.get("before_task", {})
    read_first = before.get("read_first", [])
    if read_first:
        lines.append(f"**Read first:** {', '.join(read_first)}")

    checks = before.get("check", [])
    if checks:
        lines.append("\n**Pre-task checks:**")
        for c in checks:
            lines.append(f"- {c}")

    boundaries = rules_data.get("boundaries", {})
    rules = boundaries.get("rules", [])
    if rules:
        lines.append("\n**Boundary rules:**")
        for r in rules:
            lines.append(f"- {r}")

    forbidden = rules_data.get("forbidden", [])
    if forbidden:
        lines.append("\n**Forbidden:**")
        for f in forbidden:
            lines.append(f"- {f}")

    after = rules_data.get("after_task", {})
    update = after.get("update", [])
    if update:
        lines.append("\n**After task — update:**")
        for u in update:
            lines.append(f"- {u}")

    return "\n".join(lines)


def _format_acts_context(state: dict) -> str:
    """Format acts into a compact context block."""
    lines = ["## Current Acts"]
    lines.append(f"**Phase:** {state.get('current_phase', 'unknown')}")

    task = state.get("active_task", {})
    if task:
        lines.append(f"**Active Task:** {task.get('name', 'none')}")
        if task.get("description"):
            lines.append(f"  {task['description']}")

    blocked = state.get("blocked_tasks", [])
    if blocked:
        lines.append("\n**Blocked:**")
        for b in blocked:
            lines.append(f"- {b['name']}: {b.get('reason', 'unknown')}")

    unresolved = state.get("unresolved_dependencies", [])
    if unresolved:
        lines.append("\n**Unresolved:**")
        for u in unresolved:
            lines.append(f"- {u['item']}")

    return "\n".join(lines)


def _format_expect_context(expect: dict) -> str:
    """Format expect.yaml into a compact plan block."""
    lines = ["## What's Expected Next"]

    planning = expect.get("planning", {})
    if planning:
        if planning.get("goal"):
            lines.append(f"**Goal:** {planning['goal']}")
        if planning.get("estimated_runs"):
            size = planning.get("project_size", "unknown")
            lines.append(f"**Expected size:** {planning['estimated_runs']} runs ({size})")
        if "map_required" in planning:
            map_state = "required" if planning.get("map_required") else "not required yet"
            reason = planning.get("map_reason", "")
            lines.append(f"**Map:** {map_state}" + (f" — {reason}" if reason else ""))

    phases = expect.get("phases", [])
    active = [p for p in phases if p.get("status") == "active"]
    if active:
        lines.append(f"**Active phase:** {active[0]['name']}")
        if active[0].get("done_when"):
            lines.append(f"  Done when: {active[0]['done_when']}")

    upcoming = expect.get("upcoming", [])
    if upcoming:
        lines.append("\n**Upcoming tasks:**")
        for t in upcoming[:5]:
            lines.append(f"- [{t.get('priority', '?')}] {t['task']}")

    runbook = expect.get("runbook", [])
    next_runs = [r for r in runbook if r.get("status") in ("active", "planned", "blocked")]
    if next_runs:
        lines.append("\n**Expected runs:**")
        for r in next_runs[:3]:
            run = r.get("run", "?")
            status = r.get("status", "?")
            lines.append(f"- Run {run} [{status}]: {r.get('goal', 'no goal')}")
            if r.get("outcome"):
                lines.append(f"  Outcome: {r['outcome']}")
            if r.get("requires"):
                lines.append(f"  Requires: {', '.join(r['requires'])}")
            if r.get("uses_map"):
                lines.append("  Uses map.yaml: yes")

    map_policy = expect.get("map_policy", {})
    if map_policy and map_policy.get("agent_instruction"):
        lines.append(f"\n**Map policy:** {map_policy['agent_instruction']}")

    questions = expect.get("open_questions", [])
    blocking_q = [q for q in questions if q.get("blocking")]
    if blocking_q:
        lines.append("\n**Blocking questions:**")
        for q in blocking_q:
            lines.append(f"- {q['question']}")

    return "\n".join(lines)


def count_tokens(text: str, model: str = "cl100k_base") -> int:
    """Count tokens in a string using tiktoken."""
    try:
        import tiktoken

        enc = tiktoken.get_encoding(model)
        return len(enc.encode(text))
    except ImportError:
        return len(text.split())
