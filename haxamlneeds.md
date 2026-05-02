# Haxaml Needs

## Direction: Haxaml As Agent Prebuild And Governance

Haxaml should move away from being presented as another **AI memory**, **context management**, or **project context** tool.

That market is already crowded. Many tools are trying to help agents remember information, retrieve previous decisions, store memories, or search project context. Haxaml can include memory internally, but memory should not be the public headline.

The stronger direction is:

> **Prebuild and governance for AI coding agents.**

The core idea:

> AI agents should not jump straight from a vague user request into code. They should first understand the job, ask what is missing, gather what they need, plan the work, understand likely impact, define success, verify the result, and only then record progress.

This makes Haxaml less like a memory backpack and more like an operating process for agentic software work.

---

## Why This Direction Is Better

Most people are trying to fix AI coding issues by writing better prompts or feeding agents more context.

That helps, but it does not fully solve the deeper workflow problem:

- The agent starts too early.
- The task is vague.
- The project rules are unclear.
- The agent does not know what it needs.
- The agent touches unrelated files.
- The agent makes assumptions without asking.
- The agent says “done” without evidence.
- The user has to manually correct drift after the damage is already done.

Haxaml should solve the earlier failure point:

> **Was the agent ready to do the work before it started?**

That is a sharper and more marketable question than:

> “Can the agent remember more context?”

Haxaml should be the tool that makes an AI coding agent pause and prepare before acting.

---

## House-Building Analogy

A strong way to explain Haxaml:

Building software with AI agents should be like building a house.

Before anyone starts building:

- the architect understands the final goal
- the plumber knows what materials are needed
- the electrician understands the wiring plan
- the carpenter knows the structure
- the builder understands constraints
- everyone agrees what “done” means

You do not tell a random worker:

> “Build me a house.”

Then hope they figure out the plumbing, wiring, safety rules, materials, and finish line while already building.

But that is how many AI coding workflows currently behave.

A user gives a vague request:

```text
Add authentication.
```

The agent starts editing immediately.

Then the project suffers from:

- missing requirements
- wrong assumptions
- unrelated file edits
- skipped tests
- fake “done” summaries
- architecture drift
- repeated context explanation from the human

Haxaml should fix that by making the agent run a prebuild process before implementation.

---

## Recommended Public Positioning

### Avoid Leading With

Avoid using these as the headline:

- AI memory
- context management
- project context tool
- long-term memory for coding agents
- context engine
- another MCP memory server
- persistent project memory

These can appear deeper in the README, but they should not be the main marketing surface.

### Lead With

Use terms like:

- prebuild
- governance
- readiness
- agent workflow
- task clarification
- work planning
- verification gates
- provider-agnostic agent workflow
- disciplined AI-assisted development

### Best GitHub About

```text
Prebuild and governance for AI coding agents
```

### Alternative GitHub About Options

```text
Agent prebuild for AI-assisted development
```

```text
MCP-first prebuild and governance for AI coding agents
```

```text
AI agent prebuild for real software projects
```

### Best README Headline

```text
Haxaml helps AI coding agents plan before they act.
```

### Best Public Hook

```text
Stop prompting harder. Make the agent gather what it needs first.
```

### Stronger Product Sentence

```text
Haxaml is a prebuild and governance layer for AI coding agents.
```

### Longer Explanation

```text
Instead of relying on one perfect prompt, Haxaml makes the agent inspect the project, ask what it needs, plan the work, gather task-specific signals, verify the result, and record what changed.
```

---

## New Product Category

Haxaml should aim to define or claim one of these categories:

```text
Agent prebuild
```

```text
AI coding governance
```

```text
Agent workflow control
```

```text
AI-assisted development governance
```

The best current category is:

```text
Prebuild and governance for AI coding agents
```

This is more distinctive than “memory for agents.”

A memory tool says:

```text
Here is information from the past.
```

Haxaml should say:

```text
Here is the process you must follow before doing the work.
```

---

## Core Product Promise

Haxaml should promise this:

> **Haxaml makes AI agents understand the job before they touch the code.**

This should become the center of the product.

The deeper promise:

> Haxaml helps agents govern themselves through task classification, clarification, project inspection, planning, impact preview, verification, and recording.

This is the difference between a passive context store and an active workflow controller.

---

## Feature 1: `haxaml_prebuild`

## Summary

`haxaml_prebuild` should become the flagship feature.

It should run before implementation and produce a structured readiness report.

The job of `haxaml_prebuild` is to answer:

> Is the agent ready to work on this task?

If not, it should explain why.

## What It Should Do

`haxaml_prebuild` should combine:

