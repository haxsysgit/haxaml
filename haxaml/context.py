"""Context builder — produces minimal context for AI agent consumption."""

from pathlib import Path

import yaml

from haxaml.paths import resolve_frame_file


def build_context(project_dir: str, include_state: bool = True) -> str:
    """Build minimal context string from FRAME files.

    This is what gets loaded at the start of an agent task.
    Loads: facts + rules + acts (+ expect if present).
    """
    project = Path(project_dir)
    parts = []

    # F — Facts
    facts_path = resolve_frame_file(project, "facts.yaml", "brain.yaml")
    if facts_path:
        with open(facts_path) as f:
            facts = yaml.safe_load(f)
        parts.append(_format_facts_context(facts))
    else:
        parts.append("⚠ facts.yaml not found — project facts are missing.")

    # R — Rules
    rules_path = resolve_frame_file(project, "rules.yaml", "mind.yaml")
    if rules_path:
        with open(rules_path) as f:
            rules = yaml.safe_load(f)
        parts.append(_format_rules_context(rules))

    # A — Acts
    if include_state:
        acts_path = resolve_frame_file(project, "acts.yaml", "state.yaml")
        if acts_path:
            with open(acts_path) as f:
                acts = yaml.safe_load(f)
            parts.append(_format_acts_context(acts))

    # E — Expect
    expect_path = resolve_frame_file(project, "expect.yaml")
    if expect_path:
        with open(expect_path) as f:
            expect = yaml.safe_load(f)
        parts.append(_format_expect_context(expect))

    return "\n\n---\n\n".join(parts)


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
        return len(text.split())  # rough fallback
