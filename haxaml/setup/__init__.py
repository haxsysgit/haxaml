"""Setup and onboarding helpers for Haxaml 0.7.x."""

from haxaml.setup.cli import (
    doctor_plan,
    execute_setup,
    print_plan,
    setup_plan,
)
from haxaml.setup.registry import SUPPORTED_TARGET_IDS, get_target, list_targets

__all__ = [
    "SUPPORTED_TARGET_IDS",
    "doctor_plan",
    "execute_setup",
    "get_target",
    "list_targets",
    "print_plan",
    "setup_plan",
]
