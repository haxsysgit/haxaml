"""Token efficiency benchmarks — YAML vs JSON, growth tracking, context budgets.

Implements Experiments 2, 3, and 5 from research.md.
"""

import json
import time
from pathlib import Path
from typing import Optional

import yaml

from haxaml.context import count_tokens
from haxaml.paths import resolve_frame_file
from haxaml.validator import load_yaml


def benchmark_format_tokens(facts_path: str) -> dict:
    """Experiment 2: Compare token counts across YAML, JSON, and compact JSON.

    Returns dict with token counts and sizes for each format.
    """
    brain = load_yaml(facts_path)

    yaml_text = yaml.dump(brain, default_flow_style=False, sort_keys=False)
    json_text = json.dumps(brain, indent=2)
    json_compact = json.dumps(brain, separators=(",", ":"))

    yaml_tokens = count_tokens(yaml_text)
    json_tokens = count_tokens(json_text)
    json_compact_tokens = count_tokens(json_compact)

    return {
        "yaml": {
            "tokens": yaml_tokens,
            "chars": len(yaml_text),
            "bytes": len(yaml_text.encode("utf-8")),
        },
        "json_pretty": {
            "tokens": json_tokens,
            "chars": len(json_text),
            "bytes": len(json_text.encode("utf-8")),
        },
        "json_compact": {
            "tokens": json_compact_tokens,
            "chars": len(json_compact),
            "bytes": len(json_compact.encode("utf-8")),
        },
        "winner": min(
            [("yaml", yaml_tokens), ("json_pretty", json_tokens), ("json_compact", json_compact_tokens)],
            key=lambda x: x[1]
        )[0],
        "savings_vs_worst": {
            "yaml_vs_json_pretty": json_tokens - yaml_tokens,
            "compact_vs_pretty": json_tokens - json_compact_tokens,
            "yaml_vs_compact": json_compact_tokens - yaml_tokens,
        },
    }


def benchmark_parse_speed(facts_path: str, iterations: int = 100) -> dict:
    """Benchmark parse speed for YAML vs JSON.

    Returns average parse time in milliseconds.
    """
    brain = load_yaml(facts_path)

    yaml_text = yaml.dump(brain, default_flow_style=False, sort_keys=False)
    json_text = json.dumps(brain)

    start = time.perf_counter()
    for _ in range(iterations):
        yaml.safe_load(yaml_text)
    yaml_time = (time.perf_counter() - start) / iterations * 1000

    start = time.perf_counter()
    for _ in range(iterations):
        json.loads(json_text)
    json_time = (time.perf_counter() - start) / iterations * 1000

    return {
        "yaml_ms": round(yaml_time, 3),
        "json_ms": round(json_time, 3),
        "ratio": round(yaml_time / json_time, 1) if json_time > 0 else 0,
        "iterations": iterations,
    }


def simulate_state_growth(base_state: dict, num_runs: int = 50,
                          task_desc_length: int = 80) -> list[dict]:
    """Experiment 3: Simulate state growth over N runs.

    Returns a list of measurements at each step.
    """
    import copy
    state = copy.deepcopy(base_state)
    if "runs" not in state:
        state["runs"] = []
    if "completed_tasks" not in state:
        state["completed_tasks"] = []
    if "decisions" not in state:
        state["decisions"] = []

    measurements = []

    for i in range(num_runs):
        run_entry = {
            "id": f"run-{i:04d}",
            "task": f"Implement feature {i}: {'x' * task_desc_length}",
            "result": "success" if i % 5 != 0 else "partial",
            "changes": f"Modified {2 + i % 4} files in module_{i % 3}",
            "decisions": f"Decision {i}: chose approach {'A' if i % 2 == 0 else 'B'}" if i % 3 == 0 else "",
            "risks": f"Risk: potential regression in module_{i % 3}" if i % 7 == 0 else "",
            "timestamp": f"2025-01-{(i % 28) + 1:02d}T12:00:00Z",
        }
        state["runs"].append(run_entry)

        if i % 2 == 0:
            state["completed_tasks"].append({
                "name": f"task-{i}",
                "result": "success",
                "summary": f"Completed feature {i}",
                "completed": f"2025-01-{(i % 28) + 1:02d}T12:00:00Z",
            })

        if i % 5 == 0:
            state["decisions"].append({
                "decision": f"Architectural decision {i // 5}",
                "reasoning": f"Based on scaling requirements for phase {i // 10}",
                "date": f"2025-01-{(i % 28) + 1:02d}T12:00:00Z",
                "reversible": i % 10 != 0,
            })

        yaml_text = yaml.dump(state, default_flow_style=False, sort_keys=False)
        measurements.append({
            "run_number": i + 1,
            "total_runs": len(state["runs"]),
            "total_completed": len(state["completed_tasks"]),
            "total_decisions": len(state["decisions"]),
            "yaml_chars": len(yaml_text),
            "yaml_bytes": len(yaml_text.encode("utf-8")),
            "yaml_tokens": count_tokens(yaml_text),
        })

    return measurements


