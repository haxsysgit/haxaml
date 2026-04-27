"""FRAME model validation against schemas (facts/rules/acts/map/expect)."""

from pathlib import Path

import yaml
from jsonschema import Draft202012Validator


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
