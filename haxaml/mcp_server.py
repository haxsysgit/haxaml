"""Compatibility entrypoint for the Haxaml MCP server.

This module preserves the historical import path (`haxaml.mcp_server`) while
implementation details live under `haxaml.mcp` submodules.
"""

import shutil  # backward-compatible patch target (tests/integrations)

from haxaml.mcp.base import mcp_app
from haxaml.mcp.tools import (
    haxaml_about,
    haxaml_init,
    haxaml_validate,
    haxaml_context,
    haxaml_health,
    haxaml_doctor,
    haxaml_guidance,
    haxaml_session_start,
    haxaml_session_plan,
    haxaml_context_pack,
    haxaml_session_verify,
    haxaml_session_record,
    haxaml_expect_sync,
    haxaml_run,
    haxaml_done,
    haxaml_export,
    haxaml_upgrade,
    haxaml_mcp_bootstrap,
    haxaml_adopt_plan,
    haxaml_reconcile,
    haxaml_adopt,
    haxaml_needs,
    haxaml_impact,
    haxaml_state_show,
    haxaml_state_compact,
    haxaml_benchmark,
)
from haxaml.mcp.resources import (
    resource_facts,
    resource_rules,
    resource_acts,
    resource_expect,
    resource_map,
    resource_context,
)


__all__ = [
    "mcp_app",
    "haxaml_about",
    "haxaml_init",
    "haxaml_validate",
    "haxaml_context",
    "haxaml_health",
    "haxaml_doctor",
    "haxaml_guidance",
    "haxaml_session_start",
    "haxaml_session_plan",
    "haxaml_context_pack",
    "haxaml_session_verify",
    "haxaml_session_record",
    "haxaml_expect_sync",
    "haxaml_run",
    "haxaml_done",
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
    "resource_facts",
    "resource_rules",
    "resource_acts",
    "resource_expect",
    "resource_map",
    "resource_context",
    "main",
]


def main():
    """Run the Haxaml MCP server (stdio transport)."""
    mcp_app.run()


if __name__ == "__main__":
    main()
