"""Entrypoint for the Haxaml MCP server."""

import shutil

from haxaml.mcp.base import mcp_app
from haxaml.mcp.tools_benchmark import haxaml_benchmark
from haxaml.mcp.tools_frame import (
    haxaml_doctor,
    haxaml_health,
    haxaml_init,
    haxaml_validate,
)
from haxaml.mcp.tools_lifecycle import (
    haxaml_about,
    haxaml_context_fetch,
    haxaml_context_pack,
    haxaml_expect_sync,
    haxaml_guidance,
    haxaml_session_record,
    haxaml_session_verify,
)
from haxaml.mcp.tools_ops import (
    haxaml_adopt,
    haxaml_adopt_plan,
    haxaml_export,
    haxaml_impact,
    haxaml_mcp_bootstrap,
    haxaml_needs,
    haxaml_reconcile,
    haxaml_state_compact,
    haxaml_state_show,
    haxaml_upgrade,
)
from haxaml.mcp.tools_prebuild import haxaml_prebuild
from haxaml.mcp.resources import (
    resource_facts,
    resource_rules,
    resource_acts,
    resource_expect,
    resource_map,
)


__all__ = [
    "mcp_app",
    "haxaml_prebuild",
    "haxaml_about",
    "haxaml_init",
    "haxaml_validate",
    "haxaml_health",
    "haxaml_doctor",
    "haxaml_guidance",
    "haxaml_context_pack",
    "haxaml_context_fetch",
    "haxaml_session_verify",
    "haxaml_session_record",
    "haxaml_expect_sync",
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
    "main",
]


def main():
    """Run the Haxaml MCP server (stdio transport)."""
    mcp_app.run()


if __name__ == "__main__":
    main()
