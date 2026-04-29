# FRAME: The Main Frame For AI-Governed Projects

Most AI project workflows do not break because the model is "bad".

They break because the project has no shared memory.

That is the whole reason FRAME exists.

A team starts using AI agents. At first, everything feels fast. Someone adds a
`CLAUDE.md`. Someone else adds `AGENTS.md`. Cursor gets its own rules. Copilot
gets another instruction file. A few important decisions live in Notion. A few
more live in GitHub issues. Some live in Slack. Some only exist in a chat
thread from last Tuesday.

Then a new agent shows up and gets half the story.

It reads the README but not the decision log. It sees the old setup command but
not the new one. It knows the code style but not the product constraint. It
finds the prompt file for one provider but misses the instructions for another.
Now the agent is not really "thinking wrong". It is working from a messy
memory.

FRAME is a way to clean that up.

FRAME stands for:

- `F` = Facts
- `R` = Rules
- `A` = Acts
- `M` = Map
- `E` = Expect

That is it. Five plain buckets for the five kinds of context an agent keeps
needing:

- What is true about this project?
- How should agents behave here?
- What already happened?
- Where do things live, and what can changes affect?
- What should happen next?

If you remember nothing else, remember this:

FRAME is not more docs. FRAME is organized project memory.

Haxaml is the current implementation of FRAME. In Haxaml, the memory lives in
`.haxaml/facts.yaml`, `.haxaml/rules.yaml`, `.haxaml/acts.yaml`,
`.haxaml/map.yaml`, and `.haxaml/expect.yaml`. But FRAME is the bigger idea.
Haxaml is one way to make it real.

## Why This Matters

AI agents are powerful, but they are also extremely context-shaped.

Give an agent clean context and it can do useful work. Give it mixed, stale, or
contradictory context and it will confidently walk into problems that look silly
afterward.

That is not mysterious. It is the same thing that happens with people.

Imagine a new developer joins a project. One teammate tells them the app uses
PostgreSQL. The README says SQLite. The deployment docs mention MySQL. The
current ticket does not mention a database at all. If that developer makes a bad
choice, the issue is not just skill. The onboarding was broken.

AI agents have the same problem, just faster.

They can read a lot. They can act quickly. They can touch many files. So when
the context is messy, the damage can spread quickly too.

FRAME slows down the confusion by giving the project one main shape. Not a
giant encyclopedia. Not a magic brain. Just a simple structure that says:

- Facts go here.
- Rules go here.
- History goes here.
- Impact map goes here.
- Current expectations go here.

That one change makes the whole workflow easier to reason about.

## The Old Way: Context Everywhere

Most teams do not plan to create context chaos. It just happens.

The usual setup looks something like this:

- `CLAUDE.md` for Claude.
- `AGENTS.md` for agent CLIs.
- `.cursor/rules/` for Cursor.
- Copilot instructions for GitHub.
- A README that is half setup guide, half product summary.
- Architecture notes in Notion or Google Docs.
- Tickets in Linear, Jira, or GitHub Issues.
- Important "we decided this" moments trapped in chat.
- Long project-context prompts pasted into web chat.
- Random local instructions sitting in one developer's machine.

Each piece may be useful. The problem is that they do not behave like one
memory.

One file says "run `pytest`". Another says "run `uv run pytest`". One prompt
says "never edit generated files". Another ticket asks the agent to edit a
generated file directly. One doc says the billing module owns invoices. A newer
chat says invoices moved to payments. Which one should the agent believe?

Usually, the answer is: whichever one it happened to see.

That is not governance. That is luck.

FRAME gives the project a more stable answer. If something is true, put it in
Facts. If something is a rule, put it in Rules. If a decision happened, record
it in Acts. If a module affects other modules, put that in Map. If a task has a
finish line, put it in Expect.

Now the agent is not guessing from scattered clues. It has a place to look.

## The Real Failure: No Shared Truth

The core failure is not that teams have too many documents.

The core failure is that important project truth lives in too many places with
no clear ranking.

