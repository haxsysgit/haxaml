"""Agent profile and few-shot rendering helpers for export output."""

from __future__ import annotations

from typing import Any, Optional

from haxaml.utils import normalized_text


DEFAULT_EXAMPLE_POLICY = {
    "max_examples": 4,
    "max_input_chars": 320,
    "max_output_chars": 420,
    "max_total_chars": 2800,
    "derived_from_acts_max": 4,
    "ordering": "explicit_then_derived",
    "fallback_when_empty": "render_notice",
}


def agent_profile(rules: Optional[dict]) -> dict:
    """Return the agent_profile block from rules when present."""
    if not isinstance(rules, dict):
        return {}
    profile = rules.get("agent_profile", {})
    return profile if isinstance(profile, dict) else {}


def _truncate_text(text: str, max_chars: int) -> tuple[str, bool]:
    if len(text) <= max_chars:
        return text, False
    if max_chars <= 1:
        return "…", True
    return text[: max_chars - 1].rstrip() + "…", True


def _safe_int(value: Any, default: int) -> int:
    return value if isinstance(value, int) and value >= 0 else default


def _example_policy(profile: dict) -> dict:
    policy = dict(DEFAULT_EXAMPLE_POLICY)
    incoming = profile.get("example_policy", {})
    if isinstance(incoming, dict):
        for key, default in DEFAULT_EXAMPLE_POLICY.items():
            if key not in incoming:
                continue
            if isinstance(default, int):
                policy[key] = _safe_int(incoming[key], default)
            elif isinstance(default, str) and isinstance(incoming[key], str):
                policy[key] = incoming[key]
    return policy


def render_agent_persona(rules: Optional[dict]) -> str:
    """Render the agent persona section."""
    profile = agent_profile(rules)
    persona = profile.get("persona", {})
    if not isinstance(persona, dict):
        persona = {}

    role = normalized_text(
        persona.get(
            "role",
            "Deterministic software engineer operating under FRAME governance and explicit project constraints.",
        )
    )
    tone = persona.get("tone", [])
    constraints = persona.get("constraints", [])

    tone_items = tone if isinstance(tone, list) and tone else [
        "Direct, concise, and factual communication.",
        "Prioritize practical implementation and verification steps.",
    ]
    constraint_items = constraints if isinstance(constraints, list) and constraints else [
        "Keep generated outputs deterministic from FRAME input files.",
        "Avoid unverified claims; report checks and residual risks.",
    ]

    lines = [f"Role: {role}", "\nTone:"]
    lines.extend(f"- {normalized_text(item)}" for item in tone_items if normalized_text(item))
    lines.append("\nOperating constraints:")
    lines.extend(f"- {normalized_text(item)}" for item in constraint_items if normalized_text(item))
    return "\n".join(lines)


def render_agent_reasoning_policy(rules: Optional[dict]) -> str:
    """Render the public/private reasoning and output contract section."""
    profile = agent_profile(rules)
    reasoning = profile.get("reasoning_policy", {})
    output_contract = profile.get("output_contract", {})
    if not isinstance(reasoning, dict):
        reasoning = {}
    if not isinstance(output_contract, dict):
        output_contract = {}

    private_reasoning = normalized_text(
        reasoning.get(
            "private_reasoning",
            "Keep private reasoning internal. Do not expose internal deliberation transcripts.",
        )
    )
    public_rationale = normalized_text(
        reasoning.get(
            "public_rationale",
            "Provide concise rationale tied to file changes, tests, and concrete evidence.",
        )
    )
    checklist = reasoning.get("checklist", [])
    checklist_items = checklist if isinstance(checklist, list) and checklist else [
        "State what changed.",
        "List tests/checks run.",
        "State remaining risks or follow-ups.",
    ]

    required_sections = output_contract.get("required_sections", [])
    required_items = (
        required_sections
        if isinstance(required_sections, list) and required_sections
        else ["Summary", "Changes", "Verification", "Risks"]
    )
    format_notes = output_contract.get("format_notes", [])
    format_items = format_notes if isinstance(format_notes, list) else []

    lines = [
        f"Private reasoning policy: {private_reasoning}",
        f"Public rationale policy: {public_rationale}",
        "\nResponse checklist:",
    ]
    lines.extend(f"- {normalized_text(item)}" for item in checklist_items if normalized_text(item))
    lines.append("\nOutput contract:")
    lines.extend(
        f"- Required section: `{normalized_text(item)}`"
        for item in required_items
        if normalized_text(item)
    )
    for note in format_items:
        normalized = normalized_text(note)
        if normalized:
            lines.append(f"- Format note: {normalized}")

    return "\n".join(lines)


