# Haxaml Skill Setup Plan

## Goal

Haxaml should ship with a built-in Skill layer and setup system.

The Haxaml Skill is mandatory as part of the product experience.

Haxaml remains MCP-first as the runtime engine, but the Skill layer is required for optimal usage because Haxaml is designed to be extremely token and context efficient.

The Skill teaches agents how to use Haxaml properly:

- avoid context dumps
- use short tool outputs
- pull one task-scoped context pack
- avoid reading every `.haxaml/*` file manually
- use prebuild before implementation
- verify with evidence before record
- record only useful project outcomes
- avoid polluting FRAME state with side tasks

The product stack should be:

FRAME       = project model
CLI         = human setup and inspection
MCP         = runtime engine for agents
Skill       = mandatory token-efficient operating guide
Exports     = fallback adapters for agents without native Skill support

## Key Product Position

Haxaml is not only an MCP server.

Haxaml is a complete agent workflow package:

1. It creates FRAME project state.
2. It exposes MCP tools for runtime governance.
3. It installs the Haxaml Skill or equivalent instructions for supported agents.
4. It helps agents use Haxaml without wasting tokens.
5. It keeps the public workflow stable across providers.

Core promise:

Haxaml does not make the agent intelligent.
It gives the agent a project workflow it can actually follow.

## Why Skill Is Mandatory

The Haxaml Skill should be built in because token efficiency is not an extra feature.

Token efficiency is central to the product.

Without the Skill, an agent may still connect to the MCP server, but it may use Haxaml badly:

- calling too many tools
- requesting full payloads too often
- reading all FRAME files manually
- pasting large project state into the chat
- refreshing context without a reason
- recording noisy session history
- treating Haxaml like a context dump

That would weaken the whole point of Haxaml.

The Skill makes the agent follow the intended operating discipline.

So the setup rule should be:

If the agent supports native Skills, install a Haxaml Skill.
If the agent does not support native Skills, install the closest equivalent:
rules, guidelines, custom instructions, memory, or AGENTS.md style adapters.

## Main Setup Command

The main public onboarding command should be:

haxaml setup

This command should become the one-stop setup flow.

It should:

1. Detect the project root.
2. Create or validate `.haxaml/` FRAME files.
3. Generate MCP setup guidance.
4. Detect supported AI agents and editors.
5. Install the Haxaml Skill or equivalent instruction adapter.
6. Print a setup summary.
7. Print the next steps for the user.

## Setup Scopes

Haxaml setup should support two scopes.

### Project Scope

Project scope installs Haxaml support inside the current repository.

This should be the default.

Project scope should create:

.haxaml/
  facts.yaml
  rules.yaml
  acts.yaml
  map.yaml
  expect.yaml
  skills/
    haxaml/
      SKILL.md

It should also create target-specific adapters where possible.

Examples:

Codex:
  .agents/skills/haxaml/SKILL.md
  or project skill target supported by Codex

Claude Code:
  .claude/skills/haxaml/SKILL.md
  or project plugin/skill location if supported

OpenCode:
  .opencode/skills/haxaml/SKILL.md

Cursor:
  .cursor/rules/haxaml.mdc

Windsurf:
  .windsurf/rules/haxaml.md
  or Windsurf workflow/rules equivalent

Copilot:
  .github/copilot-instructions.md
  .github/instructions/haxaml.instructions.md

Gemini CLI:
  GEMINI.md
  or .gemini/system.md when that mode is enabled

Cline:
  .clinerules/haxaml.md
  or project rules equivalent

Roo Code:
  .roo/rules/haxaml.md
  or mode-specific project instructions

Continue:
  .continue/rules/haxaml.md

Junie:
  AGENTS.md
  .junie/AGENTS.md
  .junie/guidelines.md where supported

Zed:
  project rule adapter where supported
  AGENTS.md or CLAUDE.md fallback where supported

Aider:
  CONVENTIONS.md
  or generated Haxaml conventions file to read into sessions

### User Scope

User scope installs Haxaml support globally where the target agent supports it.

User-wide setup should be useful for the user's personal machine.

Examples:

Codex:
  user skills directory where Codex discovers Skills

Claude Code:
  user skills directory where Claude Code discovers Skills

OpenCode:
  global OpenCode skills directory

Cursor:
  user rules instructions where supported

Windsurf:
  global rules or memories where supported

Copilot:
  personal custom instructions are usually configured through GitHub or IDE UI, so Haxaml should print guidance instead of silently editing unknown settings