When that happens, every agent session becomes a fresh negotiation:

- Which instruction file is current?
- Which doc is stale?
- Which chat decision still matters?
- Which ticket has the real acceptance criteria?
- Which rules are project-wide and which were only for one task?

Humans can sometimes navigate that with social memory. They remember who said
what. They know which docs are stale. They know which Slack thread mattered.

Agents usually do not.

They need the project to be more explicit.

FRAME is basically saying: stop making the agent solve your context management
problem before it even starts solving the actual task.

## The Provider Trap

Here is a very common path.

You start with one model or one IDE. You tune the perfect instruction file for
it. Maybe it is a great `CLAUDE.md`. It has style rules, testing rules,
architecture notes, examples, and workflow instructions. Nice.

Then the team adds another agent.

Now you need `AGENTS.md`. Then Copilot needs instructions. Then Cursor wants
rules. Then another model follows instructions differently, so you tweak the
wording again.

Suddenly your project memory is copied across provider-specific files.

That is the provider trap.

The project truth gets trapped inside prompts written for one tool. When the
tool changes, the memory has to be rewritten. When one copy changes, the other
copies drift. The project slowly becomes a bunch of adapters pretending to be a
source of truth.

FRAME separates those jobs.

Project memory should be provider-neutral:

- This is what the project is.
- These are the rules.
- This is what happened.
- This is what changes affect.
- This is what we expect next.

Provider-specific files can still exist. They are useful. But they should act
like adapters, not the original memory.

In other words:

`CLAUDE.md`, `AGENTS.md`, Cursor rules, and Copilot instructions should point to
or be generated from the same project memory, not each become their own version
of reality.

That is how you switch tools without rewriting your whole project brain.

## The Token Trap

Another trap is thinking bigger context automatically means better work.

It is easy to see why people think that. Modern models can read huge inputs.
MCP servers can pull docs, files, tickets, schemas, logs, and external sources.
So the instinct becomes: just give the agent everything.

Sounds powerful. Often it is just noisy.

A huge context dump can be expensive. It can be slow. It can bury the important
part in the middle. It can also make humans overconfident because they think,
"Well, the docs were in the prompt, so the agent knew."

Not necessarily.

