"""Governed FRAME memory retrieval and ranking helpers."""

from __future__ import annotations

from typing import Any

from haxaml.acts_archive import ActsArchive
from haxaml.runtime_cache import runtime_cache
from haxaml.utils import clean_str_list, normalized_text


DEFAULT_CONTEXT_FETCH_SOURCES = [
    "facts",
    "rules",
    "acts",
    "archived_acts",
    "expect",
    "map",
    "file_refs",
]


def _load_frame_data(project_dir: str) -> dict[str, Any]:
    return runtime_cache().get_frame_bundle(project_dir)["data"]


def _clean_str(value: Any, default: str = "") -> str:
    return normalized_text(value) or default


def _clean_str_list(items: Any) -> list[str]:
    return clean_str_list(items if isinstance(items, list) else [])


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
    frame = frame_data if isinstance(frame_data, dict) else _load_frame_data(project_dir)
    resolved_sources = _normalize_fetch_sources(sources)
    hits = _ranked_memory_hits(project_dir, frame, task=task, query=query, sources=resolved_sources)
    if limit < 1:
        limit = 5
    if len(hits) > limit:
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
        part
        for part in [
            title,
            text,
            record_id,
            status_or_result,
            " ".join(refs),
            " ".join(modules),
            " ".join(keywords or []),
        ]
        if part
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
        for item in acts.get("completed_tasks", []) if isinstance(acts.get("completed_tasks", []), list) else []:
            if not isinstance(item, dict):
                continue
            candidates.append(
                _candidate(
                    source="acts",
                    kind="completed_task",
                    title=f"completed:{_clean_str(item.get('name', ''))}",
                    text=" ".join(
                        [
                            _clean_str(item.get("name", "")),
                            _clean_str(item.get("summary", "")),
                            _clean_str(item.get("result", "")),
                        ]
                    ),
                    record_id=_clean_str(item.get("id", "")),
                    timestamp=_clean_str(item.get("completed", "")),
                    status_or_result=_clean_str(item.get("result", "")),
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