- task classification
- governed vs utility mode detection
- missing information detection
- required user questions
- needed project context
- likely impacted files or modules
- assumptions
- risk flags
- done criteria
- verification expectations
- readiness status

## Why It Matters

This is the feature that makes Haxaml marketable.

Before Haxaml:

```text
User: Add auth.
Agent: Starts coding immediately.
```

After Haxaml:

```text
User: Add auth.
Agent: Runs prebuild.
Agent: Finds missing auth decisions.
Agent: Asks the right questions.
Agent: Identifies likely files.
Agent: Defines done criteria.
Agent: Only codes when ready.
```

That is a demo people will instantly understand.

## Example Output

```yaml
task:
  user_request: "Add authentication to this FastAPI app"
  task_type: "implementation"
  governed_mode: true

understanding:
  summary: "User wants authentication added to an existing FastAPI project."
  likely_goal: "Protect selected API routes and support user login."

missing_information:
  required_questions:
    - "Should authentication use JWT, sessions, OAuth, or another method?"
    - "Which routes should be protected?"
    - "Does a user model already exist?"
    - "Should registration be included?"
    - "What password hashing policy should be used?"

needed_context:
  project_files:
    - "app/main.py"
    - "app/api/router.py"
    - "app/models/"
    - "app/schemas/"
    - "app/core/config.py"

likely_impact:
  modules:
    - "auth"
    - "users"
    - "api routes"
    - "settings"
    - "tests"

risks:
  - "Implementing auth without knowing the intended auth flow may create the wrong design."
  - "Protecting the wrong routes could break existing workflows."
  - "Adding password logic without project policy may introduce security risk."

agent_plan:
  - "Inspect existing project structure."
  - "Confirm auth requirements."
  - "Identify user model and routing setup."
  - "Create minimal implementation plan."
  - "Only implement after required questions are answered."

done_criteria:
  - "Auth flow matches confirmed requirement."
  - "Protected routes are documented."
  - "Tests or verification steps are provided."
  - "No unrelated modules are changed."

status:
  ready_to_build: false
  reason: "Required auth decisions are missing."
```

## How Possible Is It?

Very possible.

This does not require rewriting the entire system. Haxaml already has some of the ingredients through guidance, session planning, context packs, verification, and record gates.

A first implementation can be rule-based and deterministic:

1. Accept the user task.
2. Classify the task type.
3. Read existing FRAME files.
4. Match task type to known requirement templates.
5. Produce missing questions.
6. Identify likely project areas from map entries.
7. Generate done criteria from task type and rules.
8. Return readiness status.

Later, it can become smarter by using optional LLM-assisted analysis, but the first version should avoid depending on magic.

## Suggested Implementation Complexity

| Level | Difficulty | Notes |
|---|---:|---|
| Basic rule-based prebuild | Low to medium | Can be built from task keywords, FRAME data, and templates |
| Project-aware prebuild using map/rules | Medium | Needs good `.haxaml/map.yaml` and `.haxaml/rules.yaml` usage |
| LLM-assisted requirement generation | Medium to high | Useful later, but should not be required |
| Fully adaptive prebuild across project types | High | Needs presets, learning from history, and better classification |

## MVP Version

The MVP should return:

- task type
- readiness status
- required questions
- likely affected areas
- risks
- done criteria
- next recommended action

This alone is enough for a strong demo.

---

## Feature 2: Readiness Status

## Summary

Every prebuild should end with a clear readiness status.

The agent should never be left with vague advice.

It should know whether it can code, ask questions, inspect the project, or stop.

## Suggested Statuses

```text
ready_to_build
needs_user_input
needs_project_inspection
blocked_by_missing_context
utility_mode
blocked_by_conflict
blocked_by_policy
```

## What Each Status Means

### `ready_to_build`

The task is clear enough, project rules are available, no blocking questions remain, and the agent can proceed.

### `needs_user_input`

The task is not clear enough. The agent must ask the user questions before implementation.

Example:

```text
User says: Add payment support.
Haxaml says: Which provider? Stripe, PayPal, Paystack, Moniepoint, or something else?
```

### `needs_project_inspection`

The user request is clear enough, but the agent needs to inspect project files or FRAME entries before planning implementation.

### `blocked_by_missing_context`

The task cannot continue because required project context is unavailable.

Example:

```text
The map file is missing and the task is a risky refactor.
```

### `utility_mode`

The request is a side task and should not modify governed project memory.

Example:

```text
User asks: Explain this error message.
```

### `blocked_by_conflict`

Haxaml detects conflicting instructions or project state.

Example:

```text
Rules say never edit generated files, but Expect asks the agent to edit a generated file directly.
```

### `blocked_by_policy`

The request violates a project rule or safety boundary.