The paper [Lost in the Middle: How Language Models Use Long
Contexts](https://arxiv.org/abs/2307.03172) showed that models can struggle to
use information placed in the middle of long contexts, even when the model
supports long context. The lesson is pretty simple: more text is not the same
as better memory.

FRAME does not say "never use lots of context".

It says: structure first.

Instead of one giant pile, FRAME gives the context jobs:

- Facts ground the agent.
- Rules guide behavior.
- Acts explain history.
- Map shows impact.
- Expect defines the next target.

Then the agent can pull what it needs for the task.

That is the difference between giving someone a messy backpack and giving them a
labeled toolkit.

## What FRAME Is

FRAME is a small model for project memory.

It is small on purpose. The goal is not to create a heavy process that makes
people groan before they even start working. The goal is to make the important
stuff hard to miss.

FRAME helps with five repeat problems:

- Agents guess facts that should have been written down.
- Agents follow one tool's rules but miss another tool's rules.
- Agents repeat old work because history was not recorded.
- Agents make local edits without understanding impact.
- Agents stop without knowing what "done" means.

FRAME handles those with five buckets:

- Facts: what is true.
- Rules: how to behave.
- Acts: what happened.
- Map: where things live and what they affect.
- Expect: what should happen next.

Now let us walk through each one like a teacher at a whiteboard, not like a
schema manual.

## F = Facts

Facts are the "what is true right now?" part of the project.

Not dreams. Not plans. Not maybe-later ideas. Actual current truth.

Examples:

- Project name: `haxaml`.
- Purpose: deterministic governance for AI-assisted software delivery.
- Runtime: Python 3.11 or newer.
- Package manager: `uv` and `pip`.
- Main surfaces: CLI, MCP server, schemas, context tools, export engine.
- Repository type: developer tooling, not a web app.

Facts are what stop the agent from making up the basics.

If the runtime is not written down, an agent might use syntax the project cannot
run. If the product audience is vague, the agent might write docs for the wrong
reader. If the project purpose is unclear, the agent may optimize for the wrong
thing.

A good Fact sounds like this:

```text
runtime: python 3.11+
```

A weak Fact sounds like this:

```text
runtime: modern Python
```

See the difference? One is usable. The other sounds nice but does not guide a
real decision.

What belongs in Facts:

- Project purpose.
- Current stack.
- Supported runtime.
- Package and build tools.
- Stable architecture choices.
- Product boundaries.
- Supported platforms.
- Important non-goals.

What does not belong in Facts:

- Temporary plans.
- Long explanations.
- Work history.
- Agent behavior rules.
- Provider-specific prompt wording.
- Speculation.

Facts prevent assumption drift.

They are the "before you touch anything, understand this" layer.

## R = Rules

Rules are how agents should behave in the project.

Facts say what is true. Rules say what to do.

Examples:

- Read project context before implementation.
- Do not overwrite user-owned instruction files during adoption.
- Prefer existing code patterns over new abstractions.
- Run validation after changing FRAME files.
- Do not claim success while blocking checks remain unresolved.

Rules need to be concrete. "Be careful" is not a rule. It is a wish.

A better rule:

```text
after changing MCP lifecycle behavior, run the focused MCP registration tests
```

That tells the agent what action matters.

Rules exist because different agents have different default behavior. Some are
bold. Some are cautious. Some edit too broadly. Some stop too early. Some follow
the latest instruction even when it conflicts with project policy.

Rules give the project a consistent operating style.

What belongs in Rules:

- Required read order.
- Forbidden actions.
- Testing expectations.
- Safety boundaries.
- When to ask a human.
- How to handle conflicting instructions.
- Documentation and code style rules that actually affect work.

What does not belong in Rules:

- Project facts.
- Completed task history.
- Every tiny personal preference.
- Long tutorials.
- Full tool manuals.

Rules prevent behavior drift.

They help the project say, "This is how work is done here," no matter which
agent is holding the keyboard.

## A = Acts

Acts are what already happened.

Think of Acts as the project diary for agent work. Not a dramatic diary. More
like: what task happened, what changed, what got decided, what was checked, and
what risk is still open.

Examples:

- Adoption was started.
- Existing native agent files were preserved.
- Validation passed.
- A token benchmark exposed context growth.
- A docs rewrite finished.
- A release risk remains unresolved.

Git already records file changes, but Git does not always explain the working
memory behind them.

A commit can show that `rules.yaml` changed. Acts can explain that it changed
because adoption must not overwrite user-owned instruction files by default.

A test log can show that tests passed. Acts can record which assumption was
verified.

A chat can contain the decision, but if the next agent cannot see that chat, the
project effectively forgot it.

Acts are how the project remembers the useful parts.

What belongs in Acts:

- Completed tasks.
- Partial or failed tasks.
- Decisions.
- Verification evidence.
- Risks found during work.
- Open questions.
- Summaries of old runs.

What does not belong in Acts:

- Full command logs.
- Entire chat transcripts.
- Every tiny action.
- Stable facts.
- Rules that should guide future work.

Acts prevent session amnesia.

Without Acts, every new agent has to rediscover why things are the way they are.
With Acts, the project can say, "We already learned this. Do not start from
zero."

## M = Map

Map shows where things live and what changes affect.

This is the part teams often skip, and then they wonder why agents make narrow
fixes that break something nearby.

Most projects have hidden connections:

- Change the schema and tests fail somewhere else.
- Change session lifecycle and docs need updates.
- Change export behavior and generated agent files are affected.
- Change billing and emails need checking.
- Change auth and onboarding breaks.

Map makes those connections visible.

Examples:

- `haxaml/mcp/tools_lifecycle.py` owns governed session lifecycle behavior.
- `haxaml/mcp/tools.py` and `haxaml/mcp_server.py` keep the public MCP tool export surface stable.
- `haxaml/context.py` owns context pack construction and token accounting.
- `haxaml/schemas/` owns validation shapes.
- `docs/architecture.md` explains module layout.
- Schema changes can affect validation, adoption, and generated docs.

Map does not need to list every file. That would become noise. It needs to
capture the parts where impact matters.

Good Map entry:

```text
module: export engine
affects: generated agent files, docs, example policy tests
```

Weak Map entry:

```text
module: code
```

Map helps the agent ask better questions:

- If I touch this file, what else should I inspect?
- Which tests are likely relevant?
- Is this generated?
- Which docs might need an update?
- Is this a local fix or a cross-module change?

What belongs in Map:

- Module ownership.
- Important file groups.
- Impact relationships.
- Generated file relationships.
- Tests linked to modules.
- Docs linked to behavior.
- High-risk boundaries.

What does not belong in Map:

- Every file in the repo.
- Temporary task plans.
- Long architecture essays.
- General behavior rules.

Map prevents local-only thinking.

It helps the agent understand that touching one part of a project can move
another part too.

## E = Expect

Expect is what should happen next.

This is the active target. The current phase. The "what are we actually trying
to finish?" section.

Examples:

- Current goal: finish release stability work.
- Active phase: dogfooding.
- Current task: rewrite `FRAME.md` as a public-friendly guide.
- Success: explains all five letters, compares old workflows, cites sources,
  avoids long code dumps.
- Next check: inspect links and run a focused safety test.

Expect matters because agents often need a finish line.

If the finish line is vague, the agent may stop too early, overbuild, edit the
wrong files, or run the wrong checks. "Improve docs" is not enough. Improve
which docs? For whom? What counts as done?

Good Expect:

```text
active task: rewrite FRAME.md as a plain-English model guide
success: explains all five letters, compares old workflows, cites research
```

Weak Expect:

```text
active task: improve docs
```

What belongs in Expect:

- Active goals.
- Current phase.
- Milestones.
- Success criteria.
- Next actions.
- Blocking questions.
- Verification gates.

What does not belong in Expect:

- Permanent facts.
- Old completed work.
- General rules.
- Huge roadmaps.
- Background docs.

Expect prevents aimless execution.

It lets the project say, "This is the target right now. Do not wander."

## How The Five Parts Work Together

The magic is not any one letter. The magic is the separation.

Old prompt files often mix everything together:

- "This project uses Python."
- "Do not edit generated files."
- "We decided last week to preserve old config."
- "The CLI lives in this folder."
- "Next, fix MCP registration tests."

All useful. All different.

FRAME sorts them:

- Facts: "This project uses Python."
- Rules: "Do not edit generated files."
- Acts: "We decided last week to preserve old config."
- Map: "The CLI lives in this folder."
- Expect: "Next, fix MCP registration tests."

That sorting makes context easier to maintain.

If the runtime changes, update Facts.

If the workflow changes, update Rules.

If work finishes, record Acts.

If ownership changes, update Map.

If the next milestone changes, update Expect.

This is the part that sounds obvious once you see it. But most agent workflows
still do not do it.

## Schemas, Explained Like A Form

A schema is just a form with required fields.

That is the least scary way to think about it.

If you ask five people for a project update and say, "send me your thoughts",
you will get five different shapes. One person writes a paragraph. One writes a
list. One forgets risks. One forgets the result. One gives you a vibe, not an
update.

Now give them a form:

- Task
- Result
- Changes
- Decisions
- Risks
- Verification

Suddenly the updates are easier to compare. The content can still be human. The
shape is consistent.

That is what schemas do for agents.

They make important fields harder to forget.

Tiny example of Facts:

```text
project: haxaml
purpose: deterministic governance for AI-assisted software delivery
runtime: python 3.11+
```

Tiny example of Acts:

```text
task: rewrite FRAME guide
result: success
verification: links checked, markdown inspected
risks: none known for runtime behavior
```

The point is not "look at this YAML". The point is that structured fields give
humans and tools something stable to check.

OpenAI's [Structured Outputs](https://openai.com/index/introducing-structured-outputs-in-the-api/)
feature is a useful proof point here. It is built around model outputs following
developer-supplied JSON Schemas more reliably. FRAME applies the same general
idea to project memory: when something matters, give it a clear shape.

Schemas do not make agents perfect. They do reduce missing context, vague
handoffs, and "sounds complete but forgot the important field" moments.

## Haxaml As The Current Implementation

Haxaml is the current implementation of FRAME.

It stores the five parts under `.haxaml/`:

- `.haxaml/facts.yaml` for Facts.
- `.haxaml/rules.yaml` for Rules.
- `.haxaml/acts.yaml` for Acts.
- `.haxaml/map.yaml` for Map.
- `.haxaml/expect.yaml` for Expect.

Those files are meant to be readable. Humans can review them. Agents can load
them. Tools can validate them. Native prompt files can be generated from them.

That last part matters.

Haxaml does not say you must delete `AGENTS.md`, `CLAUDE.md`, Copilot
instructions, or IDE rules. Those files still have a job. The difference is
that they should not be the only place project truth lives.

FRAME is the memory.

Native agent files are delivery formats.

That makes the project more portable. If the team changes models or IDEs, the
memory stays intact. Only the adapter needs to change.

## Why This Matches Prompt Guidance

FRAME is not random philosophy. It lines up with where prompt guidance and
research have been pointing.

Anthropic's
[prompting best practices](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices)
emphasize clear instructions, useful context, examples, XML-style separation,
and long-context organization. FRAME does that at the project level. It says:
do not hand the agent a messy pile. Separate the parts.

Microsoft's
[prompt engineering guidance](https://learn.microsoft.com/en-us/azure/foundry/openai/concepts/prompt-engineering)
recommends clear syntax, Markdown or XML-style structure, and breaking large
tasks into smaller steps. FRAME is that same idea applied to project state.
Instead of "understand the repo and do the right thing", the agent gets named
sections with jobs.

OpenAI's [Structured Outputs](https://openai.com/index/introducing-structured-outputs-in-the-api/)
support the idea that schema-backed structure improves reliability when models
need to interact with software systems.

[Lost in the Middle](https://arxiv.org/abs/2307.03172) explains why dumping
huge context is not enough. Important information can get lost inside long
inputs.

[Structured Prompting: Scaling In-Context Learning to 1,000 Examples](https://arxiv.org/abs/2212.06713)
supports the broader idea that structured context can improve performance and
reduce variance as context gets larger.

Different sources, same practical lesson:

Models do better when important information is clear, separated, and shaped for
use.

FRAME turns that lesson into a project memory model.

## Old Prompt Files Vs FRAME

Prompt files are useful. They are just not enough as the main memory system.

Old workflow:

- Put everything in `CLAUDE.md`.
- Copy some of it into `AGENTS.md`.
- Add IDE rules.
- Paste extra context into chat.
- Hope everything stays aligned.

FRAME workflow:

- Facts hold project truth.
- Rules hold behavior.
- Acts hold history.
- Map holds impact.
- Expect holds the current target.
- Prompt files become adapters to that memory.

The difference is responsibility.

In the old workflow, one file may contain facts, rules, history, examples, task
plans, and provider-specific wording all mixed together. In FRAME, each kind of
context has a home.

That makes drift easier to spot.

If a prompt file says the runtime is Python 3.10 but Facts say Python 3.11+,
there is a clear conflict. If one provider instruction says to skip tests but
Rules require validation, the project can catch that mismatch.

The point is not to shame prompt files. The point is to stop making them carry
every job at once.

## Notion And Doc Dumps Vs FRAME

Notion, Google Docs, tickets, and architecture docs are still useful.

But they are usually written for humans, not for repeated agent execution.

A doc dump says:

"Here is everything. Figure it out."

FRAME says:

"Here is what is true. Here is how to behave. Here is what happened. Here is
what changes affect. Here is what we expect next."

That is a different level of clarity.

FRAME does not replace long docs. It makes them easier to use.

Facts can point to the architecture doc. Map can say which docs explain which
modules. Acts can summarize a decision and link to the original issue. Expect
can identify the active milestone.

The long docs stay available. The agent does not need to swallow all of them
for every task.

That is a healthier workflow than pasting a small novel into a prompt and
hoping the agent notices the one sentence that matters.

## Single-Provider Prompt Tuning Vs FRAME

Single-provider prompt tuning can be useful. Sometimes one model really does
need instructions phrased a certain way.

But project memory should not live there.

If your core project knowledge only exists inside one provider prompt, switching
tools becomes painful. The memory is glued to the tool.

FRAME keeps the core memory portable:

- What is this project?
- What rules matter?
- What already happened?
- What files are connected?
- What is the current goal?

Then each provider can receive that memory in the format it handles best.

One tool may prefer Markdown. Another may benefit from XML-style sections.
Another may use MCP resources. Another may need a short generated instruction
file.

Fine. Let the adapter adapt.

The project truth should not have to move every time the tool changes.

## Human Notes Vs Machine-Readable State

Human notes are flexible. Machine-readable state is consistent.

You need both.

FRAME is not trying to turn every thought into a schema. That would be
exhausting. People still need design docs, strategy notes, issue threads,
review comments, and architecture essays.

But some information is too important to leave only in prose:

- Current runtime.
- Forbidden actions.
- Active milestone.
- Verification required before success.
- Modules affected by a change.
- Decisions from the last run.

If forgetting it would make an agent do the wrong thing, it probably belongs
somewhere in FRAME.

If it is background reading or long-form reasoning, it can stay in normal docs
with a pointer from FRAME.

That split keeps the system practical.

## One-Off Chat Memory Vs Persistent Project Memory

Chat is great for working through a problem.

Chat is bad as the only place a project remembers things.

A chat thread can be lost, truncated, unavailable to another tool, or mixed with
ideas that were never final. It can be hard for the next agent to tell the
difference between "we considered this" and "we decided this".

FRAME keeps the useful parts after the conversation ends.

If a chat discovers a new truth, update Facts.

If a chat creates a new operating rule, update Rules.

If a chat completes work or makes a decision, record Acts.

If a chat reveals coupling between modules, update Map.

If a chat changes the plan, update Expect.

The chat can stay conversational. FRAME keeps the durable memory.

## What FRAME Is Not

FRAME is not a replacement for code review.

It gives agents better context. Humans still need to review important changes.
Tests still matter.

FRAME is not a replacement for documentation.

Docs explain deeply. FRAME keeps the operational memory clear.

FRAME is not an MCP feature.

Haxaml can expose FRAME through MCP, but FRAME is the memory model underneath.
MCP is a way to use it.

FRAME is not provider-specific.

It should work whether the agent is Claude, GPT, Copilot, Cursor, a CLI tool,
or something else.

FRAME is not a dumping ground.

If the files become giant walls of text, the point has been missed. FRAME should
make context easier to use, not heavier to carry.

## A Simple Example

Imagine a small API project.

Without FRAME, the context is scattered:

- README says the project uses FastAPI.
- `AGENTS.md` says to run `pytest`.
- A chat says the team switched from SQLite to PostgreSQL.
- A Notion page says billing code is risky.
- A ticket says to add invoice export.
- A previous agent learned invoice changes also affect email templates, but the
  note stayed in chat.

Now a new agent is asked to add invoice export.

What does it know? Depends on what it sees.

With FRAME, the same project can say:

Facts:

```text
framework: fastapi
database: postgresql
runtime: python 3.11
```

Rules:

```text
verification: run pytest for API changes
boundary: do not edit generated OpenAPI output directly
```

Acts:

```text
decision: invoice changes also affect email templates
evidence: discovered during prior export investigation
```

Map:

```text
module: billing
affects: invoice API, PDF export, email templates
tests: tests/billing, tests/email
```

Expect:

```text
active task: add invoice export
success: API endpoint, tests, email template compatibility checked
```

Same knowledge. Cleaner shape.

That is FRAME.

## Who FRAME Helps

Developers get a clearer working surface.

They can see the current truth, the rules, the history, the impact map, and the
target without reverse-engineering everything from scattered files.

Non-technical readers get a simple mental model.

They do not need to understand MCP or schemas to understand the point: FRAME
helps the project remember what matters when AI tools are doing work.

Technical decision-makers get portability.

They can evaluate tools without locking project memory into one provider. The
better question becomes: does this workflow preserve Facts, Rules, Acts, Map,
and Expect across tools?

Agent builders get a cleaner interface.

Instead of scraping meaning from random docs, they can build around known
categories of project state. They can validate fields, build compact context
packs, export native prompt files, and record outcomes consistently.

## How FRAME Reduces Cost And Noise

FRAME helps because it changes the context question.

Bad question:

"How much can we fit into the prompt?"

Better question:

"Which parts of project memory does this task need?"

For a small docs edit, the agent may need Facts, Rules, and Expect.

For a risky refactor, it may need all five parts.

For release notes, Acts and Expect may matter most.

That is not starving the model. That is feeding it on purpose.

Unstructured context grows from anxiety. People keep adding more because they
are scared the agent might miss something. FRAME makes selection easier because
the memory is already organized.

## How FRAME Makes Handoffs Better

AI projects involve constant handoffs:

- Human to agent.
- Agent to human.
- One agent session to another.
- One model to another.
- IDE assistant to CLI agent.
- Local work to CI automation.

Every handoff can lose context.

FRAME reduces the loss by giving every handoff the same basic route:

- Read Facts for truth.
- Read Rules for behavior.
- Read Acts for history.
- Read Map for impact.
- Read Expect for the target.

Simple enough for humans. Structured enough for tools.

That is the sweet spot.

## How FRAME Changes With The Project

FRAME is not meant to freeze the project.

It should change when the project changes.

When the runtime changes, update Facts.

When the workflow changes, update Rules.

When work completes, update Acts.

When ownership changes, update Map.

When the goal changes, update Expect.

This makes memory maintenance part of the project, not something reconstructed
later from vibes and old chats.

## How To Start Small

You do not need a perfect FRAME setup on day one.

Start with the obvious things:

1. Write the core Facts.
2. Add the Rules agents must not miss.
3. Record the current Expect.
4. Add Map entries for risky modules.
5. Start recording Acts after meaningful work.

That is enough to improve the next session.

Then expand only when the project proves it needs more:

- Add Facts when agents guess wrong.
- Add Rules when behavior needs to be consistent.
- Add Map entries when impact surprises people.
- Compact Acts when history gets too long.
- Update Expect when the target changes.

Do not fill FRAME just to fill it.

The goal is not a bigger file. The goal is fewer repeated explanations and fewer
avoidable mistakes.

## What Good FRAME Content Feels Like

Good FRAME content is specific, current, and actionable.

Good Fact:

```text
runtime: python 3.11+
```

Weak Fact:

```text
runtime: modern python
```

Good Rule:

```text
after changing MCP lifecycle behavior, run the focused MCP registration tests
```

Weak Rule:

```text
test things well
```

Good Act:

```text
decision: adoption should preserve existing native agent files by default
result: implemented and covered by tests
```

Weak Act:

```text
worked on adoption
```

Good Map:

```text
module: export engine
affects: generated agent files, docs, example policy tests
```

Weak Map:

```text
module: code
```

Good Expect:

```text
active task: rewrite FRAME.md as a public-friendly model guide
success: explains all five letters, compares old workflows, cites research
```

Weak Expect:

```text
active task: improve docs
```

The test is simple:

Can an agent act better because this exists?

If yes, keep it.

If no, tighten it or remove it.

## Why FRAME Beats Scattered Context

Scattered context makes every agent solve a puzzle before doing the task.

FRAME gives the puzzle a shape.

Instead of asking:

- Which file is current?
- Which instruction wins?
- Which note was final?
- Which doc is background?
- What does done mean?

FRAME says:

- Facts are current truth.
- Rules are behavior.
- Acts are history.
- Map is impact.
- Expect is the finish line.

That does not guarantee perfect work. Nothing does.

But it reduces avoidable confusion. It makes contradictions easier to find. It
keeps provider changes cleaner. It helps agents use context instead of drowning
in it.

## Why FRAME Beats Bigger Context Windows

Bigger context windows are useful.

They are not a memory model.

A bigger window lets you include more text. FRAME helps decide what that text
means.

Without structure, a bigger context window can just hold a bigger mess.

With FRAME, long context becomes organized:

- Facts when identity matters.
- Rules when behavior matters.
- Acts when history matters.
- Map when impact matters.
- Expect when direction matters.

The model can still read deep docs. It just does not need to treat every task
like a full-document treasure hunt.

## Why FRAME Beats Hidden Product Memory

Some AI products have memory features. Those can be helpful.

But project governance should not depend only on memory hidden inside a product.

Hidden memory can be hard to review, hard to audit, hard to move across tools,
and unavailable in CI. It can also mix one person's preferences with project
policy.

FRAME puts project memory in project-controlled files.

That means the memory can be versioned, reviewed, validated, exported, and used
by more than one tool.

Product memory can still help. It just should not be the only place project
truth lives.

## The Role Of MCP

MCP can help agents access tools and context through a standard interface.

Haxaml uses MCP so agents can ask for guidance, start governed sessions, pull
task-specific context, verify assumptions, and record outcomes.

But FRAME is not "an MCP thing".

FRAME is the memory model. MCP is one way to operate it.

That distinction matters because the same memory can help a CLI, a docs
generator, a native prompt exporter, or a human reviewer.

## The Role Of Native Agent Files

Native agent files still matter.

Tools look for them. Developers expect them. Some agents may not use MCP. A repo
may still need `AGENTS.md`, `CLAUDE.md`, Copilot instructions, or Cursor rules.

FRAME does not fight that.

It just changes their role.

Those files should become adapters to the memory, not competing memories.

They can summarize rules. They can point to Haxaml. They can include
provider-specific formatting. But the durable project truth should live in
FRAME.

## The Role Of Documentation

Documentation explains. FRAME governs.

A long architecture doc can explain why the system works the way it does.
FRAME Facts can record the current architecture truth. FRAME Map can point to
the modules and docs affected by changes. FRAME Acts can record decisions.
FRAME Expect can say whether the architecture is currently being changed.

Docs stay useful.

FRAME makes the operational parts easier for agents to use.

## The Real Goal

The goal is not to make agents read more.

The goal is to make agents guess less.

If the agent has to guess what the project is, Facts are missing.

If the agent has to guess how to behave, Rules are missing.

If the agent has to guess what already happened, Acts are missing.

If the agent has to guess what a change affects, Map is missing.

If the agent has to guess what done means, Expect is missing.

FRAME gives those answers a home.

## Conclusion

FRAME is not more docs.

FRAME is organized project memory for humans and AI agents.

It takes the messy stuff that usually gets spread across prompt files, chats,
Notion pages, tickets, IDE rules, and provider-specific instructions, then gives
it a clean shape:

- Facts keep agents grounded.
- Rules keep behavior consistent.
- Acts keep history available.
- Map keeps impact visible.
- Expect keeps work pointed at the right finish line.

Haxaml is the current implementation. It stores FRAME in `.haxaml/facts.yaml`,
`.haxaml/rules.yaml`, `.haxaml/acts.yaml`, `.haxaml/map.yaml`, and
`.haxaml/expect.yaml`, then uses tooling and validation to make that memory
practical.

But the bigger point is simple:

AI-governed projects need durable, structured, portable memory.

FRAME is the main frame that gives them one.
