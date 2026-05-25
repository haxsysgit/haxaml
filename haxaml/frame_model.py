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

from haxaml.runtime_cache import runtime_cache


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
        bundle = runtime_cache().get_frame_bundle(project_dir)
        project = Path(bundle["project_dir"]).resolve()
        data = bundle["data"]
        load_errors = list(bundle["load_errors"])
        missing_files = list(bundle["missing_files"])

        return cls(
            facts=data.get("facts"),
            rules=data.get("rules"),
            acts=data.get("acts"),
            map=data.get("map"),
            expect=data.get("expect"),
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
            "frontmatter": self.frontmatter_summary(),
        }

    def frontmatter(self, name: str) -> dict[str, Any]:
        """Return the shared FRAME frontmatter for one file."""
        data = self.frame_file(name) or {}
        frame = data.get("frame") if isinstance(data, dict) else None
        return frame if isinstance(frame, dict) else {}

    def frontmatter_summary(self) -> dict[str, dict[str, Any]]:
        """Return just the shared FRAME headers across all loaded files.

        This is the 0.8.0 handshake layer: tools can inspect roles, versions,
        and status without loading or trusting the full body.
        """
        summary: dict[str, dict[str, Any]] = {}
        for name in ("facts", "rules", "acts", "map", "expect"):
            frame = self.frontmatter(name)
            if frame:
                summary[name] = {
                    "file": frame.get("file", ""),
                    "schema_version": frame.get("schema_version", ""),
                    "role": frame.get("role", ""),
                    "status": frame.get("status", ""),
                    "last_reviewed": frame.get("last_reviewed"),
                }
        return summary

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
            "frontmatter": self.frontmatter_summary(),
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
        runs = expect.get("runbook") or []
        active = [r for r in runs if isinstance(r, dict) and r.get("status") == "active"]
        blocked = [r for r in runs if isinstance(r, dict) and r.get("status") == "blocked"]
        return {
            "total_runs": len(runs),
            "active_runs": len(active),
            "blocked_runs": len(blocked),
            "has_active": len(active) > 0,
        }