## Why It Matters

A readiness status makes Haxaml feel decisive.

It tells the agent exactly what to do next.

This turns Haxaml from a passive note system into a workflow controller.

## How Possible Is It?

Very possible.

This can be added as a structured field in prebuild, guidance, or session plan responses.

The simplest implementation can use a priority order:

1. If task is utility/off-topic, return `utility_mode`.
2. If required FRAME files are missing, return `blocked_by_missing_context`.
3. If rules conflict with the task, return `blocked_by_policy` or `blocked_by_conflict`.
4. If required task information is missing, return `needs_user_input`.
5. If project inspection is needed, return `needs_project_inspection`.
6. Otherwise return `ready_to_build`.

## Suggested Implementation Complexity

Low to medium.

This is mostly schema design plus decision rules.

---

## Feature 3: Required Questions

## Summary

Haxaml should generate questions the agent must ask before coding.

This directly solves a major prompt problem:

> Users often do not know what the agent needs to know.

Instead of expecting users to write perfect prompts, Haxaml should help the agent ask for missing information.

## Example

User asks:

```text
Add authentication.
```

Haxaml asks:

```text
Before implementation, I need these decisions:

1. Should auth use JWT, sessions, OAuth, or another method?
2. Should registration be included, or only login?
3. Which routes should be protected?
4. Does the project already have a user model?
5. What password hashing approach should be used?
```

## Why It Matters

This is one of the most marketable parts of Haxaml.

It turns Haxaml into a tool that fixes bad or incomplete prompting.

Public line:

```text
Users should not need perfect prompts. Agents should know how to ask for what they need.
```

## How Possible Is It?

Very possible.

Start with task templates.

Example templates:

- authentication
- payments
- database migration
- refactor
- API endpoint
- testing
- deployment
- documentation
- bug fix
- frontend feature
- MCP integration

Each template can define likely required questions.

Example:

```yaml
task_template: authentication
required_questions:
  - auth method
  - protected routes
  - user model availability
  - password policy
  - token/session expiry
  - test expectations
```

The agent can then combine templates with project-specific FRAME rules.

## Suggested Implementation Complexity

| Version | Difficulty | Notes |
|---|---:|---|
| Static templates | Low | Fastest and good enough for MVP |
| Template plus project rules | Medium | Better and more personalized |
| LLM-generated questions | Medium | Useful but needs guardrails |
| Learned questions from previous Acts | High | Powerful later, not needed now |

## MVP Version

Create 8 to 12 common task templates and generate questions from them.

That is enough to demo value quickly.

---

## Feature 4: Missing Materials List

## Summary

Borrowing from the house analogy, Haxaml should output a “materials needed” list.

This makes the prebuild concept very visual.

Instead of the agent vaguely saying:

```text
I need more context.
```

It should say:

```text
I need these exact materials before I can do the job properly.
```

## Example

```yaml
materials_needed:
  - auth method decision
  - protected route list
  - user model location
  - database migration policy
  - test command
  - security constraints
```

## Why It Matters

This is easy to explain publicly.

Marketing line:

```text
Before the agent builds, Haxaml makes it list the materials it needs before the build.
```

This connects directly to the house-building analogy.

## How Possible Is It?

Very possible.

It can be generated from:

- task templates
- required questions
- project rules
- map entries
- expected verification rules

## Suggested Implementation Complexity

Low.

This is mostly a renamed and more visual version of missing requirements.

---

## Feature 5: Impact Preview

## Summary

Before coding, Haxaml should show likely affected files, modules, tests, and boundaries.

The agent should understand what the task might touch before touching it.

## Example

```yaml
impact_preview:
  likely_files:
    - app/api/routes/auth.py
    - app/models/user.py
    - app/schemas/auth.py
    - app/core/security.py
  likely_tests:
    - tests/test_auth.py
  likely_modules:
    - auth
    - users
    - API router
    - settings
  avoid_touching:
    - payment module
    - inventory module
    - unrelated migrations
```

## Why It Matters

This helps prevent one of the most annoying AI coding problems:

> The agent touches files it had no business touching.

Public demo:

```text
User: Refactor checkout.
Haxaml: This may affect checkout, payment, inventory reservation, order confirmation, and tests. Do not touch webhook signature handling unless explicitly required.
```

That is immediately useful.

## How Possible Is It?

Medium difficulty.

The quality depends on the quality of `.haxaml/map.yaml`.

Simple version:

- use task keywords to match known modules
- use map entries to identify related modules
- list likely affected files if known
- list forbidden or unrelated areas from rules

Advanced version:

- parse project structure
- infer modules from imports
- connect tests to source files
- detect generated files
- understand dependency graph

