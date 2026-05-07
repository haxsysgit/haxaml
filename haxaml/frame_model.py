"""Normalized FRAME model — single loading and selector layer for all FRAME files.

All MCP tools, validation, reconcile, export generation, and context packs should
load FRAME through FrameModel instead of calling raw YAML loaders directly.

FRAME files stay human-readable on disk. Haxaml loads them into this normalized
engine representation. Agents should receive minimal task-specific signals, not
full FRAME dumps.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from haxaml.paths import resolve_frame_file


@dataclass
class FrameModel:
    """Normalized representation of all five FRAME files for a project.

    Load via FrameModel.load(project_dir). Use selector methods rather than
    inspecting the raw dicts directly in new code.
    """

    facts: dict[str, Any] | None
    rules: dict[str, Any] | None
    acts: dict[str, Any] | None
    map: dict[str, Any] | None
    expect: dict[str, Any] | None

    project_dir: Path
    load_errors: list[str] = field(default_factory=list)
    missing_files: list[str] = field(default_factory=list)

    @classmethod
    def load(cls, project_dir: str | Path) -> "FrameModel":
        """Load all five FRAME files from project_dir.

        Missing files are recorded in missing_files. Load errors (bad YAML, etc.)
        are recorded in load_errors. Never raises on missing or malformed files.
        """
        project = Path(project_dir).resolve()
        load_errors: list[str] = []
        missing_files: list[str] = []

        def _load(name: str) -> dict[str, Any] | None:
            path = resolve_frame_file(project, name)
            if path is None:
                missing_files.append(name)
                return None
            try:
                with open(path, encoding="utf-8") as f:
                    # Empty YAML files are treated as empty dicts so downstream selectors can
                    # distinguish "file exists but blank" from "file missing entirely".
                    return yaml.safe_load(f) or {}
            except Exception as exc:
                load_errors.append(f"{name}: {exc}")
                return None

        facts = _load("facts.yaml")
        rules = _load("rules.yaml")
        acts = _load("acts.yaml")
        map_data = _load("map.yaml")
        expect = _load("expect.yaml")

        return cls(
            facts=facts,
            rules=rules,
            acts=acts,
            map=map_data,
            expect=expect,
            project_dir=project,
            load_errors=load_errors,
            missing_files=missing_files,
        )

    # --- presence checks ---

    def has_facts(self) -> bool:
        return self.facts is not None

    def has_rules(self) -> bool:
        return self.rules is not None

    def has_acts(self) -> bool:
        return self.acts is not None

    def has_map(self) -> bool:
        return self.map is not None

    def has_expect(self) -> bool:
        return self.expect is not None

    # --- core selectors ---

    def missing_core(self) -> list[str]:
        """Return names of core FRAME files that are absent (facts, rules, acts)."""
        core = [
            ("facts.yaml", self.facts),
            ("rules.yaml", self.rules),
            ("acts.yaml", self.acts),
        ]
        return [name for name, data in core if data is None]

    def health_summary(self) -> dict[str, Any]:
        """Return a compact health signal for MCP payloads."""
        return {
            "has_facts": self.has_facts(),
            "has_rules": self.has_rules(),
            "has_acts": self.has_acts(),
            "has_map": self.has_map(),
            "has_expect": self.has_expect(),
            "missing_files": list(self.missing_files),
            "load_errors": list(self.load_errors),
        }

    def minimal_signal(self) -> dict[str, Any]:
        """Return the smallest useful project signal for onboarding payloads.

        Does not dump the full FRAME. Suitable for about/guidance-phase outputs.
        """
        facts = self.facts or {}
        identity = facts.get("identity") or {}
        goal = facts.get("goal") or {}

        rules = self.rules or {}
        lifecycle = rules.get("lifecycle") or {}

        return {
            "project_name": identity.get("name", ""),
            "project_version": identity.get("version", ""),
            "purpose": goal.get("purpose", ""),
            "enforce_verify_before_record": bool(
                lifecycle.get("enforce_verify_before_record", True)
            ),
            "frame_files_present": {
                "facts": self.has_facts(),
                "rules": self.has_rules(),
                "acts": self.has_acts(),
                "map": self.has_map(),
                "expect": self.has_expect(),
            },
        }

    def frame_file(self, name: str) -> dict[str, Any] | None:
        """Return a single FRAME file dict by canonical name (facts, rules, acts, map, expect)."""
        mapping = {
            "facts": self.facts,
            "rules": self.rules,
            "acts": self.acts,
            "map": self.map,
            "expect": self.expect,
        }
        return mapping.get(name)

    # --- future selectors (placeholders for v0.7+) ---

    def recent_acts(self, limit: int = 3) -> list[dict[str, Any]]:
        """Return the most recent N runs from acts.yaml."""
        acts = self.acts or {}
        runs = acts.get("runs") or []
        if not isinstance(runs, list):
            return []
        return runs[-limit:] if len(runs) >= limit else list(runs)

    def expect_summary(self) -> dict[str, Any]:
        """Return a compact summary of expect.yaml for prebuild signals."""
        expect = self.expect or {}
        runs = expect.get("runs") or []
        active = [r for r in runs if isinstance(r, dict) and r.get("status") == "active"]
        blocked = [r for r in runs if isinstance(r, dict) and r.get("status") == "blocked"]
        return {
            "total_runs": len(runs),
            "active_runs": len(active),
            "blocked_runs": len(blocked),
            "has_active": len(active) > 0,
        }