def _explicit_examples(profile: dict) -> list[dict]:
    explicit = []
    raw = profile.get("few_shot_examples", [])
    if not isinstance(raw, list):
        return explicit
    for item in raw:
        if not isinstance(item, dict):
            continue
        input_text = normalized_text(item.get("input"))
        output_text = normalized_text(item.get("output"))
        if not input_text or not output_text:
            continue
        explicit.append(
            {
                "source": "explicit",
                "title": normalized_text(item.get("title")) or "Explicit example",
                "input": input_text,
                "output": output_text,
            }
        )
    return explicit


def _derived_examples_from_acts(acts: Optional[dict]) -> list[dict]:
    if not isinstance(acts, dict):
        return []

    derived = []

    decisions = acts.get("decisions", [])
    if isinstance(decisions, list):
        for item in reversed(decisions):
            if not isinstance(item, dict):
                continue
            decision = normalized_text(item.get("decision"))
            reasoning = normalized_text(item.get("reasoning"))
            if not decision or not reasoning:
                continue
            derived.append(
                {
                    "source": "derived",
                    "title": f"Decision pattern: {decision}",
                    "input": f"User asks for a decision: {decision}",
                    "output": f"Decision: {decision}\nRationale: {reasoning}",
                }
            )

    completed_tasks = acts.get("completed_tasks", [])
    if isinstance(completed_tasks, list):
        for item in reversed(completed_tasks):
            if not isinstance(item, dict):
                continue
            name = normalized_text(item.get("name"))
            summary = normalized_text(item.get("summary"))
            result = normalized_text(item.get("result")) or "unknown"
            if not name or not summary:
                continue
            derived.append(
                {
                    "source": "derived",
                    "title": f"Completion pattern: {name}",
                    "input": f"User asks for implementation status on '{name}'.",
                    "output": f"Result: {result}\nSummary: {summary}",
                }
            )

    return derived


def _select_examples(rules: Optional[dict], acts: Optional[dict]) -> tuple[list[dict], list[str]]:
    profile = agent_profile(rules)
    policy = _example_policy(profile)
    max_examples = max(1, policy["max_examples"])
    max_input_chars = max(64, policy["max_input_chars"])
    max_output_chars = max(64, policy["max_output_chars"])
    max_total_chars = max(256, policy["max_total_chars"])
    derived_cap = policy["derived_from_acts_max"]

    explicit = _explicit_examples(profile)
    derived = _derived_examples_from_acts(acts)[:derived_cap]
    pool = explicit + derived

    selected = []
    total_chars = 0
    truncated_fields = 0
    omitted_for_budget = 0

    for item in pool:
        if len(selected) >= max_examples:
            break

        title, title_trunc = _truncate_text(normalized_text(item.get("title", "")), 120)
        input_text, input_trunc = _truncate_text(normalized_text(item.get("input", "")), max_input_chars)
        output_text, output_trunc = _truncate_text(normalized_text(item.get("output", "")), max_output_chars)

        if title_trunc or input_trunc or output_trunc:
            truncated_fields += int(title_trunc) + int(input_trunc) + int(output_trunc)

        candidate_size = len(title) + len(input_text) + len(output_text)
        if selected and total_chars + candidate_size > max_total_chars:
            omitted_for_budget += 1
            break

        selected.append(
            {
                "source": item["source"],
                "title": title,
                "input": input_text,
                "output": output_text,
            }
        )
        total_chars += candidate_size

    notes = [
        "Source precedence: explicit `rules.agent_profile.few_shot_examples` first, then derived snippets from recent `acts` decisions/completed tasks."
    ]
    if len(pool) > len(selected):
        notes.append(
            f"Compaction: showing {len(selected)} of {len(pool)} candidate examples (max_examples={max_examples})."
        )
    if omitted_for_budget:
        notes.append(
            f"Budget guard: stopped after deterministic prefix because max_total_chars={max_total_chars} was reached."
        )
    if truncated_fields:
        notes.append(
            f"Truncation: compacted {truncated_fields} field(s) to per-example limits "
            f"(input={max_input_chars}, output={max_output_chars})."
        )
    return selected, notes


def render_agent_few_shot_examples(rules: Optional[dict], acts: Optional[dict]) -> str:
    """Render deterministic few-shot examples for export output."""
    profile = agent_profile(rules)
    policy = _example_policy(profile)
    examples, notes = _select_examples(rules, acts)

    if not examples:
        if policy.get("fallback_when_empty") == "omit_section":
            return ""
        return (
            "No few-shot examples available.\n\n"
            "Add `rules.agent_profile.few_shot_examples` or keep recent decisions/completed-task "
            "summaries in `.haxaml/acts.yaml` to generate deterministic examples."
        )

    lines = [f"- {note}" for note in notes]
    for idx, example in enumerate(examples, start=1):
        lines.append(f"\n### Example {idx} ({example['source']})")
        lines.append(f"Input: {example['input']}")
        lines.append("Output:")
        lines.append(example["output"])
    return "\n".join(lines)
