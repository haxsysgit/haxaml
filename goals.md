# Haxaml Goals

Haxaml is a governance kernel for AI coding agents.

The core thesis is simple: agents need predictable architecture, not just bigger prompts. A larger context window can give an agent more text, but it does not by itself tell the agent what is true, what rules matter, what work has already happened, what files are risky, or what "done" means. Haxaml gives those concerns an explicit shape.

## Product Direction

Haxaml exists to make agent work more predictable, inspectable, and repeatable inside real repositories. It is not a generic agent runtime. It does not try to own model execution, replace an IDE, or compete with every orchestration framework. Its lane is governed agent behavior: plan, gather context, build within boundaries, verify with evidence, record the outcome, and sync the next expectation.

The goal is better output quality through structure:

- Clear task framing before implementation.
- Task-scoped context instead of broad context dumps.
- Project rules and facts that are visible in the repo.
- Examples and lifecycle prompts that guide the agent at the right time.
- Verification evidence before success is claimed.
- Durable state for the next agent or next session.

This matters for single-agent work as much as multi-agent handoff. Even when one person uses one agent, the agent benefits from a stable operating contract. It guesses less, follows a clearer prompt architecture, and leaves behind evidence that can be reviewed.

## Haxaml As Governance Kernel

Haxaml supervises the workflow around an agent. The implementing agent still edits files, runs tests, and makes engineering decisions. Haxaml provides the governed frame around that work:

1. `about`: acknowledge how this project is governed.
2. `guidance`: classify the request and decide whether it is governed project work.
3. `prebuild`: identify risk, missing materials, likely impact, and done criteria.
4. `context_pack`: assemble task-scoped context.
5. build: perform the actual implementation outside Haxaml tools.
6. `session_verify`: record checks, touched files, assumptions, and unresolved questions.
7. `session_record`: write the run outcome into Acts.
8. `expect_sync`: update the planned runbook from what actually happened.

The important rule is: plan the end from the beginning. Expect is the planned end, expected run sequence, checkpoints, and finish line. Acts is the evidence that the plan was acted on and what really happened. Map tells the agent what parts of the codebase those planned and observed changes can affect. Together they keep a governed loop instead of a loose prompt.

## FRAME Protocol Model

FRAME is Haxaml's provider-neutral protocol model for project memory and governed agent work:

- Facts: what is true about the project.
- Rules: how agents must behave here.
- Acts: what already happened and what evidence exists.
- Map: ownership, dependency, and impact boundaries.
- Expect: the planned end state, expected runs, checkpoints, milestones, and success criteria for what should happen next.

FRAME is not meant to be a doc dump. It is structured operational memory. The files should stay compact enough for agents to use and specific enough for humans to review. Long background docs can remain elsewhere and be linked from FRAME when needed.

In practice, the three most important coordination surfaces are:

- `expect.yaml`: the plan, final intended outcome, expected runbook, checkpoints, and "done" condition.
- `acts.yaml`: the checks, evidence, results, and recorded deviations from the plan.
- `map.yaml`: the ownership and impact layer that explains which modules and files the plan can safely touch.

That gives the agent a defined end to work toward. The project does not just keep generating and generating. It reaches a planned product checkpoint, then opens a new improvement cycle from that recorded baseline.

FRAME may later mature toward an open standard for agent-governed project memory. That should be researched and proven first. The near-term goal is to make the model work well in Haxaml, test it against real workflows, and document the parts that are stable enough to standardize.

## Single-Agent Value

Haxaml improves a single agent session by giving the agent a predictable route through the work:

- It separates project truth from transient chat context.
- It makes vague or risky tasks surface missing materials before coding starts.
- It forces the agent to pull relevant context deliberately.
- It records verification evidence instead of relying on a polished final message.
- It keeps short hot state and archived history so continuity does not require replaying the whole repo.

The outcome should be fewer guesses, fewer skipped checks, clearer task boundaries, and higher-quality final answers.

## Multi-Agent Value

Haxaml also supports provider-neutral continuity across tools. Claude, Codex, Cursor, Windsurf, Gemini, Copilot, OpenCode, or another agent can read the same FRAME memory and work from the same governed state.

Provider-specific files still matter. Haxaml setup can write native instructions, skills, MCP config, agents, and workflow adapters. Those files should be adapters over the same project truth, not competing sources of truth.

The multi-agent promise is:

- Handoff through repo-owned memory.
- Archive and retrieval for older run/session/verification detail.
- Cross-tool continuity without hidden provider memory.
- Setup-managed adapters that preserve user-authored native files where possible.

## How Haxaml Is Built

Haxaml is Python-first today. The core system includes:

- A Python package and CLI.
- An MCP server for governed agent tools.
- FRAME YAML files under `.haxaml/`.
- JSON Schema validation and semantic consistency checks.
- A setup and adoption engine for provider-native files.
- PromptRecipe exports for agent instructions and skills.
- Context packs for token-disciplined task context.
- Acts archive and retrieval for cold history.
- A local read-only dashboard for humans.

Rust or C++ may be considered later for measured hot paths, but that is roadmap research, not the current center of gravity. RAG and embeddings are also future research, not a prerequisite for the immediate 1.0 core.

## What Haxaml Is Not

Haxaml is not:

- A generic agent runtime.
- Hidden provider memory.
- A replacement for code review.
- A place to paste every document in a project.
- A guarantee that an agent made the right engineering decision.
- A substitute for tests, CI, security review, or human ownership.

Haxaml should make agent behavior more legible and disciplined. It should not make the system feel magical or unreviewable.

## Documentation Roles

This file is the canonical product, vision, and feature-direction document.

- `README.md` is the main public entrypoint and narrative overview.
- `learn/FRAME.md` is the deep FRAME and protocol-model explanation.
- `learn/haxaml.md` is the deep implementation and lifecycle explanation.
- `docs/architecture.md` is the code and module architecture reference.
- `docs/reports/*.md` are dated audit evidence, not canonical vision docs.
- `checklist.md` is active readiness tracking.
- Roadmaps sequence future work instead of restating the full product philosophy.

After this document lands, duplicate long-form feature-direction sections should be pruned from learning docs, reports, and roadmaps so updates have one obvious destination. README can stay fuller in tone as the main public-facing overview, but it should not compete with `goals.md` as the canonical product-direction document.
