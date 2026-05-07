# MCP: Haxaml Operator Guide

Haxaml is MCP-first and agent-first. The server gives the agent a deterministic governed workflow before coding starts.

Official MCP architecture reference:
https://modelcontextprotocol.io/docs/learn/architecture

## Core Idea

Haxaml uses tools, not prompts, as the main governance surface because tools can:

- enforce lifecycle order
- return machine-checkable error codes
- carry structured readiness and verification state

Prompt files still matter, but they are adapters. The hard governance logic lives in the MCP tool contracts.

## Runtime Shape

- Host: Codex CLI, Claude Code, Cursor, Windsurf, or another MCP-compatible client
- MCP server: `haxaml-mcp` via `haxaml.mcp_server:main`
- Project state: repository plus `.haxaml/*.yaml`

Package split in `0.6.7`:

- `haxaml` - core governance engine and CLI
- `haxaml-mcp` - MCP runtime/launcher package
- `haxaml-ui` - local dashboard package

Canonical FRAME files:

- `.haxaml/facts.yaml`
- `.haxaml/rules.yaml`
- `.haxaml/acts.yaml`
- `.haxaml/expect.yaml`
- `.haxaml/map.yaml`

## Response Envelope

Every tool returns:

- `ok`
- `tool`
- `data`
- `warnings`
- `error`

Every tool accepts `detail="short"` or `detail="full"`. Short mode is the default and should stay the normal path.

## Supported Governed Flow

Use this order for project work:

1. `haxaml_about(project_dir='.')`
2. `haxaml_guidance(task=..., project_dir='.')`
3. `haxaml_prebuild(task=..., project_dir='.')`
4. `haxaml_context_pack(task=..., session_id=..., pack='balanced', include_state=True, project_dir='.')`
5. `haxaml_context_fetch(task=..., query=..., session_id=..., project_dir='.')` when more governed memory is needed
6. `haxaml_session_verify(task=..., session_id=..., inspected_context=[...], changed_files=[...], summary=..., project_dir='.')`
7. `haxaml_session_record(task=..., result='success'|'partial'|'failed', session_id=..., changes=..., decisions=..., risks=..., project_dir='.')`
8. `haxaml_expect_sync(project_dir='.', run=<optional>)`

Public rule:

- `haxaml_prebuild` is the only public governed session-entry tool.
- Out-of-order governed calls fail with `error.code="lifecycle_contract_violation"`.

## Operating Modes

- Governed mode: project work. Use the lifecycle above and allow Haxaml to record evidence.
- Utility mode: side tasks or unrelated requests. Do not run governed lifecycle tools and do not edit `.haxaml/*`.
- Resume rule: when returning from utility work, restart with `haxaml_guidance` then `haxaml_prebuild`.

## Practical Signals

What to read from each step:

- `about`: onboarding message, lean workflow, next step
- `guidance`: execution mode, task type, risk level, required questions, recommended pack
- `prebuild`: readiness status, session id, progress summary, required questions
- `context_pack`: tokens, included sections, omitted sections, window usage
- `context_fetch`: governed follow-up hits, candidate file references, archive availability
- `session_verify`: verdict plus verification evidence
- `session_record`: recorded run id and whether `expect_sync` is now required
- `expect_sync`: runbook update and lifecycle drift clearance

## Context Pack Discipline

- Use `minimal`, `balanced`, or `full`.
- `balanced` should remain the default for most governed work.
- Repeat `haxaml_context_pack` only when scope changed or context went stale.
- Repeated calls require `refresh_reason`.
- Repeated calls now report:
  - `refresh_mode`
  - `refresh_summary`
  - `changed_sections`
  - `unchanged_sections`
  - `token_delta`
- Use `haxaml_context_fetch` for follow-up governed lookup instead of repeating `context_pack` just to go hunting for more memory.

Short mode intentionally returns compact execution facts first, not the full context body. Use `detail="full"` only when a client explicitly needs the structured pack object.

Acts history stays tiered:

- hot current state remains in `.haxaml/acts.yaml`
- older runs, sessions, and verifications move to `.haxaml/archive/acts-history.yaml`
- archive history is searched only when the agent asks for more governed context

Long-lived runtimes now also share an in-process FRAME/archive snapshot cache so repeated governed reads do not reparse every unchanged file.

## Visibility And Repair Tools

These are optional diagnostics, not part of the happy-path governed sequence:

- `haxaml_health`
- `haxaml_doctor`
- `haxaml_needs`
- `haxaml_reconcile`
- `haxaml_state_show`

Use them when:

- readiness is blocked
- verification discipline is unclear
- derivation conflicts appear
- state drift needs explanation

## Common Failures

1. `about_required`
- Call `haxaml_about` once in the active MCP session, then continue.

2. `lifecycle_contract_violation`
- Run the tool named in the response hint before retrying the blocked call.

3. `utility_mode_task`
- This is a side task. Do not use governed lifecycle tools for it.

4. `verification_required`
- Run `haxaml_session_verify` before recording `success` or `partial`.

5. `expect_sync_required` or `lifecycle_drift`
- Call `haxaml_expect_sync` before continuing governed work.

6. `derivation_conflicts`
- Run `haxaml_reconcile`, fix the reported conflicts, then retry.

7. `context_pack_refresh_reason_required`
- The session already consumed one context pack. Explain what changed before repeating it.

## Client Config

Project-local config is preferred.

### Claude Code

```json
{
  "mcpServers": {
    "haxaml": {
      "command": "uvx",
      "args": ["haxaml-mcp"]
    }
  }
}
```

### Codex CLI

```toml
[mcp_servers.haxaml]
command = "haxaml-mcp"
```

### Generic JSON

```json
{
  "mcpServers": {
    "haxaml": {
      "type": "stdio",
      "command": "uvx",
      "args": ["haxaml-mcp"]
    }
  }
}
```

For user-wide configs outside the repo, set `HAXAML_PROJECT_DIR` to the project root.
