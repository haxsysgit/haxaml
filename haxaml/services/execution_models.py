"""Small data models shared by execution services.

These dataclasses are intentionally lightweight. They are the stable payloads
used by the ``haxaml.runner`` facade and by the tests that
exercise the execution flow.
"""

from dataclasses import dataclass, field


@dataclass
class RunResult:
    """Outcome of one recorded execution run."""

    run_id: str = ""
    task: str = ""
    result: str = "pending"
    changes: str = ""
    decisions: str = ""
    risks: str = ""
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    token_count: int = 0


@dataclass
class PreflightResult:
    """Validation status returned before a governed run can start."""

    ready: bool = True
    facts_valid: bool = False
    acts_valid: bool = False
    facts_complete: bool = False
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    context_tokens: int = 0
