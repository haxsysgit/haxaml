"""Context builder — task-scoped context for AI agent consumption."""

from __future__ import annotations

from typing import Any

import yaml

from haxaml.acts_archive import ActsArchive
from haxaml.frame_model import FrameModel
from haxaml.paths import resolve_frame_file


def load_frame_data(project_dir: str) -> dict[str, Any]:
    """Load available FRAME files into a dict."""
    frame = FrameModel.load(project_dir)
    return {
        "facts": frame.facts,
        "rules": frame.rules,
        "acts": frame.acts,
        "expect": frame.expect,
        "map": frame.map,
    }


def build_context(project_dir: str, include_state: bool = True) -> str:
    """Build compact whole-project context from canonical FRAME files."""
    parts = []

    facts_path = resolve_frame_file(project_dir, "facts.yaml")
    if facts_path:
        with open(facts_path, encoding="utf-8") as f:
            facts = yaml.safe_load(f)
        parts.append(_format_facts_context(facts))
    else:
        parts.append("⚠ facts.yaml not found — project facts are missing.")

    rules_path = resolve_frame_file(project_dir, "rules.yaml")
    if rules_path:
        with open(rules_path, encoding="utf-8") as f:
            rules = yaml.safe_load(f)
        parts.append(_format_rules_context(rules))

    if include_state:
        acts_path = resolve_frame_file(project_dir, "acts.yaml")
        if acts_path:
            with open(acts_path, encoding="utf-8") as f:
                acts = yaml.safe_load(f)
            parts.append(_format_acts_context(acts))

    expect_path = resolve_frame_file(project_dir, "expect.yaml")
    if expect_path:
        with open(expect_path, encoding="utf-8") as f:
            expect = yaml.safe_load(f)
        parts.append(_format_expect_context(expect))

    return "\n\n---\n\n".join(parts)


