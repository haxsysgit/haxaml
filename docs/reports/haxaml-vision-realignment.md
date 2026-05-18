# Haxaml Vision Realignment Report

Date: 2026-05-17

The README vision is still strong: Haxaml should force agents to plan, gather materials, use scoped context, verify with evidence, and record the outcome for the next agent. The issue is not the vision. The issue is that parts of the implementation still behave like advice instead of a governor.

In FPS terms: Haxaml should be the pre-match lobby, loadout check, squad comms, minimap, objective tracker, and after-action report. Some current flows still let the player skip the lobby and run into ranked with missing gear.

## The README Promise

The README makes five promises:

- No planning, no building.
- Gather materials before work starts.
- Define success before editing.
- Budget tokens by pulling only task-relevant context.
- Stop and ask when intent is vague or high-risk.

Those promises are the right product direction. They are also the standard Haxaml should test against before 1.0.

## What Still Matches The Vision

Haxaml already has a useful shape:

- FRAME separates facts, rules, acts, map, and expect.
- MCP tools expose a real lifecycle instead of one giant prompt.
- Prebuild exists as the architect phase.
- Context packs avoid dumping the whole repo by default.
- Verification and record are separate lifecycle events.
- Setup is becoming provider-aware instead of one generic instruction file.

That foundation is still worth keeping.

## Where The Implementation Drifts

### Advisory Text Is Not Enforcement

Prebuild can surface questions and materials, but not every unresolved item blocks `context_pack` or build behavior. Agents can still keep moving because the tool response reads like guidance, not a hard stop.

Fix: introduce a build permit. If required questions or materials are unresolved, no permit exists and the adapter must tell the agent to ask the user instead of editing.

### Acts Is Doing Too Many Jobs

`acts.yaml` is trying to be live state, full diary, completed task list, context cache, and archive pointer. That is why it bloats.

Fix: split hot state from cold evidence. Hot state is the scoreboard. Archive is the replay folder. Context fetch is the replay viewer.

### Setup Is The Trust Boundary

If setup says Codex but writes generic, the user loses trust before Haxaml even starts governing work.

Fix: setup must become preview-first and idempotent. It should show selected target, why it was selected, every path, every merge, and every skip. Rerunning setup should be boring.

### Tests Are Target Dummies, Not Match Simulations

Many tests prove commands return something. Fewer tests prove the system survives real messy projects, repeated setup, large history, corrupt archive, provider ambiguity, and broken lifecycle order.

Fix: add fixture-matrix and state-machine tests that model real operator mistakes.

## Proposed 1.0 Architecture

### 1. Mission Lobby: PrebuildGate

`haxaml_prebuild` should create a structured gate:

- task classification
- risk level
- required user questions
- required repo reads
- required external materials
- planned files/modules
- success criteria
- verification plan
- stop conditions

If anything blocking is unresolved, the session stays in lobby. No build.

### 2. Loadout Check: Materials Receipts

Haxaml should not only say "needs DB URI" or "needs API key." It should record status:

- `missing`
- `provided_by_user`
- `found_in_repo`
- `not_applicable`
- `declined`

Sensitive values should not be stored. The receipt should prove the dependency was handled without leaking secrets.

### 3. Build Permit: Context Pack

`haxaml_context_pack` should consume the gate, not recompute rough hints. It should return:

- build permit id
- exact context budget
- required files to inspect
- unresolved non-blocking risks
- verification obligations

No permit means no edits.

### 4. Inspection: Verification Against The Permit

Verification should not pass just because the agent says it checked something. It should compare:

- changed files against planned scope
- inspected context against required reads
- commands/tests against verification plan
- remaining risks against allowed risk level

### 5. Match Log: Hot Acts Plus Cold Archive

Hot `acts.yaml` should be small and fast:

- active task
- latest run stubs
- current gate state
- latest verification summary
- archive counters

Cold archive should keep full replay evidence:

- verbose sessions
- full verification details
- old completed tasks
- long decisions
- historical context-pack receipts

## Context Engineering Direction

The current agent ecosystem points in the same direction:

- OpenAI Codex engineering emphasizes stable prompt structure, prompt caching, and automatic compaction when context grows.
- Anthropic separates predictable workflows from autonomous agents and recommends simple composable patterns first.
- MCP elicitation gives Haxaml a protocol-level way to ask the user for structured missing context.
- LangChain frames context engineering as writing, selecting, compressing, and isolating context.

Haxaml should use those ideas without becoming a generic agent framework. Its job is narrower: govern coding agents inside repositories.

## What This Means For FRAME

FRAME should stay, but each file needs a sharper job.

- `facts.yaml`: the map rules. What is true about this project.
- `rules.yaml`: the server settings. What agents must obey.
- `acts.yaml`: the live scoreboard. What is active and recently happened.
- `map.yaml`: the minimap. What modules are connected and risky.
- `expect.yaml`: the objective tracker. What the next expected outcomes are.
- `archive/`: the replay vault. Full history, loaded only when useful.

The model is good. The engine needs stronger enforcement.

## Release Impact

The path to 1.0 should shift from "more adapters" to "less bypass."

- Setup UX is release-critical because bad onboarding poisons everything after it.
- Acts compaction is release-critical because token bloat makes Haxaml expensive and less reliable.
- Lifecycle gates are release-critical because "no planning, no building" must be mechanically true.
- Tests are release-critical because the current suite does not simulate enough messy real usage.

## 1.0 Definition Of Done

Haxaml reaches 1.0 when a real project can:

- run setup twice without state loss
- select the intended provider without ambiguity
- keep hot state small after months of work
- force unresolved questions back to the user
- block build when required materials are missing
- verify with evidence tied to the original plan
- hand off to another agent without rereading the whole repo

That is the README vision in operational form.

## Sources

- [OpenAI, Unrolling the Codex agent loop](https://openai.com/index/unrolling-the-codex-agent-loop/)
- [OpenAI, Prompt caching](https://developers.openai.com/api/docs/guides/prompt-caching)
- [Anthropic, Building effective agents](https://www.anthropic.com/engineering/building-effective-agents)
- [MCP elicitation specification](https://modelcontextprotocol.io/specification/2025-06-18/client/elicitation)
- [LangChain, Context Engineering](https://www.langchain.com/blog/context-engineering-for-agents)
