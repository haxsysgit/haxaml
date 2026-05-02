"""Compatibility re-export for MCP tool modules."""

from haxaml.mcp.tools_frame import *
from haxaml.mcp.tools_lifecycle import *
from haxaml.mcp.tools_ops import *
from haxaml.mcp.tools_benchmark import *
from haxaml.mcp.tools_prebuild import *

__all__ = [
    "haxaml_prebuild",
    "haxaml_about",
    "haxaml_guidance",
    "haxaml_session_start",
    "haxaml_session_plan",
    "haxaml_context_pack",
    "haxaml_session_verify",
    "haxaml_session_record",
    "haxaml_expect_sync",
    "haxaml_run",  # deprecated
    "haxaml_done",  # deprecated
    "haxaml_init",
    "haxaml_validate",
    "haxaml_context",
    "haxaml_health",
    "haxaml_doctor",
    "haxaml_export",
    "haxaml_upgrade",
    "haxaml_mcp_bootstrap",
    "haxaml_adopt_plan",
    "haxaml_reconcile",
    "haxaml_adopt",
    "haxaml_needs",
    "haxaml_impact",
    "haxaml_state_show",
    "haxaml_state_compact",
    "haxaml_benchmark",
]