def measure_context_budget(project_dir: str) -> dict:
    """Experiment 5: Measure token budget breakdown for a project.

    Returns token counts for each component and total.
    """
    project = Path(project_dir)
    results = {}

    # Canonical FRAME files only
    for filename, label in [
        ("facts.yaml", "facts"),
        ("rules.yaml", "rules"),
        ("acts.yaml", "acts"),
        ("expect.yaml", "expect"),
    ]:
        fpath = resolve_frame_file(project, filename)
        if fpath:
            with open(fpath) as f:
                text = f.read()
            results[label] = {
                "tokens": count_tokens(text),
                "chars": len(text),
            }

    total_tokens = sum(v["tokens"] for v in results.values())
    results["total"] = {
        "tokens": total_tokens,
        "budget_4k_pct": round(total_tokens / 4000 * 100, 1),
        "budget_8k_pct": round(total_tokens / 8000 * 100, 1),
        "budget_32k_pct": round(total_tokens / 32000 * 100, 1),
    }

    return results


def format_benchmark_report(facts_path: str, project_dir: Optional[str] = None) -> str:
    """Generate a formatted benchmark report."""
    lines = ["# Haxaml Token Benchmark Report\n"]

    lines.append("## Format Comparison (YAML vs JSON)")
    fmt = benchmark_format_tokens(facts_path)
    lines.append(f"| Format | Tokens | Chars | Bytes |")
    lines.append(f"|--------|--------|-------|-------|")
    for name in ["yaml", "json_pretty", "json_compact"]:
        d = fmt[name]
        lines.append(f"| {name} | {d['tokens']} | {d['chars']} | {d['bytes']} |")
    lines.append(f"\n**Winner:** {fmt['winner']}")
    lines.append(f"**YAML vs JSON pretty:** {fmt['savings_vs_worst']['yaml_vs_json_pretty']:+d} tokens")
    lines.append(f"**YAML vs JSON compact:** {fmt['savings_vs_worst']['yaml_vs_compact']:+d} tokens")

    lines.append("\n## Parse Speed")
    speed = benchmark_parse_speed(facts_path)
    lines.append(f"- YAML: {speed['yaml_ms']}ms avg")
    lines.append(f"- JSON: {speed['json_ms']}ms avg")
    lines.append(f"- YAML is {speed['ratio']}x slower than JSON")

    if project_dir:
        lines.append("\n## Context Token Budget")
        budget = measure_context_budget(project_dir)
        for key, val in budget.items():
            if key == "total":
                lines.append(f"\n**Total: {val['tokens']} tokens**")
                lines.append(f"  - 4K budget: {val['budget_4k_pct']}%")
                lines.append(f"  - 8K budget: {val['budget_8k_pct']}%")
                lines.append(f"  - 32K budget: {val['budget_32k_pct']}%")
            else:
                lines.append(f"- {key}: {val['tokens']} tokens ({val['chars']} chars)")

    lines.append("\n## State Growth Simulation (50 runs)")
    base_state = {"current_phase": "test", "active_task": {"name": "test"}}
    growth = simulate_state_growth(base_state, num_runs=50)
    lines.append(f"| Runs | Tokens | Chars |")
    lines.append(f"|------|--------|-------|")
    for m in growth:
        if m["run_number"] in (1, 5, 10, 20, 30, 40, 50):
            lines.append(f"| {m['run_number']} | {m['yaml_tokens']} | {m['yaml_chars']} |")

    if growth:
        first = growth[0]["yaml_tokens"]
        last = growth[-1]["yaml_tokens"]
        lines.append(f"\n**Growth factor:** {round(last / first, 1)}x over 50 runs")
        lines.append(f"**Tokens at 50 runs:** {last}")
        if last > 4000:
            lines.append(f"**⚠ State alone exceeds 4K token budget at 50 runs — compaction critical**")

    return "\n".join(lines)