## Suggested Implementation Complexity

| Version | Difficulty | Notes |
|---|---:|---|
| Manual map-based preview | Medium | Good enough for MVP |
| Keyword plus map matching | Medium | Practical and useful |
| Static analysis impact graph | High | Great later |
| Import graph and test mapping | High | Powerful, but more engineering-heavy |

## MVP Version

Start with map-based impact preview.

If `.haxaml/map.yaml` says auth affects users, routes, config, and tests, Haxaml can show that.

---

## Feature 6: Done Criteria

## Summary

Haxaml should force the agent to define success before implementation.

The agent should not start work without knowing what “done” means.

## Example

```yaml
done_criteria:
  - login endpoint works
  - password hashing is used
  - protected routes reject unauthenticated users
  - tests or manual verification steps are provided
  - no unrelated modules are changed
```

## Why It Matters

Without done criteria, agents often stop too early or claim completion without proof.

Done criteria makes verification easier later.

Public line:

```text
If the agent cannot define done, it should not claim done.
```

## How Possible Is It?

Very possible.

Done criteria can be generated from:

- task type
- project rules
- user request
- expected verification commands
- map impact
- previous Acts decisions

## Suggested Implementation Complexity

Low to medium.

Basic done criteria can be generated from templates.

Advanced done criteria can incorporate project-specific rules.

## MVP Version

For each task type, define standard done criteria.

Example:

```yaml
task_type: bug_fix
done_criteria:
  - root cause identified
  - fix applied only to relevant files
  - regression test added or manual verification explained
  - no unrelated behavior changed
```

---

## Feature 7: Verification Evidence Gate

## Summary

Haxaml should strengthen the rule:

> No evidence, no done.

The agent should not be allowed to record success without explaining what it inspected, changed, tested, and left unresolved.

## Required Evidence

A successful record should require:

- inspected context
- changed files
- summary of work
- verification performed
- risks or unknowns
- decisions made
- avoided areas if relevant

## Example Failure

Agent tries to record:

```text
Done.
```

Haxaml blocks:

```yaml
ok: false
error:
  code: "verification_required"
  message: "Cannot record success without verification evidence."
  details:
    missing:
      - inspected_context
      - changed_files
      - verification_summary
      - risks
```

## Why It Matters

This is one of Haxaml’s strongest differentiators.

Many tools can store context.

Fewer tools can say:

```text
You are not allowed to call this done yet.
```

Public line:

```text
Haxaml makes agents prove the work before they record success.
```

## How Possible Is It?

Very possible.

Haxaml already has verification and record concepts. This feature mostly means making them stricter, clearer, and more central to the product.

## Suggested Implementation Complexity

Low to medium.

If Haxaml already blocks skipped verification, this becomes mostly a messaging and schema-strengthening task.

---

## Feature 8: Provider-Agnostic Workflow

## Summary

Haxaml should lean heavily into provider agnosticism.

The user should be able to move between:

- Claude Code
- Codex CLI
- Copilot CLI
- Cursor
- Windsurf
- Gemini
- future agents

The project workflow should stay stable even when the AI tool changes.

## Public Message

```text
Your AI tool can change. Your project workflow should not.
```

## Why It Matters

Developers are switching between AI tools constantly.

One week they use Claude Code. Another week they try Codex CLI. Then Cursor. Then Windsurf. Then Copilot.

Without Haxaml, project instructions get copied across:

- `AGENTS.md`
- `CLAUDE.md`
- `.cursor/rules`
- `.windsurf/rules`
- `.github/copilot-instructions.md`
- random prompt files

That creates drift.

Haxaml should say:

> Keep the workflow stable. Adapt it outward to different agents.

## How Possible Is It?

Medium difficulty.

Haxaml already supports the concept through MCP and exports. To make it stronger, Haxaml should add or improve:

- client-specific export templates
- bootstrap commands
- compatibility examples
- provider comparison docs
- generated native instruction files
- checks for drift between generated/adapted files and canonical Haxaml state

## Suggested Implementation Complexity

| Version | Difficulty | Notes |
|---|---:|---|
| Docs and examples | Low | Fastest way to show the idea |
| Export templates | Medium | Useful for adoption |
| Drift checks between files | Medium to high | Strong feature |
| Full multi-provider workflow testing | High | Great later |

## MVP Version

Start with clear config examples for:

- Claude Code
- Codex CLI
- Cursor
- Copilot
- Windsurf

Then show the same Haxaml workflow working across at least two agents.

---

## Feature 9: Prompt Files As Adapters

## Summary

Haxaml should not fight native agent instruction files.

It should not say:

> Delete `AGENTS.md`, `CLAUDE.md`, Cursor rules, and Copilot instructions.

