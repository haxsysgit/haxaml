"""Small shared normalization helpers used across Haxaml."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable


DEFAULT_KEYWORD_STOP_WORDS = frozenset(
    {
        "the",
        "and",
        "for",
        "with",
        "that",
        "this",
        "from",
        "into",
        "have",
        "will",
        "when",
        "what",
        "where",
        "then",
        "than",
        "them",
        "they",
        "been",
        "were",
        "your",
        "about",
        "after",
        "before",
        "only",
        "over",
        "under",
        "task",
        "tasks",
        "work",
        "works",
        "working",
        "update",
        "updated",
        "using",
    }
)


def now_iso() -> str:
    """Return the current UTC timestamp in ISO-8601 format."""
    return datetime.now(timezone.utc).isoformat()


def normalized_text(value: Any) -> str:
    """Return a stripped string representation of a value."""
    return str(value or "").strip()


def clean_str_list(items: Any) -> list[str]:
    """Return an ordered, deduplicated list of non-empty strings."""
    if not isinstance(items, list):
        return []
    cleaned: list[str] = []
    seen = set()
    for item in items:
        text = normalized_text(item)
        if not text or text in seen:
            continue
        seen.add(text)
        cleaned.append(text)
    return cleaned


def keywords_from_text(
    *parts: Any,
    limit: int = 12,
    stop_words: Iterable[str] | None = DEFAULT_KEYWORD_STOP_WORDS,
) -> list[str]:
    """Extract compact, deduplicated keywords from free text."""
    blocked = {str(item).lower() for item in (stop_words or ())}
    tokens: list[str] = []
    seen = set()
    for part in parts:
        text = normalized_text(part).lower()
        if not text:
            continue
        for raw in text.replace("/", " ").replace("-", " ").replace("_", " ").split():
            token = "".join(ch for ch in raw if ch.isalnum())
            if len(token) < 4 or token in blocked or token in seen:
                continue
            seen.add(token)
            tokens.append(token)
            if len(tokens) >= limit:
                return tokens
    return tokens