def build_context_pack(
    project_dir: str,
    task: str,
    pack: str = "balanced",
    include_state: bool = True,
    frame_data: dict[str, Any] | None = None,
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
    facts = frame.get("facts") or {}
    rules = frame.get("rules") or {}
    acts = frame.get("acts") or {}
    expect = frame.get("expect") or {}
    map_data = frame.get("map") or {}

    policy = _context_policy(rules)
    default_pack = _resolve_pack_name(str(policy.get("default_pack", "balanced")))
    resolved_pack = _resolve_pack_name(pack, default_pack)
    limits = _pack_limits(pack, policy)

    essential_facts = {
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

    relevant_rules = {
        "read_first": _clean_str_list(((rules.get("before_task") or {}).get("read_first", []) or [])),
        "checks": _clean_str_list(((rules.get("before_task") or {}).get("check", []) or [])),
        "boundaries": _clean_str_list(((rules.get("boundaries") or {}).get("rules", []) or [])),
        "forbidden": _clean_str_list((rules.get("forbidden", []) or [])),
        "after_verify": _clean_str_list(((rules.get("after_task") or {}).get("verify", []) or [])),
    }

    recent_decisions = _normalize_decisions(acts.get("decisions", []))
    affected_modules = _detect_affected_modules(task, facts, rules, map_data)

    expectations = {
        "goal": ((expect.get("planning") or {}).get("goal", "")),
        "active_phase": _active_phase(expect),
        "active_runs": _active_runs(expect.get("runbook", [])),
    }

    unresolved = {
        "facts": _normalize_unresolved_facts(facts.get("unresolved", [])),
        "acts": _normalize_unresolved_acts(acts.get("unresolved_dependencies", [])),
        "expect": _normalize_open_questions(expect.get("open_questions", [])),
    }

    task_risks = _task_risks(task, rules, affected_modules)

    # Deterministic compaction
    notes: list[str] = []
    recent_decisions, note = _limit_list(recent_decisions, limits["max_items"], limits["max_chars"])
    if note:
        notes.append(f"recent_decisions: {note}")

    relevant_rules["checks"], note = _limit_list(relevant_rules["checks"], limits["max_items"], limits["max_chars"])
    if note:
        notes.append(f"rules.checks: {note}")

    relevant_rules["boundaries"], note = _limit_list(relevant_rules["boundaries"], limits["max_items"], limits["max_chars"])
    if note:
        notes.append(f"rules.boundaries: {note}")

    relevant_rules["forbidden"], note = _limit_list(relevant_rules["forbidden"], limits["max_items"], limits["max_chars"])
    if note:
        notes.append(f"rules.forbidden: {note}")

    affected_modules, note = _limit_list(affected_modules, limits["max_items"], limits["max_chars"])
    if note:
        notes.append(f"affected_modules: {note}")

    unresolved["facts"], note = _limit_list(unresolved["facts"], limits["max_items"], limits["max_chars"])
    if note:
        notes.append(f"unresolved.facts: {note}")

    unresolved["acts"], note = _limit_list(unresolved["acts"], limits["max_items"], limits["max_chars"])
    if note:
        notes.append(f"unresolved.acts: {note}")

    unresolved["expect"], note = _limit_list(unresolved["expect"], limits["max_items"], limits["max_chars"])
    if note:
        notes.append(f"unresolved.expect: {note}")

    pack_data: dict[str, Any] = {
        "task": task,
        "pack": resolved_pack,
        "essential_facts": essential_facts,
        "relevant_rules": relevant_rules,
        "recent_decisions": recent_decisions if include_state else [],
        "affected_modules": affected_modules,
        "expectations": expectations,
        "unresolved": unresolved,
        "task_risks": task_risks,
    }
    retrieval_hints = build_context_hints(project_dir, task=task, frame_data=frame)
    pack_data["retrieval_hints"] = retrieval_hints

    pack_text = format_context_pack(pack_data)
    section_order = [
        "essential_facts",
        "relevant_rules",
        "recent_decisions",
        "affected_modules",
        "expectations",
        "unresolved",
        "task_risks",
    ]
    included_sections = [name for name in section_order if _has_section_data(pack_data.get(name))]
    omitted_sections = [name for name in section_order if name not in included_sections]
    omitted_context = list(notes)
    if not include_state:
        omitted_context.append("recent_decisions: omitted (include_state=False)")
    if omitted_sections:
        omitted_context.append(f"empty sections omitted: {', '.join(omitted_sections)}")

    token_count = count_tokens(pack_text)
    pack_data["_meta"] = {
        "token_count": token_count,
        "context_window_usage": _token_window_usage(token_count),
        "compaction_notes": notes,
        "included_sections": included_sections,
        "omitted_sections": omitted_sections,
        "omitted_context": omitted_context,
        "limits": limits,
        "state_included": include_state,
        "requested_pack": pack,
        "resolved_pack": resolved_pack,
        "likely_relevant_sources": retrieval_hints.get("likely_relevant_sources", []),
        "candidate_file_refs": retrieval_hints.get("candidate_file_refs", []),
        "archive_available": retrieval_hints.get("archive_available", False),
    }

    return pack_data


def format_context_pack(pack_data: dict[str, Any]) -> str:
    """Render a context pack to compact markdown text."""
    lines: list[str] = ["## Context Pack"]
    lines.append(f"Task: {pack_data.get('task', '')}")
    lines.append(f"Pack: {pack_data.get('pack', 'balanced')}")

    facts = pack_data.get("essential_facts", {})
    lines.append("\n### Essential Facts")
    lines.append(f"Project: {facts.get('project', 'unknown')}")
    lines.append(f"Purpose: {facts.get('purpose', '')}")
    if facts.get("scope"):
        lines.append(f"Scope: {facts.get('scope')}")

    stack = facts.get("stack", {})
    if isinstance(stack, dict) and stack:
        stack_text = ", ".join(f"{k}: {v}" for k, v in stack.items() if v)
        if stack_text:
            lines.append(f"Stack: {stack_text}")

    lines.append("\n### Relevant Rules")
    rules = pack_data.get("relevant_rules", {})
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

    decisions = pack_data.get("recent_decisions", [])
    if decisions:
        lines.append("\n### Recent Decisions")
        for item in decisions:
            lines.append(f"- {item}")

    modules = pack_data.get("affected_modules", [])
    if modules:
        lines.append("\n### Affected Modules")
        for item in modules:
            lines.append(f"- {item}")

    lines.append("\n### Expectations")
    expect = pack_data.get("expectations", {})
    if expect.get("goal"):
        lines.append(f"Goal: {expect['goal']}")
    if expect.get("active_phase"):
        lines.append(f"Active phase: {expect['active_phase']}")
    for run in expect.get("active_runs", []):
        lines.append(f"- Run {run.get('run', '?')} [{run.get('status', '?')}]: {run.get('goal', '')}")

    unresolved = pack_data.get("unresolved", {})
    if any(unresolved.values()):
        lines.append("\n### Unresolved")
        for label, items in (("Facts", unresolved.get("facts", [])), ("Acts", unresolved.get("acts", [])), ("Expect", unresolved.get("expect", []))):
            if items:
                lines.append(f"{label}:")
                for item in items:
                    lines.append(f"- {item}")

    risks = pack_data.get("task_risks", [])
    if risks:
        lines.append("\n### Task Risks")
        for risk in risks:
            lines.append(f"- {risk}")

    hints = pack_data.get("retrieval_hints", {})
    if isinstance(hints, dict):
        sources = hints.get("likely_relevant_sources", [])
        file_refs = hints.get("candidate_file_refs", [])
        archive_available = bool(hints.get("archive_available"))
        if sources or file_refs or archive_available:
            lines.append("\n### Retrieval Hints")
            if sources:
                lines.append(f"Likely sources: {', '.join(sources)}")
            if file_refs:
                for item in file_refs[:6]:
                    lines.append(f"- {item}")
            if archive_available:
                lines.append("Archive history exists and may contain relevant prior context.")

    meta = pack_data.get("_meta", {})
    notes = meta.get("compaction_notes", [])
    if notes:
        lines.append("\n### Compaction")
        for note in notes:
            lines.append(f"- {note}")

    return "\n".join(lines)


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
    text = str(value).strip() if value is not None else ""
    return text if text else default


def _clean_str_list(items: list[Any]) -> list[str]:
    out: list[str] = []
    for item in items:
        text = _clean_str(item)
        if text:
            out.append(text)
    return out


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


DEFAULT_CONTEXT_FETCH_SOURCES = [
    "facts",
    "rules",
    "acts",
    "archived_acts",
    "expect",
    "map",
    "file_refs",
]


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
        sources=["facts", "rules", "acts", "archived_acts", "expect", "map"],
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


def search_context_memory(
    project_dir: str,
    *,
    task: str,
    query: str,
    sources: list[str] | None = None,
    limit: int = 5,
    frame_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Search governed FRAME memory without falling back to repo-wide content search."""
    frame = frame_data if isinstance(frame_data, dict) else load_frame_data(project_dir)
    resolved_sources = _normalize_fetch_sources(sources)
    hits = _ranked_memory_hits(project_dir, frame, task=task, query=query, sources=resolved_sources)
    if limit < 1:
        limit = 5
    if len(hits) > limit:
        # Overfetch is intentional here: when several matches tie at the cutoff,
        # keep all of them instead of hiding equally relevant governed history.
        cutoff = hits[limit - 1]["score"]
        hits = [hit for hit in hits if int(hit.get("score", 0)) >= cutoff]
    hits = _attach_archived_record_details(project_dir, hits)
    file_refs: list[str] = []
    for hit in hits:
        for ref in hit.get("file_refs", []):
            if ref not in file_refs:
                file_refs.append(ref)
    archive = ActsArchive(project_dir)
    return {
        "task": task,
        "query": query,
        "sources": resolved_sources,
        "limit": limit,
        "archive_available": archive.exists(),
        "hits": hits,
        "candidate_file_refs": file_refs,
    }


def _normalize_fetch_sources(sources: list[str] | None) -> list[str]:
    if not isinstance(sources, list) or not sources:
        return list(DEFAULT_CONTEXT_FETCH_SOURCES)
    allowed = set(DEFAULT_CONTEXT_FETCH_SOURCES)
    normalized: list[str] = []
    for item in sources:
        text = str(item or "").strip().lower()
        if text in allowed and text not in normalized:
            normalized.append(text)
    return normalized or list(DEFAULT_CONTEXT_FETCH_SOURCES)


def _attach_archived_record_details(project_dir: str, hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Add full archive record details only for the archived hits we will return."""
    archived_record_keys: list[tuple[str, str]] = []
    for hit in hits:
        if str(hit.get("source", "")) != "archived_acts":
            continue
        kind = _clean_str(hit.get("kind", ""))
        record_id = _clean_str(hit.get("id", ""))
        if kind and record_id:
            archived_record_keys.append((kind, record_id))

    if not archived_record_keys:
        return hits

    archive = ActsArchive(project_dir)
    record_details = archive.load_selected_record_details(archived_record_keys)
    hits_with_details: list[dict[str, Any]] = []
    for hit in hits:
        if str(hit.get("source", "")) != "archived_acts":
            hits_with_details.append(hit)
            continue
        key = (_clean_str(hit.get("kind", "")), _clean_str(hit.get("id", "")))
        updated = dict(hit)
        updated["details"] = record_details.get(key, {})
        hits_with_details.append(updated)
    return hits_with_details


def _tokenize(text: str) -> list[str]:
    tokens: list[str] = []
    seen = set()
    for raw in str(text or "").lower().replace("/", " ").replace("-", " ").replace("_", " ").split():
        token = "".join(ch for ch in raw if ch.isalnum())
        if len(token) < 3 or token in seen:
            continue
        seen.add(token)
        tokens.append(token)
    return tokens


def _unique_refs(items: list[str]) -> list[str]:
    out: list[str] = []
    seen = set()
    for item in items:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def _map_module_refs(map_data: dict[str, Any], file_refs: list[str], text_tokens: list[str]) -> list[str]:
    modules = map_data.get("modules", []) if isinstance(map_data, dict) else []
    matched: list[str] = []
    for module in modules if isinstance(modules, list) else []:
        if not isinstance(module, dict):
            continue
        name = _clean_str(module.get("name", ""))
        if not name:
            continue
        files = _clean_str_list(module.get("files", []))
        if any(name.lower() == token for token in text_tokens):
            matched.append(name)
            continue
        for ref in file_refs:
            if any(file_ref in ref or ref in file_ref for file_ref in files):
                matched.append(name)
                break
    return _unique_refs(matched)


def _file_ref_terms(file_refs: list[str]) -> list[str]:
    terms: list[str] = []
    for ref in file_refs:
        terms.extend(_tokenize(ref))
    return terms


def _candidate(
    *,
    source: str,
    kind: str,
    title: str,
    text: str,
    file_refs: list[str] | None = None,
    module_refs: list[str] | None = None,
    record_id: str = "",
    timestamp: str = "",
    status_or_result: str = "",
    keywords: list[str] | None = None,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    refs = _unique_refs(list(file_refs or []))
    modules = _unique_refs(list(module_refs or []))
    search_text = " ".join(
        part for part in [title, text, record_id, status_or_result, " ".join(refs), " ".join(modules), " ".join(keywords or [])] if part
    )
    return {
        "source": source,
        "kind": kind,
        "title": title,
        "text": text,
        "file_refs": refs,
        "module_refs": modules,
        "id": record_id,
        "timestamp": timestamp,
        "status_or_result": status_or_result,
        "keywords": _unique_refs(list(keywords or [])) or _tokenize(search_text)[:12],
        "details": details or {},
        "_tokens": _tokenize(search_text),
    }


def _ranked_memory_hits(
    project_dir: str,
    frame: dict[str, Any],
    *,
    task: str,
    query: str,
    sources: list[str],
) -> list[dict[str, Any]]:
    candidates = _memory_candidates(project_dir, frame, sources=sources)
    query_tokens = _tokenize(f"{task} {query}")
    query_set = set(query_tokens)
    scored: list[dict[str, Any]] = []
    for candidate in candidates:
        token_matches = sum(1 for token in candidate["_tokens"] if token in query_set)
        file_matches = sum(1 for token in _file_ref_terms(candidate.get("file_refs", [])) if token in query_set)
        module_matches = sum(1 for token in _tokenize(" ".join(candidate.get("module_refs", []))) if token in query_set)
        keyword_matches = sum(1 for token in candidate.get("keywords", []) if token in query_set)
        score = (token_matches * 10) + (module_matches * 6) + (file_matches * 4) + (keyword_matches * 3)
        if candidate["source"] in {"acts", "archived_acts"} and candidate.get("file_refs"):
            score += 2
        if candidate["source"] == "map" and candidate.get("module_refs"):
            score += 1
        if score <= 0:
            continue
        hit = dict(candidate)
        hit["score"] = score
        hit["match_counts"] = {
            "text": token_matches,
            "module": module_matches,
            "file_ref": file_matches,
            "keyword": keyword_matches,
        }
        hit.pop("_tokens", None)
        scored.append(hit)
    scored.sort(
        key=lambda item: (
            -int(item.get("score", 0)),
            str(item.get("source", "")),
            str(item.get("kind", "")),
            str(item.get("timestamp", "")),
            str(item.get("title", "")),
        )
    )
    return scored


def _memory_candidates(project_dir: str, frame: dict[str, Any], *, sources: list[str]) -> list[dict[str, Any]]:
    facts = frame.get("facts") or {}
    rules = frame.get("rules") or {}
    acts = frame.get("acts") or {}
    expect = frame.get("expect") or {}
    map_data = frame.get("map") or {}
    candidates: list[dict[str, Any]] = []

    if "facts" in sources:
        identity = facts.get("identity") or {}
        goal = facts.get("goal") or {}
        architecture = facts.get("architecture") or {}
        constraints = _clean_str_list(facts.get("constraints", []))
        candidates.extend(
            [
                _candidate(
                    source="facts",
                    kind="identity",
                    title="facts.identity",
                    text=" ".join(
                        [
                            _clean_str(identity.get("name", "")),
                            _clean_str(identity.get("description", "")),
                            _clean_str(goal.get("purpose", "")),
                            _clean_str(goal.get("scope", "")),
                        ]
                    ),
                    file_refs=[".haxaml/facts.yaml"],
                    module_refs=_clean_str_list(architecture.get("boundaries", [])),
                ),
                _candidate(
                    source="facts",
                    kind="constraints",
                    title="facts.constraints",
                    text=" ".join(constraints),
                    file_refs=[".haxaml/facts.yaml"],
                    module_refs=_clean_str_list(architecture.get("boundaries", [])),
                ),
            ]
        )
        for item in facts.get("unresolved", []) if isinstance(facts.get("unresolved", []), list) else []:
            if not isinstance(item, dict):
                continue
            candidates.append(
                _candidate(
                    source="facts",
                    kind="unresolved",
                    title=f"facts.unresolved:{_clean_str(item.get('item', ''))}",
                    text=" ".join(
                        [
                            _clean_str(item.get("item", "")),
                            _clean_str(item.get("reason", "")),
                            _clean_str(item.get("question", "")),
                        ]
                    ),
                    file_refs=[".haxaml/facts.yaml"],
                )
            )

    if "rules" in sources:
        before = rules.get("before_task") or {}
        after = rules.get("after_task") or {}
        memory_policy = rules.get("memory_policy") or {}
        rules_file_refs = [".haxaml/rules.yaml"] + _clean_str_list(before.get("read_first", [])) + _clean_str_list(before.get("then_read", []))
        candidates.extend(
            [
                _candidate(
                    source="rules",
                    kind="before_task",
                    title="rules.before_task",
                    text=" ".join(_clean_str_list(before.get("check", []))),
                    file_refs=rules_file_refs,
                ),
                _candidate(
                    source="rules",
                    kind="boundaries",
                    title="rules.boundaries",
                    text=" ".join(_clean_str_list((rules.get("boundaries") or {}).get("rules", []))),
                    file_refs=[".haxaml/rules.yaml"],
                    module_refs=_clean_str_list(list(((rules.get("boundaries") or {}).get("modules") or {}).keys())),
                ),
                _candidate(
                    source="rules",
                    kind="forbidden",
                    title="rules.forbidden",
                    text=" ".join(_clean_str_list(rules.get("forbidden", []))),
                    file_refs=[".haxaml/rules.yaml"],
                ),
                _candidate(
                    source="rules",
                    kind="memory_policy",
                    title="rules.memory_policy",
                    text=" ".join(f"{k} {v}" for k, v in memory_policy.items()) if isinstance(memory_policy, dict) else "",
                    file_refs=[".haxaml/rules.yaml"],
                ),
                _candidate(
                    source="rules",
                    kind="after_task",
                    title="rules.after_task",
                    text=" ".join(_clean_str_list(after.get("verify", [])) + _clean_str_list(after.get("report", []))),
                    file_refs=[".haxaml/rules.yaml"],
                ),
            ]
        )

    if "acts" in sources:
        for item in acts.get("decisions", []) if isinstance(acts.get("decisions", []), list) else []:
            if not isinstance(item, dict):
                continue
            candidates.append(
                _candidate(
                    source="acts",
                    kind="decision",
                    title=f"decision:{_clean_str(item.get('decision', ''))}",
                    text=" ".join([_clean_str(item.get("decision", "")), _clean_str(item.get("reasoning", ""))]),
                    file_refs=[".haxaml/acts.yaml"] + _clean_str_list(item.get("file_refs", [])),
                    module_refs=_clean_str_list(item.get("module_refs", [])),
                    timestamp=_clean_str(item.get("date", "")),
                )
            )
        for item in acts.get("runs", []) if isinstance(acts.get("runs", []), list) else []:
            if not isinstance(item, dict):
                continue
            candidates.append(
                _candidate(
                    source="acts",
                    kind="run",
                    title=f"run:{_clean_str(item.get('id', ''))}",
                    text=" ".join(
                        [
                            _clean_str(item.get("task", "")),
                            _clean_str(item.get("changes", "")),
                            _clean_str(item.get("decisions", "")),
                            _clean_str(item.get("risks", "")),
                        ]
                    ),
                    file_refs=_clean_str_list(item.get("file_refs", [])),
                    module_refs=_clean_str_list(item.get("module_refs", [])),
                    record_id=_clean_str(item.get("id", "")),
                    timestamp=_clean_str(item.get("timestamp", "")),
                    status_or_result=_clean_str(item.get("result", "")),
                    keywords=_clean_str_list(item.get("keywords", [])),
                )
            )
        for item in acts.get("verifications", []) if isinstance(acts.get("verifications", []), list) else []:
            if not isinstance(item, dict):
                continue
            candidates.append(
                _candidate(
                    source="acts",
                    kind="verification",
                    title=f"verification:{_clean_str(item.get('id', ''))}",
                    text=" ".join(
                        [
                            _clean_str(item.get("task", "")),
                            _clean_str(item.get("summary", "")),
                            " ".join(_clean_str_list(item.get("follow_ups", []))),
                        ]
                    ),
                    file_refs=_clean_str_list(item.get("file_refs", [])) or _clean_str_list(item.get("evidence_refs", [])),
                    module_refs=_clean_str_list(item.get("module_refs", [])),
                    record_id=_clean_str(item.get("id", "")),
                    timestamp=_clean_str(item.get("timestamp", "")),
                    status_or_result=_clean_str(item.get("verdict", "")),
                    keywords=_clean_str_list(item.get("keywords", [])),
                )
            )
        for item in acts.get("sessions", []) if isinstance(acts.get("sessions", []), list) else []:
            if not isinstance(item, dict):
                continue
            candidates.append(
                _candidate(
                    source="acts",
                    kind="session",
                    title=f"session:{_clean_str(item.get('id', ''))}",
                    text=" ".join(
                        [
                            _clean_str(item.get("task", "")),
                            _clean_str(item.get("description", "")),
                            " ".join(_clean_str_list(item.get("plan", []))),
                        ]
                    ),
                    file_refs=_clean_str_list(item.get("file_refs", [])),
                    module_refs=_clean_str_list(item.get("module_refs", [])),
                    record_id=_clean_str(item.get("id", "")),
                    timestamp=_clean_str(item.get("updated", "")) or _clean_str(item.get("started", "")),
                    status_or_result=_clean_str(item.get("status", "")),
                    keywords=_clean_str_list(item.get("keywords", [])),
                )
            )

    if "archived_acts" in sources:
        archive = ActsArchive(project_dir)
        if archive.exists():
            for entry in archive.index_entries():
                kind = _clean_str(entry.get("kind", ""))
                record_id = _clean_str(entry.get("id", ""))
                # Rank archive matches from the compact index first. Full record bodies
                # are only loaded later for the hits we actually return.
                candidates.append(
                    _candidate(
                        source="archived_acts",
                        kind=kind or "archived",
                        title=f"archived:{record_id}",
                        text=" ".join(
                            [
                                _clean_str(entry.get("task", "")),
                                _clean_str(entry.get("summary", "")),
                                _clean_str(entry.get("status_or_result", "")),
                            ]
                        ),
                        file_refs=_clean_str_list(entry.get("file_refs", [])),
                        module_refs=_clean_str_list(entry.get("module_refs", [])),
                        record_id=record_id,
                        timestamp=_clean_str(entry.get("timestamp", "")),
                        status_or_result=_clean_str(entry.get("status_or_result", "")),
                        keywords=_clean_str_list(entry.get("keywords", [])),
                    )
                )

    if "expect" in sources:
        planning = expect.get("planning") or {}
        runbook = expect.get("runbook", []) if isinstance(expect.get("runbook", []), list) else []
        candidates.append(
            _candidate(
                source="expect",
                kind="planning",
                title="expect.planning",
                text=" ".join(
                    [
                        _clean_str(planning.get("goal", "")),
                        _clean_str(planning.get("strategy", "")),
                        _clean_str(planning.get("map_reason", "")),
                    ]
                ),
                file_refs=[".haxaml/expect.yaml"],
            )
        )
        for item in runbook:
            if not isinstance(item, dict):
                continue
            file_refs = _clean_str_list(item.get("touches", [])) + _clean_str_list(item.get("requires", []))
            candidates.append(
                _candidate(
                    source="expect",
                    kind="runbook",
                    title=f"expect.run:{item.get('run', '?')}",
                    text=" ".join(
                        [
                            _clean_str(item.get("phase", "")),
                            _clean_str(item.get("goal", "")),
                            _clean_str(item.get("outcome", "")),
                            " ".join(_clean_str_list(item.get("verify", []))),
                        ]
                    ),
                    file_refs=file_refs,
                    module_refs=_map_module_refs(map_data, file_refs, _tokenize(" ".join(file_refs + [_clean_str(item.get("goal", ""))]))),
                    status_or_result=_clean_str(item.get("status", "")),
                )
            )
        for item in expect.get("open_questions", []) if isinstance(expect.get("open_questions", []), list) else []:
            if not isinstance(item, dict):
                continue
            candidates.append(
                _candidate(
                    source="expect",
                    kind="open_question",
                    title="expect.open_question",
                    text=" ".join([_clean_str(item.get("question", "")), _clean_str(item.get("reason", ""))]),
                    file_refs=[".haxaml/expect.yaml"],
                )
            )

    if "map" in sources:
        modules = map_data.get("modules", []) if isinstance(map_data, dict) else []
        for module in modules if isinstance(modules, list) else []:
            if not isinstance(module, dict):
                continue
            files = _clean_str_list(module.get("files", []))
            candidates.append(
                _candidate(
                    source="map",
                    kind="module",
                    title=f"map.module:{_clean_str(module.get('name', ''))}",
                    text=" ".join(
                        [
                            _clean_str(module.get("name", "")),
                            _clean_str(module.get("purpose", "")),
                            _clean_str(module.get("owner", "")),
                            " ".join(_clean_str_list(module.get("touches", []))),
                            _clean_str(module.get("notes", "")),
                        ]
                    ),
                    file_refs=files,
                    module_refs=[_clean_str(module.get("name", ""))],
                )
            )

    if "file_refs" in sources:
        derived_refs: list[str] = []
        for candidate in list(candidates):
            for ref in candidate.get("file_refs", []):
                if ref not in derived_refs:
                    derived_refs.append(ref)
        for ref in derived_refs:
            candidates.append(
                _candidate(
                    source="file_refs",
                    kind="file_ref",
                    title=ref,
                    text=ref,
                    file_refs=[ref],
                    module_refs=_map_module_refs(map_data, [ref], _tokenize(ref)),
                )
            )

    return candidates


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