Roo Code:
  global custom instructions where supported

Zed:
  rules library guidance or installable local rule if path is discoverable

For targets where user-wide file paths are not stable or not safely writable, Haxaml should not guess blindly.

It should print:

- detected target
- recommended setup path
- generated content
- manual next step

## Detection Strategy

`haxaml setup` should detect available targets by checking common files, directories, and installed commands.

Detection examples:

Codex:
  detect Codex config directory
  detect Codex CLI command if available
  detect existing skills directory

Claude Code:
  detect Claude config directory
  detect `.claude/`
  detect Claude Code command if available

Cursor:
  detect `.cursor/`
  detect Cursor installation if possible

Windsurf:
  detect `.windsurf/`
  detect Windsurf installation if possible

Copilot:
  detect `.github/`
  detect VS Code workspace
  detect existing copilot instruction files

Gemini CLI:
  detect `GEMINI.md`
  detect `.gemini/`
  detect Gemini CLI command if available

Cline:
  detect `.clinerules`
  detect VS Code extension workspace files where possible

Roo Code:
  detect `.roo/`
  detect Roo project rules where possible

Continue:
  detect `.continue/`
  detect `.continue/rules/`

Junie:
  detect `.junie/`
  detect `AGENTS.md`

OpenCode:
  detect `.opencode/`
  detect `.opencode/skills/`

Zed:
  detect `.zed/`
  detect project-level AI rules where possible

Aider:
  detect `.aider.conf.yml`
  detect `CONVENTIONS.md`

## Target List For First Built-In Support

Haxaml should support at least these targets first:

1. Codex
2. Claude Code
3. Cursor
4. Windsurf
5. GitHub Copilot
6. Gemini CLI
7. Cline
8. Roo Code
9. OpenCode
10. Continue

Nice-to-have later:

11. Junie
12. Zed
13. Aider

## Target Behavior

### 1. Codex

Type:
  native Skill target

Install strategy:
  install Haxaml Skill as `SKILL.md`

Project output:
  .agents/skills/haxaml/SKILL.md
  or configured Codex project skill path

User output:
  Codex user skill path if safely detected
  otherwise print generated Skill content and setup guidance

Notes:
  Codex should be one of the primary Haxaml Skill targets.

### 2. Claude Code

Type:
  native Skill target

Install strategy:
  install Haxaml Skill as `SKILL.md`

Project output:
  .claude/skills/haxaml/SKILL.md
  or Claude Code project skill/plugin equivalent

User output:
  Claude user skill path if safely detected
  otherwise print generated Skill content and setup guidance

Notes:
  Claude Code should be one of the primary Haxaml Skill targets.

### 3. OpenCode

Type:
  native Skill target

Install strategy:
  install Haxaml Skill as `SKILL.md`

Project output:
  .opencode/skills/haxaml/SKILL.md

User output:
  OpenCode global skills path if safely detected

Notes:
  OpenCode has a clear project skill pattern, so it should be easy to support.

### 4. Cursor

Type:
  rules adapter target

Install strategy:
  generate Cursor project rule

Project output:
  .cursor/rules/haxaml.mdc

User output:
  print user rules guidance
  do not silently modify unknown user settings unless path is explicit

Adapter content should include:
  Haxaml lifecycle
  MCP tool mapping
  token policy
  prebuild discipline
  verify before record

### 5. Windsurf

Type:
  rules/workflow adapter target

Install strategy:
  generate Windsurf rules or workflow instructions

Project output:
  .windsurf/rules/haxaml.md
  or closest supported Windsurf project rule file

User output:
  print Windsurf customization guidance if no stable file path is detected

Adapter content should include:
  Haxaml lifecycle
  token discipline
  use MCP tools only when needed
  one context pack per governed task

### 6. GitHub Copilot

Type:
  custom instructions adapter target

Install strategy:
  generate repository custom instructions

Project output:
  .github/copilot-instructions.md
  .github/instructions/haxaml.instructions.md

User output:
  print personal custom instructions guidance

Notes:
  Copilot should be treated as an adapter target unless native Skills support is clearly available in the user's environment.

### 7. Gemini CLI

Type:
  GEMINI.md adapter target

Install strategy:
  generate Gemini instruction file

Project output:
  GEMINI.md
  or .gemini/system.md when enabled by the user's Gemini CLI configuration

User output:
  print guidance for global or custom Gemini instruction setup

Adapter content should include:
  use Haxaml MCP when available
  avoid full FRAME dumps
  call context pack once
  prebuild before build

