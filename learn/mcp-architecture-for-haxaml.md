# MCP Architecture For Haxaml (Plain English)

This file explains MCP using simple terms, then maps each part to Haxaml.

Official MCP architecture reference:
https://modelcontextprotocol.io/docs/learn/architecture

## The 4 Parts In Simple Terms

1. Host app  
The place you run the agent (CLI, IDE, chat app).

2. MCP client  
The bridge inside that host that can connect to MCP servers and relay tool calls.

3. MCP server  
A separate process that exposes tools/resources/prompts over MCP.

4. Data source / local state  
Files, APIs, repos, databases, or anything the server reads/writes.

## How That Maps To Haxaml

1. Host app  
Examples: Codex CLI, Windsurf, Cursor, Claude Code.

2. MCP client  
The host's MCP integration that discovers `haxaml` tools and calls them.

3. MCP server  
`haxaml-mcp` (entrypoint: `haxaml.mcp_server:main`) exposing tools like:
- `haxaml_about`
- `haxaml_guidance`
- `haxaml_session_start`
- `haxaml_session_plan`
- `haxaml_context_pack`
- `haxaml_session_verify`
- `haxaml_session_record`
- `haxaml_expect_sync`
- `haxaml_validate`

4. Data source / local state  
Your project plus `.haxaml/*` FRAME files.

## What MCP Can And Cannot Force

MCP gives agents a standard way to call tools. It does not guarantee a host or model will always choose to call them.

So Haxaml must enforce rules at the server level:
- out-of-order governed calls fail (`lifecycle_contract_violation`)
- recording without verification fails
- validate fails when lifecycle sync is pending (`lifecycle_drift`)
- validate fails when code changed without governed evidence (`governance_evidence_missing`)

That is the core design: if an agent skips contract steps, Haxaml returns hard errors instead of silently accepting drift.

## Practical Cross-Client Checklist

1. Confirm MCP server is visible in the host (`/mcp show` or equivalent).
2. Confirm server command is `uvx haxaml-mcp` (or installed `haxaml-mcp`) and `HAXAML_PROJECT_DIR` is set correctly.
3. Start governed work with `haxaml_about`.
4. Follow lifecycle order exactly.
5. Treat contract errors as blockers, not warnings.
6. Run `haxaml_validate` before claiming completion.
