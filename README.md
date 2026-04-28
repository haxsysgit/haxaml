# Haxaml

[![PyPI version](https://img.shields.io/pypi/v/haxaml.svg)](https://pypi.org/project/haxaml/)

Haxaml is an LLM-first governance layer for coding agents.

It gives agents one deterministic source of truth called **FRAME** and a strict MCP tool workflow so project context does not drift across sessions or tools.

## What Haxaml Is For

Use Haxaml when an AI agent is doing implementation work and you want:

- explicit project facts and rules
- deterministic context handoff
- verify/record gates before claiming success
- stable MCP-native workflows instead of ad-hoc prompting

## 5-Minute Start

1. Install:

```bash
pip install haxaml
# or
uv tool install haxaml
uv tool install haxaml-mcp
```

2. Initialize FRAME:

```bash
haxaml init
haxaml validate
```

3. Configure MCP client:

```json
{
  "mcpServers": {
    "haxaml": {
      "command": "uvx",
      "args": ["haxaml-mcp"],
      "env": {
        "HAXAML_PROJECT_DIR": "/path/to/project"
      }
    }
  }
}
```

4. For existing projects:

```bash
haxaml adopt-plan --dir .
haxaml reconcile --dir .
haxaml validate --dir .
```

For the practical lifecycle flow and failure recovery path, use `MCP.md` sections: `Quick Start MCP Flow`, `Demo Walkthrough`, `Top 5 Troubleshooting`, and `Detail Mode Quick Examples`.

## Startup Prompt For Agent Files

Paste this at the top of your native agent file (`AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `.github/copilot-instructions.md`, etc.):

```md
You are working in a repository governed by Haxaml.

Haxaml is the project governance source of truth for LLM agents.
Use Haxaml MCP tools directly instead of ad-hoc workflow decisions.

Operational contract:
1. Start with haxaml_guidance(task=...).
2. Open a governed run with haxaml_session_start(task=..., description=...).
3. Generate execution steps with haxaml_session_plan(session_id=...).
4. Pull only task-relevant context with haxaml_context_pack(task=...).
5. Before recording success/partial, run haxaml_session_verify(...).
6. Record outcomes using haxaml_session_record(...).
7. If boundary or derivation risk appears, run haxaml_reconcile(project_dir='.') and resolve conflicts first.

Adoption rule:
- For existing repos, run haxaml_adopt_plan(project_dir='.') first.
- Do not overwrite existing governance files unless explicitly requested.

Safety rule:
- Do not claim success if validation/reconcile gates are unresolved.
```

## Core FRAME Files

- `.haxaml/facts.yaml` - project truth
- `.haxaml/rules.yaml` - agent operating rules
- `.haxaml/acts.yaml` - execution diary and decisions
- `.haxaml/expect.yaml` - run plan and milestones
- `.haxaml/map.yaml` - optional module ownership and impact map

## Docs

- [MCP.md](https://github.com/haxsysgit/haxaml/blob/main/MCP.md) - MCP-first operator guide with bootstrap-aligned config examples, Quick Start MCP Flow, demo walkthroughs, bad/good usage pairs, and troubleshooting
- [ADVANCED.md](https://github.com/haxsysgit/haxaml/blob/main/ADVANCED.md) - deeper command and export behavior
- [LONGTERM.md](https://github.com/haxsysgit/haxaml/blob/main/LONGTERM.md) - roadmap direction
- `CHANGELOG.md` - release notes
