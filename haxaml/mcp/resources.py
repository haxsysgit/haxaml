"""MCP resources for Haxaml."""

from haxaml.mcp.base import *


# ─── Resources ───────────────────────────────────────────────────────────────


@mcp_app.resource("haxaml://frame/facts")
def resource_facts() -> str:
    """Current project facts (FRAME: F)."""
    path = resolve_frame_file(_project(), "facts.yaml")
    if not path:
        return "# facts.yaml not found"
    return path.read_text(encoding="utf-8")


@mcp_app.resource("haxaml://frame/rules")
def resource_rules() -> str:
    """Current project rules (FRAME: R)."""
    path = resolve_frame_file(_project(), "rules.yaml")
    if not path:
        return "# rules.yaml not found"
    return path.read_text(encoding="utf-8")


@mcp_app.resource("haxaml://frame/acts")
def resource_acts() -> str:
    """Current project diary (FRAME: A)."""
    path = resolve_frame_file(_project(), "acts.yaml")
    if not path:
        return "# acts.yaml not found"
    return path.read_text(encoding="utf-8")


@mcp_app.resource("haxaml://frame/expect")
def resource_expect() -> str:
    """Current project runbook (FRAME: E)."""
    path = resolve_frame_file(_project(), "expect.yaml")
    if not path:
        return "# expect.yaml not found"
    return path.read_text(encoding="utf-8")


@mcp_app.resource("haxaml://frame/map")
def resource_map() -> str:
    """Current module map (FRAME: M) — required when complexity policy says so."""
    path = resolve_frame_file(_project(), "map.yaml")
    if not path:
        assessment = evaluate_map_complexity(_project())
        state = "required" if assessment.required else "optional"
        return f"# map.yaml not found — {state} by current complexity policy"
    return path.read_text(encoding="utf-8")