Instead, it should say:

> Those files are adapters. Haxaml is the governed workflow underneath.

## Public Message

```text
Stop copying project rules across five AI tools. Keep the workflow in one place and adapt it outward.
```

## Why It Matters

This avoids positioning Haxaml as hostile to existing workflows.

Most developers already have some native files.

Haxaml should work with them.

## What This Requires

Haxaml should be able to:

- inspect existing instruction files
- detect overlapping rules
- detect conflicting guidance
- suggest adoption steps
- preserve user-owned files by default
- generate or update adapter files only with permission
- explain what should live in Haxaml vs what should live in native files

## How Possible Is It?

Medium difficulty.

The simple version can inspect files and produce an adoption report.

The advanced version can reconcile conflicts and generate clean adapters.

## Suggested Implementation Complexity

| Version | Difficulty | Notes |
|---|---:|---|
| Adoption report | Medium | Very useful and achievable |
| Rule overlap detection | Medium | Can be heuristic-based |
| Conflict detection | Medium to high | Needs careful logic |
| Safe generated adapters | Medium | Good next step |
| Automatic rewrite of native files | High | Risky, should be opt-in only |

## MVP Version

Build an adoption report:

```yaml
native_files_found:
  - AGENTS.md
  - CLAUDE.md
  - .cursor/rules/project.md

overlapping_guidance:
  - testing command appears in multiple files
  - architecture rule appears in AGENTS.md and CLAUDE.md

possible_conflicts:
  - AGENTS.md says use pytest
  - CLAUDE.md says use uv run pytest

recommended_action:
  - move canonical testing rule into Haxaml rules
  - keep native files as tool-specific adapters
```

---

## Feature 10: Agent Self-Governance

## Summary

This is the high-level product idea.

Haxaml should help agents govern themselves.

Not magically.

Practically.

The agent should follow a disciplined workflow:

1. classify the task
2. identify whether it is governed work
3. ask for missing information
4. gather project signals
5. create a plan
6. preview impact
7. define done criteria
8. implement only when ready
9. verify the result
10. record the outcome

## Public Line

```text
Haxaml gives AI agents a workflow they have to follow before they touch your code.
```

## Why It Matters

This separates Haxaml from memory tools.

A memory tool helps the agent remember.

Haxaml should help the agent behave.

That is a stronger promise.

## How Possible Is It?

Very possible as an incremental roadmap.

It does not require one massive feature.

It can be built as a sequence:

1. guidance
2. prebuild
3. session start
4. plan
5. context pack
6. verify
7. record
8. expect sync
9. reconcile

The important part is making the lifecycle strict and easy to demonstrate.

## Suggested Implementation Complexity

Medium overall.

The individual pieces are manageable. The challenge is making the workflow feel smooth instead of ceremonial.

---

## Feature 11: Task Type Templates

## Summary

Haxaml should include task templates that define common prebuild logic.

This makes prebuild practical without needing a full AI reasoning engine.

## Suggested Templates

- authentication
- payment integration
- API endpoint
- database migration
- bug fix
- refactor
- testing
- documentation
- deployment
- CLI command
- MCP server integration
- frontend feature
- security-sensitive change
- performance optimization

## Example Template

```yaml
task_type: payment_integration
required_questions:
  - "Which payment provider should be used?"
  - "Is webhook support required?"
  - "How should failed payments be handled?"
  - "Does the project already have order or invoice models?"
  - "What verification is expected?"
likely_impact:
  - payments
  - orders
  - webhooks
  - settings
  - tests
risks:
  - "Webhook handling may require idempotency."
  - "Payment verification should not rely only on client-side success."
done_criteria:
  - "Provider flow is implemented according to confirmed requirements."
  - "Webhook or callback behavior is documented."
  - "Verification steps are recorded."
  - "No unrelated payment behavior is changed."
```

## Why It Matters

Templates make Haxaml useful quickly.

They also make the product feel smart without relying on vague LLM behavior.

## How Possible Is It?

Very possible.

This is one of the easiest high-value features.

Start with 8 to 12 templates and improve them through dogfooding.

## Suggested Implementation Complexity

Low to medium.

---

## Feature 12: `haxaml_requirements_brief`

## Summary

This can either be a separate feature or a mode of `haxaml_prebuild`.

Its job is to produce a clean brief from the user request.

## Output Sections

```md
## What I Understand

## What Is Missing

## Questions For The User

## Materials Needed

## Likely Project Impact

## Suggested Plan

## Done Criteria

## Readiness Status
```

## Why It Matters

This is useful for both agents and humans.

It can be shown directly in chat before coding starts.

## How Possible Is It?

