"""Setup and onboarding helpers for Haxaml 0.7.x."""

from haxaml.setup.cli import (
    doctor_plan,
    execute_setup,
    print_plan,
    setup_plan,
    workflow_check_plan,
)
from haxaml.setup.registry import SUPPORTED_TARGET_IDS, get_target, list_targets
from haxaml.setup.service import (
    apply_setup,
    doctor_data,
    plan_setup,
    print_data,
    setup_data,
    setup_message,
    workflow_check_data,
)
from haxaml.setup.workflow import WORKFLOW_TARGET_IDS, get_workflow_target, list_workflow_targets

__all__ = [
    "SUPPORTED_TARGET_IDS",
    "WORKFLOW_TARGET_IDS",
    "apply_setup",
    "doctor_data",
    "doctor_plan",
    "execute_setup",
    "get_target",
    "get_workflow_target",
    "list_targets",
    "list_workflow_targets",
    "plan_setup",
    "print_data",
    "print_plan",
    "setup_data",
    "setup_message",
    "setup_plan",
    "workflow_check_data",
    "workflow_check_plan",
]
