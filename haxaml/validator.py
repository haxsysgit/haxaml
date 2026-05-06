"""FRAME model validation against schemas (facts/rules/acts/map/expect)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml
from jsonschema import Draft202012Validator

if TYPE_CHECKING:
    from haxaml.frame_model import FrameModel


@dataclass
class SemanticValidationResult:
    """Result of semantic_validate().

    blocking: hard errors — haxaml_validate should return ok=false for these.
    warnings: quality gaps — haxaml_doctor surfaces these; agents can still proceed.
    """
    blocking: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def is_clean(self) -> bool:
        return not self.blocking and not self.warnings

    def has_blocking(self) -> bool:
        return bool(self.blocking)


def semantic_validate(frame: "FrameModel") -> SemanticValidationResult:
    """Run semantic checks beyond JSON Schema shape validation.

    Blocking checks: structural gaps that prevent safe Haxaml operation.
    Advisory warnings: quality gaps that weaken FRAME but don't block execution.
    """
    blocking: list[str] = []
    warnings: list[str] = []

    # --- load errors are always blocking ---
    for err in frame.load_errors:
        blocking.append(f"FRAME load error: {err}")

    facts: dict[str, Any] = frame.facts or {}
    rules: dict[str, Any] = frame.rules or {}
    acts: dict[str, Any] = frame.acts or {}
    expect: dict[str, Any] = frame.expect or {}

    # --- blocking: required structural facts ---
    # Block only when the key is entirely absent — not when it exists but is
    # empty (that is valid for a freshly scaffolded project).
    identity = facts.get("identity")
    if identity is None:
        blocking.append("facts.identity section is absent — add identity.name and identity.version")
    else:
        if "name" not in (identity or {}):
            blocking.append("facts.identity.name key is absent")

    goal = facts.get("goal")
    if goal is None:
        blocking.append("facts.goal section is absent — add goal.purpose and goal.scope")
    else:
        if "purpose" not in (goal or {}):
            blocking.append("facts.goal.purpose key is absent")

    # Warn (not block) on empty scaffold values. A freshly scaffolded project should
    # still validate, but collaborators should see exactly which values remain placeholders.
    _identity = identity or {}
    _goal = goal or {}
    if "name" in _identity and not str(_identity.get("name") or "").strip():
        warnings.append("facts.identity.name is empty — fill in the project name")
    if "purpose" in _goal and not str(_goal.get("purpose") or "").strip():
        warnings.append("facts.goal.purpose is empty — fill in the project purpose")

    # --- blocking: corrupt/inconsistent lifecycle state ---
    _active_task_raw = acts.get("active_task")
    if isinstance(_active_task_raw, dict):
        _task_name = str(_active_task_raw.get("name") or "").strip().lower()
        active_task = None if _task_name in ("", "none", "null") else _task_name
    elif isinstance(_active_task_raw, str):
        _task_name = _active_task_raw.strip().lower()
        active_task = None if _task_name in ("", "none", "null") else _task_name
    else:
        active_task = None
    sessions = acts.get("sessions") or []
    if active_task and isinstance(sessions, list) and len(sessions) > 0:
        open_sessions = [
            s for s in sessions
            if isinstance(s, dict) and s.get("status") not in ("completed", "failed", "recorded")
        ]
        if not open_sessions:
            blocking.append(
                "acts.yaml has active_task set but no matching open session — "
                "lifecycle state is stale and may block verify/record"
            )

    if isinstance(expect, dict):
        expect_runs = expect.get("runs") or []
        acts_run_ids = {
            r.get("id") for r in (acts.get("runs") or [])
            if isinstance(r, dict) and r.get("id")
        }
        for run in expect_runs:
            if not isinstance(run, dict):
                continue
            if run.get("status") == "active" and run.get("id") and run["id"] not in acts_run_ids:
                blocking.append(
                    f"expect.yaml run '{run.get('id')}' is active but has no matching acts record"
                )

    # --- advisory: description and scope quality ---
    if not _identity.get("description"):
        warnings.append("facts.identity.description is missing — helps agents understand the project")

    if not _goal.get("scope"):
        warnings.append("facts.goal.scope is missing — agents may over-apply changes")

    if not _goal.get("out_of_scope"):
        warnings.append("facts.goal.out_of_scope is missing — agents may attempt out-of-scope work")

    # --- advisory: vague rules ---
    for key, value in rules.items():
        if isinstance(value, str) and len(value.strip().split()) <= 2:
            warnings.append(
                f"rules.{key} value is very short ('{value.strip()}') — "
                "consider a more descriptive rule"
            )

    # --- advisory: missing verification policy ---
    if not rules.get("verification") and not rules.get("verification_policy"):
        warnings.append(
            "rules.verification policy is absent — "
            "agents may not know how to verify before recording"
        )

    # --- advisory: map quality ---
    map_data: dict[str, Any] = frame.map or {}
    modules = map_data.get("modules") or []
    if isinstance(modules, list):
        for mod in modules:
            if not isinstance(mod, dict):
                continue
            name = mod.get("name", "<unnamed>")
            if not mod.get("owner"):
                warnings.append(f"map module '{name}' has no owner defined")
            if not mod.get("paths") and not mod.get("path"):
                warnings.append(f"map module '{name}' has no paths defined")

    # --- advisory: outstanding blocking unresolved items ---
    unresolved = facts.get("unresolved") or []
    if isinstance(unresolved, list):
        for item in unresolved:
            if isinstance(item, dict) and item.get("blocking"):
                warnings.append(
                    f"facts.unresolved blocking item outstanding: "
                    f"{item.get('item', '?')} — {item.get('reason', 'no reason given')}"
                )

    return SemanticValidationResult(blocking=blocking, warnings=warnings)


SCHEMA_DIR = Path(__file__).parent / "schemas"


def load_yaml(path: str) -> dict:
    """Load a YAML file and return its contents."""
    with open(path, "r") as f:
        return yaml.safe_load(f) or {}


def load_schema(schema_name: str) -> dict:
    """Load a schema YAML file from the schemas directory."""
    schema_path = SCHEMA_DIR / schema_name
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema not found: {schema_path}")
    return load_yaml(str(schema_path))


def validate_facts(facts_path: str) -> list[str]:
    """Validate facts.yaml against the facts schema.

    Returns a list of error messages. Empty list = valid.
    """
    schema = load_schema("facts.schema.yaml")
    data = load_yaml(facts_path)
    validator = Draft202012Validator(schema)
    errors = []
    for error in sorted(validator.iter_errors(data), key=lambda e: list(e.path)):
        path = ".".join(str(p) for p in error.absolute_path) or "(root)"
        errors.append(f"[{path}] {error.message}")
    return errors



def validate_acts(acts_path: str) -> list[str]:
    """Validate acts.yaml against the acts schema.

    Returns a list of error messages. Empty list = valid.
    """
    schema = load_schema("acts.schema.yaml")
    data = load_yaml(acts_path)
    validator = Draft202012Validator(schema)
    errors = []
    for error in sorted(validator.iter_errors(data), key=lambda e: list(e.path)):
        path = ".".join(str(p) for p in error.absolute_path) or "(root)"
        errors.append(f"[{path}] {error.message}")
    return errors



def validate_rules(rules_path: str) -> list[str]:
    """Validate rules.yaml against the rules schema.

    Returns a list of error messages. Empty list = valid.
    """
    schema = load_schema("rules.schema.yaml")
    data = load_yaml(rules_path)
    validator = Draft202012Validator(schema)
    errors = []
    for error in sorted(validator.iter_errors(data), key=lambda e: list(e.path)):
        path = ".".join(str(p) for p in error.absolute_path) or "(root)"
        errors.append(f"[{path}] {error.message}")
    return errors


def validate_expect(expect_path: str) -> list[str]:
    """Validate expect.yaml against the expect schema.

    Returns a list of error messages. Empty list = valid.
    """
    schema = load_schema("expect.schema.yaml")
    data = load_yaml(expect_path)
    validator = Draft202012Validator(schema)
    errors = []
    for error in sorted(validator.iter_errors(data), key=lambda e: list(e.path)):
        path = ".".join(str(p) for p in error.absolute_path) or "(root)"
        errors.append(f"[{path}] {error.message}")
    return errors



def validate_map(map_path: str) -> list[str]:
    """Validate map.yaml against the map schema.

    Returns a list of error messages. Empty list = valid.
    """
    schema = load_schema("map.schema.yaml")
    data = load_yaml(map_path)
    validator = Draft202012Validator(schema)
    errors = []
    for error in sorted(validator.iter_errors(data), key=lambda e: list(e.path)):
        path = ".".join(str(p) for p in error.absolute_path) or "(root)"
        errors.append(f"[{path}] {error.message}")
    return errors


def detect_missing_facts_fields(facts_path: str) -> list[str]:
    """Detect fields that are absent but would improve facts completeness.

    Goes beyond schema required fields to check for recommended fields.
    """
    facts = load_yaml(facts_path)
    missing = []

    recommended = {
        "identity.description": facts.get("identity", {}).get("description"),
        "goal.scope": facts.get("goal", {}).get("scope"),
        "goal.out_of_scope": facts.get("goal", {}).get("out_of_scope"),
        "tools": facts.get("tools"),
        "services": facts.get("services"),
        "roles": facts.get("roles"),
        "features": facts.get("features"),
    }

    for field, value in recommended.items():
        if value is None:
            missing.append(f"Recommended field missing: {field}")
        elif isinstance(value, (list, dict)) and len(value) == 0:
            missing.append(f"Recommended field empty: {field}")

    unresolved = facts.get("unresolved", [])
    blocking = [u for u in unresolved if u.get("blocking", False)]
    if blocking:
        for item in blocking:
            missing.append(f"BLOCKING unresolved: {item['item']} — {item.get('reason', 'no reason given')}")

    return missing