Very possible.

It is mostly a formatted version of prebuild output.

## Suggested Implementation Complexity

Low.

---

## Feature 13: `haxaml_impact_preview`

## Summary

This can be a standalone tool for high-risk tasks.

The agent can ask:

```text
What might this task affect?
```

Haxaml responds with likely modules, files, tests, docs, and risk boundaries.

## Why It Matters

This is especially useful for refactors and architecture changes.

## How Possible Is It?

Medium difficulty.

It depends on the quality of map data.

A simple map-based implementation is possible now.

A deeper static-analysis version can come later.

---

## Feature 14: `haxaml_done_check`

## Summary

Before recording success, the agent should run a final done check.

This can be separate from verification or part of verification.

## It Should Ask

- Did the agent satisfy done criteria?
- Did the agent inspect required context?
- Did it change only expected files?
- Did it run or explain verification?
- Did it record unresolved risks?
- Did it avoid unrelated work?

## Why It Matters

This makes Haxaml’s governance feel concrete.

It gives a strong demo:

```text
Agent says done.
Haxaml says not yet.
```

## How Possible Is It?

Very possible.

This extends existing verification logic.

## Suggested Implementation Complexity

Low to medium.

---

## Feature 15: Conflict And Drift Detection

## Summary

Haxaml should detect when project instructions disagree.

This is different from generic context management.

The point is not simply to store instructions.

The point is to stop the agent from acting on conflicting instructions.

## Example

```yaml
conflicts:
  - type: testing_command_conflict
    file_a: AGENTS.md
    value_a: "pytest"
    file_b: CLAUDE.md
    value_b: "uv run pytest"
    recommendation: "Move canonical test command into Haxaml rules and export adapters."
```

## Why It Matters

This is highly marketable because many devs already have scattered instruction files.

## How Possible Is It?

Medium to high difficulty.

Basic detection is possible with simple heuristics:

- detect repeated commands
- detect contradictory phrases
- detect mismatched tool instructions
- detect old vs new setup commands

Advanced detection requires semantic comparison.

## Suggested Implementation Complexity

| Version | Difficulty | Notes |
|---|---:|---|
| Detect duplicate files and repeated commands | Low |
| Detect obvious command conflicts | Medium |
| Detect semantic conflicts | High |
| Auto-reconcile conflicts | High and risky |

## MVP Version

Start with obvious conflicts:

- testing command differences
- package manager differences
- runtime version differences
- forbidden file rules
- generated file handling
- deployment command differences

---

## Feature 16: Provider Switch Demo

## Summary

Haxaml should have a demo showing the same project workflow across different agents.

Example:

```text
Claude Code -> Codex CLI -> Cursor
```

Message:

```text
The agent changed. The project workflow did not.
```

## Why It Matters

This makes platform agnosticism visible.

It also shows why Haxaml is more than an instruction file.

## How Possible Is It?

Mostly documentation and demo work.

Technically, it depends on stable MCP setup across clients.

## Suggested Implementation Complexity

Low to medium.

The hard part is polish, not core engineering.

---

## Feature 17: Better README Around Prebuild

## Summary

The README should be rewritten around prebuild, not memory.

## Suggested Opening

```md
# Haxaml

**Prebuild and governance for AI coding agents.**

Haxaml helps AI coding agents plan before they act.

Most AI coding problems do not start when the agent writes bad code.
They start earlier, when the agent begins work without understanding the job.

Haxaml makes agents run a governed workflow:

1. Understand the task.
2. Ask what is missing.
3. Gather the right project signals.
4. Plan the work.
5. Preview impact.
6. Verify the result.
7. Record what changed.

The goal is simple:

AI agents should not jump from vague request to code.
They should know what they are building before they build it.
```

## Why It Matters

The README is the landing page.

If people land on the repo and see “context management,” they may compare Haxaml with every memory tool.

If they see “prebuild and governance,” the project feels more distinct.

## How Possible Is It?

Very possible.

This is a content and positioning update.

## Suggested Implementation Complexity

Low.

---

## Feature 18: Marketable Demo Scenarios

## Demo 1: Vague Task

User says:

```text
Add authentication.
```

Haxaml responds:

```text
Not ready to code.
Missing auth type, route protection scope, user model location, password policy, and test expectations.
```

## Demo 2: Risky Refactor

User says:

```text
Refactor checkout.
```

Haxaml responds:

```text
Likely impact: checkout, payments, inventory reservation, order confirmation, and tests.
Do not edit payment webhook handling unless explicitly required.
```

## Demo 3: Fake Done Blocked

Agent says:

```text
Done.
```

Haxaml blocks:

