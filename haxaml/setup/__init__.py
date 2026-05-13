"""Setup and onboarding helpers for Haxaml 0.7.x."""

from haxaml.setup.cli import (
    doctor_plan,
    execute_setup,
    print_plan,
    setup_plan,
)
from haxaml.setup.registry import SUPPORTED_TARGET_IDS, get_target, list_targets
from haxaml.setup.service import apply_setup, doctor_data, plan_setup, print_data, setup_data, setup_message

__all__ = [
    "SUPPORTED_TARGET_IDS",
    "apply_setup",
    "doctor_data",
    "doctor_plan",
    "execute_setup",
    "get_target",
    "list_targets",
    "plan_setup",
    "print_data",
    "print_plan",
    "setup_data",
    "setup_message",
    "setup_plan",
]