### 8. Cline

Type:
  rules adapter target

Install strategy:
  generate project rules

Project output:
  .clinerules/haxaml.md
  or supported Cline project rules format

User output:
  print custom instructions guidance

Adapter content should include:
  Haxaml workflow
  MCP mapping
  token rules
  utility mode handling

### 9. Roo Code

Type:
  custom instructions/rules adapter target

Install strategy:
  generate project rules

Project output:
  .roo/rules/haxaml.md
  or supported Roo mode-specific instruction file

User output:
  print global custom instructions guidance

Adapter content should include:
  Haxaml workflow
  prebuild mode
  token budget policy
  verification policy

### 10. Continue

Type:
  rules adapter target

Install strategy:
  generate Continue rule file

Project output:
  .continue/rules/haxaml.md

User output:
  print guidance for global Continue config if supported

Adapter content should include:
  lifecycle
  token discipline
  verify before record
  use MCP tools when connected

## Setup Modes

`haxaml setup` should support these modes internally:

### Auto Mode

Auto mode detects the environment and installs what it safely can.

Behavior:
  create FRAME files
  create Haxaml Skill bundle
  detect agents
  install project adapters
  print manual steps for unsafe or unknown paths

### Project Mode

Project mode installs project-local setup.

Behavior:
  create `.haxaml/`
  create project-local Skill
  create project-local adapter files
  avoid global writes

### User Mode

User mode installs user-wide setup where paths are known.

Behavior:
  install user skill where supported
  print manual instructions for targets with no stable writable path
  avoid modifying private settings without confirmation

### Print Mode

Print mode outputs the generated Skill or adapter content.

Useful for:
  unsupported tools
  manual setup
  debugging
  documentation

### Doctor Mode

Doctor mode checks whether setup looks correct.

Checks:
  FRAME files exist
  MCP setup guidance exists
  Skill installed
  target adapters installed
  Skill version matches Haxaml version
  Skill contains prebuild terminology
  Skill contains token policy
  Skill contains MCP tool mapping

## Required Commands

Add these commands:

haxaml setup

haxaml setup scope project

haxaml setup scope user

haxaml setup target codex

haxaml setup target claude-code

haxaml setup target cursor

haxaml setup target windsurf

haxaml setup target copilot

haxaml setup target gemini

haxaml setup target cline

haxaml setup target roo

haxaml setup target opencode

haxaml setup target continue

haxaml setup print skill

haxaml setup doctor

haxaml setup dry-run

haxaml setup force

Note:
  CLI flag names can be designed later.
  The important product shape is one high-level setup command with scope and target controls.

## Generated Haxaml Skill Content

The core Haxaml Skill should be concise.

Recommended SKILL.md structure:

---
name: haxaml
description: Use Haxaml as a Git-style FRAME engine for token-efficient AI coding workflows. Use this when working in a repo with Haxaml, `.haxaml/`, or Haxaml MCP tools.
version: 0.1.0
---

# Haxaml Skill

Use Haxaml as a FRAME engine, not as a context dump.

Haxaml does not provide intelligence by itself. The agent supplies the reasoning. Haxaml supplies the structured project workflow, lifecycle gates, FRAME state, validation, verification, and record system.

## Public Lifecycle

about -> guidance -> prebuild -> build -> verify -> record

## MCP Tool Mapping

about:
  haxaml_about

guidance:
  haxaml_guidance

prebuild:
  haxaml_session_start
  haxaml_session_plan
  haxaml_context_pack
  future haxaml_prebuild

build:
  no Haxaml tool
  this is the agent's implementation work

verify:
  haxaml_session_verify

record:
  haxaml_session_record
  haxaml_expect_sync

## Token Policy

Prefer short tool outputs.

Use full detail only when short output is insufficient.

Do not read all `.haxaml/*` files manually by default.

Use one task-scoped context pack per governed task.

Request another context pack only when:

- the task scope changes
- new risk appears
- the previous pack is stale
- verification cannot be completed with current information

Summarize Haxaml outputs instead of pasting full FRAME state.

Do not record utility tasks into `.haxaml/*`.

## Prebuild Discipline

Before coding, use Haxaml to identify:

- task type
- missing information
- required project signals
- likely impact
- risks
- done criteria
- verification evidence required

If the task is unclear, ask the user before implementation.

## Build Discipline

During build, use the context already gathered.

Do not repeatedly call Haxaml tools unless scope changes or a gate fails.

Do not touch unrelated modules.

Do not edit generated files unless the task explicitly requires it.