```text
Cannot record success.
Missing verification evidence.
No changed files supplied.
No tests or inspection summary provided.
```

## Demo 4: Provider Switch

Show the same project working across:

```text
Claude Code -> Codex CLI -> Cursor
```

Message:

```text
The agent changed. The project workflow did not.
```

## Demo 5: Instruction Drift

Project has:

```text
AGENTS.md
CLAUDE.md
.cursor/rules
.github/copilot-instructions.md
```

Haxaml detects conflicting guidance and recommends an adoption plan.

## Why These Matter

These demos are better than saying:

```text
Haxaml stores context.
```

They show Haxaml controlling agent behavior.

---

## Feature 19: Implementation Roadmap

## Phase 1: Positioning And README

Goal:

Make the repo instantly understandable.

Tasks:

- Change GitHub About to “Prebuild and governance for AI coding agents.”
- Rewrite README opening.
- Add prebuild-focused examples.
- Add “What Haxaml is not” section.
- Add house-building analogy.
- Add simple lifecycle diagram.

Difficulty:

Low.

Impact:

High.

## Phase 2: Basic Prebuild MVP

Goal:

Make Haxaml produce a readiness report before coding.

Tasks:

- Add `haxaml_prebuild` tool.
- Add readiness statuses.
- Add required questions.
- Add materials needed.
- Add done criteria.
- Add simple task templates.

Difficulty:

Medium.

Impact:

Very high.

## Phase 3: Impact Preview

Goal:

Help agents understand likely affected modules before editing.

Tasks:

- Use `.haxaml/map.yaml` to generate likely impact.
- Add `avoid_touching` boundaries.
- Connect task types to likely modules.
- Add risk warnings for cross-module changes.

Difficulty:

Medium.

Impact:

High.

## Phase 4: Strong Verification Gate

Goal:

Make “No evidence, no done” a real product behavior.

Tasks:

- Require changed files for success records.
- Require inspected context.
- Require verification summary.
- Block success when done criteria are not addressed.
- Improve error messages.

Difficulty:

Low to medium.

Impact:

High.

## Phase 5: Adoption And Provider Agnosticism

Goal:

Make Haxaml useful across different AI coding tools.

Tasks:

- Add config examples for Claude Code, Codex CLI, Cursor, Copilot, Windsurf.
- Add native instruction file inspection.
- Add adoption report.
- Add drift detection for obvious conflicts.
- Add provider switch demo.

Difficulty:

Medium.

Impact:

High.

## Phase 6: Advanced Governance

Goal:

Make Haxaml a mature agent workflow controller.

Tasks:

- Add semantic conflict detection.
- Add static-analysis impact graph.
- Add test mapping.
- Add learned patterns from Acts.
- Add optional LLM-assisted prebuild.
- Add CI integration.

Difficulty:

High.

Impact:

High after early adoption.

---

## What Should Exist In The Final Marketable Haxaml

A highly marketable Haxaml should be able to do this:

```text
User gives task.
Agent calls Haxaml.
Haxaml classifies task.
Haxaml says whether agent is ready.
Haxaml asks missing questions.
Haxaml lists needed materials.
Haxaml previews likely impact.
Haxaml defines done criteria.
Agent works only after readiness.
Agent verifies evidence.
Haxaml blocks fake done.
Haxaml records outcome.
User can switch agent provider later.
Workflow stays stable.
```

That is the full product story.

---

## Comparison: Engram vs Haxaml

Engram and similar tools strengthen the reason Haxaml should avoid leading with memory.

Engram appears to focus more directly on persistent memory for AI coding agents: storage, recall, search, MCP access, HTTP API, CLI, and related memory workflows.

That is useful, but it is close to the crowded “AI memory” category.

Haxaml should take a different lane.

## Clean Comparison

| Area | Engram-style memory tool | Haxaml target direction |
|---|---|---|
| Main category | Persistent memory for AI agents | Prebuild and governance for AI coding agents |
| Main question | What should the agent remember? | Is the agent ready to do this work? |
| Core promise | Store and recall useful context | Prepare, plan, verify, and govern work |
| Best demo | Agent recalls old decision | Agent refuses to code until requirements are clear |
| Strength | Memory and recall | Workflow control and readiness |
| Market risk | Crowded memory category | Sharper agent prebuild category |
| User feeling | “The agent remembers” | “The agent works with discipline” |

## Haxaml’s Separation

Engram-style tools say:

```text
What should the agent remember?
```

Haxaml should say:

```text
Is the agent ready to do this work?
```

That is the key separation.

Haxaml can still store memory, but the public story should be about preparation and governance.

---

## Rust Rewrite Question

## Should Haxaml Be Rewritten In Rust?

Not now.

A Rust rewrite could be useful later, but it should not be the priority before Haxaml proves its product direction.

The biggest current need is not raw performance.

The biggest current need is:

- clearer positioning
- prebuild feature
- stronger README
- better demos
- provider-agnostic examples
- verification gate polish
- real users testing it

Rust is powerful, but rewriting too early can become a shiny side quest.

## When Rust Makes Sense

Rust makes sense when Haxaml needs:

- faster parsing
- faster validation
- fast project scanning
- import/dependency graph analysis
- static analysis
- single-binary CLI distribution
- cross-platform performance
- low-level filesystem operations
- heavy concurrency
- fast indexing/search

## When Rust Does Not Make Sense

Rust does not help much with:

- figuring out product positioning
- writing better docs
- validating user demand
- building the first prebuild MVP
- improving marketing clarity
- creating demos
- collecting feedback

So the practical answer is:

```text
Do not rewrite Haxaml in Rust yet.
```

## Better Rust Strategy

Instead of rewriting everything, use Rust later for specific core parts.

Possible phased approach:

```text
Phase 1: Python only
Phase 2: Rust core for parsing, validation, indexing, or fast scanning
Phase 3: Python wrapper around Rust core
Phase 4: optional standalone Rust binary
```

## How Rust Works With Python

There are a few common patterns.

### Pattern 1: Python Calls Rust As A Native Extension

This is the most likely path for Haxaml.

You write performance-sensitive logic in Rust and expose it as a Python module.

Python code imports it like a normal package:

```python
from haxaml_core import validate_frame, run_prebuild

result = validate_frame(".haxaml")
```

Under the hood, `haxaml_core` is compiled Rust.

This is usually done with tools like PyO3 and maturin.

Python remains the user-facing layer.

Rust becomes the fast internal engine.

### Pattern 2: Rust Binary, Python As A Thin Launcher

This is closer to how tools like uv feel.

The core CLI is a Rust binary:

```bash
haxaml validate
haxaml prebuild
haxaml reconcile
```

Python may install it, call it, or wrap it, but the main engine is Rust.

This gives good performance and distribution, but it requires more work.

### Pattern 3: Rust Runs Python

Rust can embed or call Python, but this is usually more complex.

For Haxaml, Python calling Rust is cleaner.

## Practical Hybrid Architecture

A future hybrid Haxaml could look like this:

```text
haxaml-python:
  CLI
  MCP server
  config loading
  user-facing commands
  docs/export behavior
  packaging entrypoints

haxaml-core-rs:
  FRAME loading
  validation
  prebuild scoring
  map analysis
  reconcile checks
  impact preview
  token accounting
  project scanning
```

Python would call Rust like this:

```python
from haxaml_core import run_prebuild, validate_frame, reconcile_frame
```

The user still runs:

```bash
uvx haxaml
```

But internally, some work is Rust-powered.

## Recommended Rust Decision

For now:

```text
Keep Haxaml in Python.
```

Later:

```text
Move specific performance-heavy internals to Rust if needed.
```

Do not rewrite early just because Rust sounds cooler.

A Rust core makes sense after Haxaml has:

- users
- repeated workflows
- performance pain
- stable prebuild design
- clear scanning/validation bottlenecks

Until then, the priority is product sharpness.

---

## Immediate Action List

## Must Do First

1. Change public positioning away from context management.
2. Update GitHub About.
3. Rewrite README around prebuild and governance.
4. Add or design `haxaml_prebuild`.
5. Add readiness status output.
6. Add required questions.
7. Add materials needed.
8. Add done criteria.
9. Add impact preview.
10. Strengthen verification gate messaging.

## Should Do Next

1. Add task templates.
2. Add adoption report for existing agent instruction files.
3. Add provider setup examples.
4. Add demos for vague task, risky refactor, fake done, provider switch.
5. Add GitHub issue templates for agent drift and prebuild feedback.

## Later

1. Add static analysis for impact preview.
2. Add semantic conflict detection.
3. Add optional LLM-assisted prebuild.
4. Add CI integration.
5. Consider Rust core only if performance or distribution demands it.

---

## Final Direction

Haxaml should not be sold as another memory tool.

Haxaml should be sold as:

```text
Prebuild and governance for AI coding agents.
```

The strongest product promise is:

```text
Haxaml makes AI agents understand the job before they touch the code.
```

The strongest public line is:

```text
Stop prompting harder. Make the agent gather what it needs first.
```

The strongest technical story is:

```text
Haxaml uses MCP and FRAME to turn vague coding requests into governed agent sessions with task clarification, impact preview, done criteria, verification evidence, and provider-agnostic workflow continuity.
```

That is the marketable version of Haxaml.