## Verify Discipline

Before recording success, provide evidence:

- inspected context
- changed files
- summary of changes
- checks run
- risks or unresolved questions
- intentionally untouched areas when relevant

Never record success without verification evidence.

## Record Discipline

Record only useful project memory:

- what changed
- why it changed
- important decisions
- remaining risks
- follow-up expectations

Do not record:

- full chat transcripts
- command spam
- random side tasks
- vague success notes
- duplicate context

## Provider-Agnostic Rule

Do not rely on provider-specific memory as the source of truth.

Treat native files like AGENTS.md, CLAUDE.md, Cursor rules, Copilot instructions, Gemini files, and Windsurf rules as adapters around Haxaml and FRAME.

## Adapter Generation Strategy

Every target adapter should be generated from the same internal recipe.

Recipe sections:

1. Role and purpose
2. Haxaml product truth
3. Public lifecycle
4. MCP tool mapping
5. Token policy
6. Prebuild discipline
7. Build discipline
8. Verify discipline
9. Record discipline
10. Provider-specific notes

This prevents drift between target files.

## Internal Package Structure

Suggested package layout:

haxaml/
  setup/
    detect.py
    install.py
    targets/
      codex.py
      claude_code.py
      cursor.py
      windsurf.py
      copilot.py
      gemini.py
      cline.py
      roo.py
      opencode.py
      continue.py
      junie.py
      zed.py
      aider.py
  skills/
    haxaml/
      SKILL.md
      examples/
        governed-task.md
        utility-mode.md
        refresh-context.md
  adapters/
    cursor.mdc
    windsurf.md
    copilot-instructions.md
    gemini.md
    cline.md
    roo.md
    continue.md
    junie-agents.md
    zed-rule.md
    aider-conventions.md

## Setup Output Example

When setup completes, output should look like:

Haxaml setup complete.

Project root:
  /path/to/project

FRAME:
  created or validated `.haxaml/`

MCP:
  setup guidance generated

Skill:
  Haxaml Skill installed
  token-efficient operating guide ready

Detected targets:
  Codex: installed
  Cursor: installed project rule
  Copilot: generated repository instructions
  Gemini: generated GEMINI.md

Public lifecycle:
  about -> guidance -> prebuild -> build -> verify -> record

Next steps:
  1. Connect the Haxaml MCP server in your agent.
  2. Start the agent in this project.
  3. Tell the agent to use Haxaml for governed work.

## Setup Safety Rules

Haxaml setup should never silently overwrite user-owned files.

If a target file already exists:

- preserve it
- create a backup only when explicitly allowed
- append a managed Haxaml section only when safe
- otherwise write a `.haxaml.generated` or `.haxaml-suggested` file
- tell the user what to merge manually

Generated sections should include markers:

BEGIN HAXAML MANAGED SECTION
END HAXAML MANAGED SECTION

Only content inside those markers may be updated automatically.

## Versioning

The Haxaml Skill should have a version.

The version should be checked by `haxaml setup doctor`.

Doctor should warn when:

- package version and Skill version drift
- Skill still says preflight instead of prebuild
- Skill does not include token policy
- Skill does not include MCP tool mapping
- adapter files are stale
- target-specific files conflict with FRAME policy

## Roadmap Placement

Add Haxaml Skill setup to `v0.6.0` or `v0.7.0`.

Recommended:

v0.6.0:
  Add built-in Haxaml Skill bundle.
  Add setup command.
  Add project-scope setup.
  Add Codex, Claude Code, OpenCode, Cursor, Copilot, and Gemini adapters.

v0.7.0:
  Add user-scope setup.
  Add Cline, Roo Code, Windsurf, Continue adapters.
  Add setup doctor.
  Add adapter version checks.

v0.8.0:
  Add stronger detection.
  Add safe merge behavior.
  Add stale adapter warnings.
  Add golden tests for all generated target files.

v0.9.0:
  Add provider switch demo.
  Freeze setup target contracts for v1.0.

## Final Product Statement

Haxaml setup should make the product feel complete.

The user should not have to manually understand FRAME, MCP, Skills, rules, and provider-specific setup before starting.

The command should do the heavy lifting:

haxaml setup

That command should prepare the project, install the Haxaml Skill or equivalent adapter, generate MCP guidance, and give the agent a token-efficient workflow.

Haxaml is MCP-first, but the Skill layer is built in and mandatory for the intended product experience.

MCP is the engine.
Skill is the operating discipline.
FRAME is the model.
Setup connects everything.