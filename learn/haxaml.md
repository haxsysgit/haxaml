# Haxaml: How FRAME Becomes A Working System

For the canonical product vision and feature direction, see [goals.md](../goals.md). This file focuses on how Haxaml implements the governed lifecycle around FRAME.

If `FRAME.md` is the model, this file is the "okay, but how does Haxaml
actually make that model useful?" guide.

Start there if you have not read it yet: [FRAME.md](FRAME.md).

FRAME explains the idea:

- Facts
- Rules
- Acts
- Map
- Expect

Five buckets for project memory. Clean, simple, human-readable.

Haxaml is what turns those buckets into a working system for AI agents.

That distinction matters. FRAME by itself is the shape. Haxaml is the machinery
around the shape: files, schemas, MCP tools, lifecycle gates, context packs,
exports, validation, adoption, state recording, tiered history, and guided retrieval.

So the short version is:

FRAME says what project memory should look like.

Haxaml says how agents should use that memory while they are actually working.

That is the whole point of this doc.

## Why Haxaml Exists

AI agents do not only need information.

They need timing.

They need guardrails.

They need a way to ask for the right context at the right moment.

They need a way to record what happened after the work is done.

They need a way to stop when the project state is broken instead of confidently
writing a fake success summary.

This is where plain prompt files start struggling.

A prompt file can tell an agent, "read these docs" or "run these tests." That is
useful. But it does not create a runtime workflow. It does not know whether the
agent already pulled context once. It does not know whether the project has
blocking conflicts. It does not know whether the agent skipped verification. It
does not know whether a side task should avoid touching project memory.

Haxaml is built around that gap.

The bet is simple: if AI agents are going to work inside real projects, project
memory cannot just be a static wall of text. It needs structure, validation, and
runtime tools.

Not because agents need more ceremony.

Because agents move fast, and fast work without shared memory gets messy very
quickly.

## The Main Mental Model

Here is the clean split:

FRAME is the memory model.

Haxaml is the execution supervisor.

FRAME answers:

- What is true?
- What rules matter?
- What happened already?
- What can changes affect?
- What should happen next?

Haxaml answers:

- Has the agent been onboarded for this session?
- Is this task governed project work or just a side task?
- What context should the agent read for this task?
- Is the project state valid?
- Are there cross-file conflicts?
- Did the agent verify before recording success?
- What should be written back into project memory?
- What native agent files can be generated from the same truth?

That is the difference between "a doc the agent may or may not read" and "a
governed workflow the agent can actually follow."

Haxaml is not trying to replace the model. It is trying to make the model
operational.

## Why The Memory Lives In Files

Haxaml stores FRAME in project files under `.haxaml/`:

```text
.haxaml/facts.yaml
.haxaml/rules.yaml
.haxaml/acts.yaml
.haxaml/map.yaml
.haxaml/expect.yaml
```

This was a very deliberate choice.

Project memory should be visible in the project.

It should be reviewable in a pull request. It should survive across tools. It
should not disappear when a chat gets archived, an IDE setting changes, or a
provider memory feature behaves differently than expected.

Files are boring in the best way.

They work with Git. They work with code review. They work with editors. They
work with CI. They can be read by humans and parsed by tools. They can be
diffed. They can be backed up. They can be exported.

That does not mean every piece of project knowledge belongs in `.haxaml/`.
Long architecture essays, product docs, and ticket discussions still belong in
normal docs and planning tools. Haxaml is for the operational memory agents must
not miss.

If forgetting it would make an agent do the wrong thing, it probably belongs
somewhere in FRAME.

If it is background reading, link to it from FRAME instead of stuffing the whole
thing into the state.

## Why YAML

The obvious question is: why YAML?

Why not JSON? Why not TOML? Why not Markdown?

The honest answer is that all of them are useful. Haxaml uses more than one of
them in different places. MCP itself uses JSON-RPC. Haxaml validates with JSON
Schema-style schemas. Haxaml exports Markdown for native agent files.

But for the canonical project memory files, Haxaml chooses YAML.

The reason is not "YAML is perfect."

The reason is "YAML is a good middle ground for human-governed structured
memory."

YAML's own spec describes it as a human-friendly data serialization language,
and that is exactly the lane Haxaml needs for FRAME files:
[YAML 1.2.2](https://yaml.org/spec/1.2.2/). The files need to hold nested
objects, lists, strings, decisions, run history, impact rules, and project
constraints. They also need to be comfortable enough for a human to edit without
feeling like they are writing transport payloads by hand.

A FRAME file is not just machine data.

It is shared working memory between humans and agents.

That means readability matters.

## YAML Vs JSON

JSON is excellent for interchange.

The JSON RFC describes it as a lightweight, text-based, language-independent
data interchange format: [RFC 8259](https://www.rfc-editor.org/rfc/rfc8259).
That is why JSON shows up everywhere. It is simple. It is portable. Parsers are
fast. Machines love it.

Haxaml uses JSON where JSON makes sense. MCP uses JSON-RPC. CLI output may
return JSON-shaped structures. Benchmarks and raw artifacts can use JSON.

But canonical FRAME files have a different job.

They are not just transport messages. They are files humans are expected to
open, scan, edit, and review.

Pretty JSON is readable, but it gets noisy quickly:

```text
{
  "decision": "preserve native agent files",
  "reasoning": "existing repos may contain user-owned instructions"
}
```

YAML says the same thing with less visual friction:

```text
decision: preserve native agent files
reasoning: existing repos may contain user-owned instructions
```

That difference matters when the file grows.

Quotes, braces, commas, and escaping are fine for programs. For humans editing
project memory, they add drag. The drag is small on one line. It gets annoying
across facts, rules, runs, decisions, risks, and impact maps.

Now, the tradeoff is real.

The local Haxaml benchmark against this repo's current `facts.yaml` showed:

```text
yaml: 595 tokens
json_pretty: 797 tokens
json_compact: 539 tokens
```

So compact JSON was smaller than YAML in that run. JSON also parsed much faster:

```text
YAML parse: 19.871ms average
JSON parse: 0.07ms average
```

That matters. Haxaml should not pretend YAML wins every metric.

The actual decision is more practical:

- Pretty JSON is noisier for humans than YAML.
- Compact JSON is smaller, but bad as editable project memory.
- JSON is faster to parse, but FRAME file parsing is not the bottleneck for
  normal agent workflows.
- YAML gives humans a better editing surface while still being structured
  enough for validation.

So Haxaml uses YAML for canonical memory and JSON where machine transport needs
it.

That is the tradeoff.

## YAML Vs TOML

TOML is a good format.

Its spec describes it as a configuration file format that aims to be obvious
and minimal: [TOML v1.0.0](https://toml.io/en/v1.0.0). That is a great goal.
For app config, package metadata, and simple settings, TOML can feel very clean.
This repo already uses `pyproject.toml`, because Python packaging lives there.

But FRAME is not only configuration.

FRAME has nested project facts. Agent rules. Run history. Decisions. Open
questions. Module maps. Impact declarations. Future expectations. Some of
those shapes are deeply list-heavy.

TOML can represent arrays and tables, but once the data becomes a journal of
runs and decisions, it starts feeling less natural than YAML.

For example, this kind of state is normal for Haxaml:

```text
runs:
  - task: rewrite FRAME guide
    result: success
    risks: none
  - task: validate MCP registration
    result: success
    risks: none
```

In TOML, repeated nested records are possible, but they are more config-like and
less diary-like. Haxaml needed the file to feel like structured project notes,
not only a settings file.

That is why TOML is great for `pyproject.toml`, but not the best default for
FRAME's living memory.

## YAML Vs Markdown

Markdown is great for humans.

The CommonMark spec exists because Markdown became a huge part of how people
write plain-text documents: [CommonMark 0.31.2](https://spec.commonmark.org/0.31.2/).
Haxaml uses Markdown too. It exports FRAME into agent-native Markdown files like
`CLAUDE.md`, `AGENTS.md`, `.github/copilot-instructions.md`, Cursor rules, and
other instruction surfaces.

Markdown is excellent for explanation.

It is not great as the canonical state format.

Why?

Because Markdown is prose-first. It is easy to write a nice paragraph that
sounds clear to a human but is hard for a tool to validate.

This looks fine:

```text
The current task is to finish the docs rewrite. Make sure links work and avoid
touching implementation files.
```

But for an agent workflow, Haxaml needs something more checkable:

```text
active_task: rewrite haxaml.md
success:
  - explains implementation choices
  - references FRAME.md
  - avoids long code dumps
```

The second shape is easier to validate, summarize, compact, and convert into
task-specific context.

So Haxaml uses Markdown as an output adapter, not as the source of truth.

Markdown is where project memory gets explained to a specific agent or human.

YAML is where the canonical memory lives.

## Why JSON Schema Still Shows Up

Here is the part that can confuse people:

Haxaml uses YAML files, but the schemas are JSON Schema-style schemas.

That is normal.

JSON Schema is about structure, not only `.json` files. The JSON Schema project
describes it as a way to annotate and validate JSON documents:
[JSON Schema overview](https://json-schema.org/overview/what-is-jsonschema).
Haxaml loads YAML into normal data structures, then validates that data against
schemas.

So the combo is:

- YAML for human-editable project memory.
- JSON Schema-style validation for required fields, types, enums, and shape.

That gives Haxaml both readability and discipline.

Without schemas, YAML can become a nice-looking mess.

With schemas, Haxaml can say:

- Facts must include identity, goal, stack, architecture, database,
  constraints, and success criteria.
- Rules must include before-task behavior, boundaries, after-task behavior, and
  forbidden actions.
- Acts must record current phase and active task.
- Expect must include phases.
- Map must include modules when it is required.

The schema does not write the project for you.

It stops the project memory from pretending to be complete when it is missing
basic parts.

## Why Five Files Instead Of One

Haxaml could have used one giant file:

```text
.haxaml/frame.yaml
```

That would be simple at first.

It would also get heavy fast.

Facts, rules, acts, map, and expectations do different jobs. Mixing them into
one file makes the memory harder to scan and harder to load selectively.

An agent doing a small docs update may need Facts, Rules, and Expect.

An agent doing a risky refactor may need all five.

An agent writing release notes may need Acts more than Map.

An agent generating native instructions may need Facts and Rules, but not every
old run.

Separate files make that possible.

They also make ownership clearer:

- `facts.yaml` is the project identity.
- `rules.yaml` is the agent operating policy.
- `acts.yaml` is the diary, evidence trail, and recorded results against the plan.
- `map.yaml` is module ownership and impact.
- `expect.yaml` is the planned end state, expected runs, checkpoints, and future path.

One big file would be simpler to explain in five seconds.

Five focused files are better once the project starts moving.

## Why MCP-First

Haxaml is MCP-first because agents need runtime tools, not just startup text.

The [Model Context Protocol](https://modelcontextprotocol.io/docs/getting-started/intro)
is an open standard for connecting AI applications to external systems. The MCP
architecture defines a client-server model where servers expose tools,
resources, and prompts to AI hosts:
[MCP architecture](https://modelcontextprotocol.io/docs/learn/architecture).

That is exactly the shape Haxaml needs.

Classic agent usage often looks like this:

1. Put instructions in a file.
2. Start the agent.
3. Hope it reads the file.
4. Hope it remembers the rules.
5. Hope it records the outcome correctly.

That is too passive for governance.

Haxaml wants the agent to do things while it is running:

- Ask for guidance.
- Start a governed session.
- Get a task-specific context pack.
- Check whether it is in utility mode.
- Verify assumptions.
- Record the outcome.
- Inspect project health.
- Reconcile conflicts.
- Export native instruction files.

Those are runtime actions.

MCP gives the agent a way to call those actions directly.

That is why the design is MCP-first instead of "read this huge Markdown file and
please behave."

## Why CLI Still Exists

MCP-first does not mean CLI-useless.

The CLI is still important.

Humans need commands. CI needs commands. Install scripts need commands. Local
debugging needs commands. Sometimes an agent or environment does not have MCP
wired up yet.

So Haxaml has a CLI.

But the design choice in this repo is that the CLI mirrors MCP behavior. It is
not a separate brain.

That matters because duplicated logic creates drift. If the CLI validates one
way and MCP validates another way, users get weird behavior. If MCP records a
session one way and CLI records another way, project state becomes unreliable.

So the CLI acts like a human-friendly front door to the same tool behavior.

MCP is the agent runtime surface.

CLI is the human and automation surface.

Same governance model underneath.

## Why The Lifecycle Exists

The Haxaml lifecycle can look like ceremony if you only see the names:

```text
about -> guidance -> prebuild -> context_pack -> verify -> record -> expect_sync
```

But each step exists because agents commonly fail in a specific way.

`about` exists because the agent needs the operating contract once per active
session. It learns what Haxaml is, what FRAME files mean, which workflow is
recommended, and what not to do.

`guidance` exists because not every task should be treated the same. Some tasks
are implementation work. Some are strategy. Some are side tasks. Some need
clarification. The agent should not guess the mode if Haxaml can help classify
it.

`prebuild` exists because guidance alone does not classify the task type or
check FRAME quality before work begins. Prebuild classifies the task against
domain templates, runs semantic validation, opens the governed session
internally, and produces a readiness report with blocking issues, advisory
warnings, required questions, and a recommended context pack level. It stops
the agent from starting high-risk work in a broken FRAME state.

`context_pack` exists because the agent should pull task-relevant memory, not
the whole project every time.

`verify` exists because "I think I did it" is not enough. The agent needs to
reflect on whether it inspected the right context, changed the right files,
followed rules, and logged unresolved risk.

`record` exists because project memory should survive the session. A completed
task should leave behind changes, decisions, risks, and result status.

`expect_sync` exists because recording the result is not enough by itself. The
forward plan should be updated so the next agent sees what changed in project
direction, not just what happened historically.

That flow is not meant to slow the agent down.

It is meant to stop the most expensive kinds of confusion:

- Acting without onboarding.
- Treating a side task like governed project work.
- Starting complex work in a semantically broken FRAME state.
- Pulling too much context.
- Skipping verification.
- Recording success while project state is inconsistent.
- Forgetting why a decision was made.

For exact operator commands and response signals, use [haxaml-mcp.md](haxaml-mcp.md). This
file is explaining why the flow exists.

## Why Utility Mode Exists

Not every task deserves governance.

If the user asks an agent to sort a folder, answer a quick question, inspect a
file, or do something unrelated to project direction, Haxaml should not write
that into `.haxaml/acts.yaml`.

That would pollute the project diary.

So Haxaml has the idea of utility mode.

Governed mode is for project work.

Utility mode is for side work.

The important rule is: utility tasks should not call the governed lifecycle and
should not modify `.haxaml/*`.

This is small, but it matters. A project memory system becomes useless if it
records every random side quest as if it were part of the project plan.

Good memory is selective.

Haxaml tries to keep the diary about the project, not about every little thing
that happened near the project.

## Why Context Packs Exist

One of Haxaml's biggest design choices is that context should be task-scoped.

The easy move would be:

"Just load all FRAME files every time."

That sounds safe. It is also how context slowly becomes expensive and noisy.

A context pack is Haxaml's answer.

Instead of dumping everything, Haxaml builds a compact bundle for the current
task:

- Essential facts.
- Relevant rules.
- Recent decisions.
- Affected modules.
- Current expected runs and checkpoints.
- Unresolved questions.
- Task risks.

That lets the agent start from a useful summary without dragging the whole
project history into every run.

The Haxaml benchmark data makes the risk obvious. In the state growth simulation
run during planning, the Acts-style state reached `5269` tokens at 50 runs. That
is more than a 4K token budget by itself.

So yes, state grows.

Haxaml assumes that from the beginning.

That is why context packs have limits, omitted-section metadata, token counts,
and context-window usage percentages.

It is not enough to say "context matters."

Haxaml also asks: how much context, for which task, and at what cost?

## Why Haxaml Does Not Just Load Everything

There is a very tempting version of Haxaml that would be simpler to explain:

"Read every FRAME file and every doc every time."

That sounds safe. It feels responsible. It also misses how long-context work
actually fails in practice.

Large context windows are useful, but they are not the same thing as organized
memory. The paper [Lost in the Middle](https://arxiv.org/abs/2307.03172)
showed that models can struggle to use relevant information when it is buried
inside long inputs. The lesson for Haxaml is not "small context only." The
lesson is "do not turn context into a junk drawer."

Haxaml treats context like a meal, not a storage unit.

The agent should get what helps the current task:

- Facts that ground the project.
- Rules that change behavior.
- Acts that explain recent decisions.
- Map entries that show impact.
- Expect entries that define the current target.

If the task needs more, Haxaml can give more. Full detail mode exists.
Visibility calls exist. Resources exist. The system is not trying to starve the
agent.

It is trying to avoid the lazy version of "context engineering" where the answer
to every uncertainty is "paste more stuff."

That matters because too much context can create a weird failure mode. The human
thinks the agent knows something because the text was technically present. The
agent misses it because it was one important sentence inside a huge pile. Then
everyone argues about whether the model ignored instructions.

Haxaml's answer is boring but strong:

Put the memory in the right bucket first.

Then retrieve the bucket that fits the job.

## Why Tools, Resources, And Exports Are Separate

MCP gives Haxaml more than one way to share information with an agent.

That could get messy if every surface tried to do the same job.

So Haxaml separates the roles.

Tools are for actions.

Resources are for readable state.

Exports are for native instruction files.

Those are different.

A tool is something the agent calls when it needs something to happen:

```text
start a session
build a context pack
verify a task
record a result
run reconcile
```

A resource is something the agent reads when it needs context:

```text
haxaml://frame/facts
haxaml://frame/rules
haxaml://frame/acts
haxaml://frame/expect
haxaml://frame/map
```

An export is something Haxaml writes for a specific client:

```text
CLAUDE.md
AGENTS.md
GEMINI.md
Copilot instructions
Cursor rules
```

Keeping those separate stops the system from blurring everything into one giant
prompt.

If the agent needs to perform a governed step, it should call a tool.

If it needs to inspect canonical state, it can read a resource.

If a client needs a native instruction file, Haxaml can export one.

That separation is part of the implementation philosophy. Haxaml is not trying
to make one surface do every job. It gives each surface a clean responsibility.

## Why One Context Pack By Default

Haxaml also limits repeated context pulls.

By default, one context pack per task/session is enough. If the agent asks for
another one, it should explain why the scope changed or why the context became
stale.

This is not because context packs are bad.

It is because repeated visibility calls can become a comfort loop.

Agents sometimes call more tools when they are uncertain. That can be useful.
But it can also turn into noise: pull context, pull more context, inspect state,
inspect health, inspect reconcile, inspect state again, and still not fix the
root issue.

Haxaml wants context gathering to be deliberate.

If the task changed, refresh the pack.

If files changed in a way that makes the old pack stale, refresh the pack.

If nothing changed and the agent is just anxious, use the context already
loaded.

That is the vibe.

## Why Short Responses Are The Default

Haxaml tools support detail modes.

Short mode is the default.

Full mode exists when the agent or human actually needs the deeper payload.

This is another anti-bloat decision. MCP responses have transport overhead.
Every tool call has payloads, envelopes, and messages. The local workflow
benchmark showed:

```text
essential_short: 1536 payload tokens
expanded_short: 2051 payload tokens
essential_full: 2523 payload tokens
```

The lesson is simple: visibility has a cost.

That does not mean "never inspect." It means "inspect when it helps."

Default short responses keep the routine path lean. Full detail is still there
for debugging, schema inspection, and unexpected behavior.

That is a better default than making every agent carry the full backpack every
time.

## Why Validation Is Not Enough

Schema validation is necessary.

It is not sufficient.

A file can be valid and still disagree with another file.

Example:

- `expect.yaml` says the map is required.
- `map.yaml` is missing.

Or:

- `rules.yaml` describes a module boundary.
- `map.yaml` has no matching module.

Each file might look fine by itself. The project state is still not coherent.

That is why Haxaml has three layers of validation:

**Schema validation** checks file shape. Does this form have the right fields?

**Semantic validation** (introduced in 0.6) checks meaning beyond structure.
Are required fields actually filled in? Is the lifecycle state consistent? Does
the active task have a matching open session? These are things the JSON schema
cannot catch but that will break agent workflows at runtime if ignored.

Semantic validation produces two classes of findings:

- Blocking issues prevent `haxaml_prebuild` from advancing and surface as
  validation errors in `haxaml_validate`.
- Advisory warnings surface in `haxaml_doctor` as quality gaps the agent
  should address before complex work.

**Reconcile** checks derivation boundaries and cross-file consistency. It asks
"Do these forms agree with each other?" — catching conflicts like a module
existing in `rules.yaml` but missing from `map.yaml`, or `expect.yaml`
referencing a run that has no matching `acts` record.

Haxaml blocks success/partial recording when there are blocking derivation
conflicts because a broken project memory should not accept a clean success
stamp.

That sounds strict because it is.

But it is strict in the right place.

## Why Verify Before Record

Agents love to summarize.

That is useful, but it can also be dangerous. A confident summary can make
unfinished work look finished.

Haxaml separates verification from recording.

Verification asks the agent to check itself before it writes the final outcome
into Acts.

Did it understand the task?

Did it inspect the right context?

Did it change the right files?

Did it touch anything risky or unrelated?

Did it follow the rules?

Did it log unresolved issues?

Only after that should the session be recorded as success or partial.

This matters because Acts become future memory. If the agent records bad memory,
the next agent inherits it.

So Haxaml treats recording as a meaningful write, not just a nice closing note.

## Why Acts Need Tiered Memory

Acts are the diary.

Diaries grow.

If Haxaml records every meaningful run, decision, and risk, the state gets more
valuable over time. It also gets larger over time.

That is the tradeoff.

Haxaml handles this with tiered memory. Recent state stays in `acts.yaml`.
Older runs, sessions, and verifications move into a readable archive file.
This keeps the default context path lean without throwing away project memory.

Think of it like this:

Recent work needs detail.

Older work still needs to stay available.

Those are not always the same thing.

A future agent usually does not need every old record loaded by default. It
does need a governed way to ask for older decisions, risks, file references,
and outcomes when they matter.

That is why Haxaml now keeps a hot current diary plus a cold searchable
history, instead of trying to squeeze old work into one smaller summary.

## Why Map Is Optional Until It Is Not

Small projects do not need a heavy module map.

If the project is tiny, forcing `map.yaml` too early can feel like paperwork.
That is not the goal.

But once a project has multiple modules, cross-impact changes, shared
integrations, or hidden dependencies, Map becomes important.

Haxaml treats Map as optional until complexity makes it necessary.

That is a practical compromise.

For small projects:

- Facts, Rules, Acts, and Expect may be enough.

For larger projects:

- Map helps agents avoid local-only thinking.
- Map shows ownership.
- Map points to relevant tests and docs.
- Map catches cross-file conflicts.

The principle is simple:

Do not add ceremony before it pays rent.

Do add structure when the project gets risky enough to need it.

## Why Export Exists

Haxaml does not pretend every agent reads `.haxaml/*` directly.

Real tools have native instruction files:

- `CLAUDE.md`
- `AGENTS.md`
- `GEMINI.md`
- `.github/copilot-instructions.md`
- `.cursor/rules/haxaml.mdc`
- `.windsurf/rules/haxaml.md`
- `HAXAML.md`

Those files are useful.

The problem is when each one becomes a separate memory.

Haxaml's export engine exists so FRAME can stay canonical while native files
stay available.

The relationship should be:

```text
FRAME -> generated native instructions
```

Not:

```text
CLAUDE.md says one thing
AGENTS.md says another
Cursor says another
Copilot says another
```

In 0.6, the export engine was refactored around a `PromptRecipe` pipeline:

```text
FrameModel.load() -> build_recipe(frame, agent) -> _render_recipe(recipe) -> Markdown
```

`PromptRecipe` is a normalised intermediate representation. Sections are keyed,
ordered, and filterable — so a caller can inspect which sections will appear,
exclude sections for a custom adapter, or toggle individual sections before
rendering. This makes export deterministic and testable without a filesystem.

Export keeps the project portable.

If the team switches models or clients, the core memory does not have to be
rewritten. Haxaml can generate a different adapter from the same source.

That is the whole reason Haxaml treats prompt files as outputs, not as the
source of truth.

## Why Adoption Is Non-Destructive

Existing projects already have history.

They may already have `CLAUDE.md`, `AGENTS.md`, README notes, Cursor rules,
Copilot instructions, docs, and hidden conventions.

Haxaml should not walk in and overwrite that like it knows better.

So adoption is designed to be non-destructive first.

The safe path is:

1. Inventory existing native agent files and repo context.
2. Identify useful evidence.
3. Detect conflicts.
4. Create or update FRAME intentionally.
5. Validate.
6. Export native files only when the user wants that.

That matters because old prompt files may contain real user-owned knowledge.

Even if the format is messy, the content may be valuable.

Haxaml's job is to convert scattered memory into structured memory, not erase
the team's memory because it was stored in the wrong shape.

## Why Retry Policy Exists

Agents can get stuck in loops.

Call a tool. Get an error. Call it again. Get the same error. Call it again with
slightly different wording. Still broken.

That wastes tokens and makes the session worse.

Haxaml has retry policy around repeated gate errors. If the same gate error
appears again, the system tells the agent to stop retrying and fix the root
cause.

This is a small design choice with a big behavioral effect.

It teaches the agent:

Do not keep knocking on a locked door. Find the key.

If validation is failing, fix the file.

If reconcile is blocked, resolve the conflict.

If about is required, call about.

If context refresh needs a reason, provide a real reason or use the existing
pack.

The goal is not to punish retries. The goal is to stop useless retries.

## Why Response Envelopes Exist

Every Haxaml MCP tool returns a consistent shape:

```text
ok
tool
data
warnings
error
```

This is boring on purpose.

Agents need predictable responses. Humans debugging tool calls need predictable
responses too.

If every tool invents its own result shape, the agent has to keep adapting. One
tool returns a string. Another returns a dict. Another hides the error in a
message. Another returns warnings as prose.

That is how integrations become annoying.

Haxaml uses response envelopes so every tool can say:

- Did it work?
- Which tool answered?
- What data came back?
- Were there non-fatal warnings?
- If it failed, what is the error code and what should happen next?

This makes failure recovery easier.

And failure recovery is a huge part of agentic work.

## Why Haxaml Tracks Tokens

Token tracking is not a vanity metric.

It changes behavior.

If the agent can see context size, it can make better choices. If maintainers
can benchmark workflow profiles, they can catch bloat before it becomes normal.

The Haxaml benchmark system measures things like:

- YAML vs JSON token size.
- Parse speed.
- State growth.
- Context budget.
- MCP workflow payload tokens.
- Transport overhead.

That sounds nerdy because it is.

But it is useful nerdy.

AI workflows often get expensive slowly. A few more docs here. A few more
visibility calls there. A little more state. Suddenly every routine task starts
with a giant context load.

Haxaml tries to make that visible.

The goal is not to make every run tiny. The goal is to keep context intentional.

## Why Haxaml Is Not Just A CLI Tool

If Haxaml were only a CLI tool, it would still be useful.

You could initialize files. Validate them. Export instructions. Run benchmarks.

But a CLI-only system would miss the agent runtime moment.

The most important part of agent work happens while the agent is deciding what
to do next.

That is where MCP matters.

With MCP, the agent can discover tools, call them, receive structured errors,
recover, ask for context, verify, and record outcomes during the same session.

That turns Haxaml from a setup tool into an execution layer.

CLI is still there for humans and automation.

MCP is where Haxaml meets the agent while the agent is alive and working.

## Why Haxaml Is Not Just An MCP Server

The flip side is also true.

Haxaml is not only an MCP server.

The MCP server is the runtime interface. The deeper system is FRAME plus files,
schemas, validation, reconciliation, context building, exports, state
management, adoption, and benchmarks.

If MCP disappeared tomorrow, the FRAME files would still matter. The validation
logic would still matter. The export idea would still matter. The CLI would
still matter.

MCP makes the system usable by agents at runtime.

It does not replace the project memory.

## How Haxaml Thinks About Agents

Haxaml assumes agents are capable but not magically aligned.

That is the whole design vibe.

The agent can write code. It can read docs. It can reason through a task. It can
call tools. It can fix problems. Great.

But the agent still needs:

- A clear source of truth.
- A clear operating contract.
- A task-specific context bundle.
- Verification gates.
- A way to record durable outcomes.
- Guardrails against context bloat and retry loops.

Haxaml does not treat the agent like a toy.

It treats the agent like a fast teammate who needs a good workflow.

That is very different from both extremes:

- "The model will figure it out."
- "The model cannot be trusted with anything."

Haxaml lives in the practical middle.

Give the agent structure. Let it work. Check the work. Record the outcome.

## How Haxaml Handles Portability

The provider landscape changes fast.

One month a team uses Claude Code. Another month it uses Codex. Then Cursor.
Then Copilot. Then Gemini. Then some internal tool.

If project memory is trapped inside one provider's prompt style, every switch is
painful.

Haxaml keeps memory provider-neutral.

FRAME stores the truth.

Exports adapt the truth.

MCP exposes the runtime workflow.

CLI supports humans and automation.

That means the project can move across tools without rewriting its whole memory
system.

This is one of the biggest design reasons Haxaml exists. It is not just about
making one agent behave today. It is about keeping project memory portable
across whatever agent stack shows up next.

## What Haxaml Does Better Than Prompt Files Alone

Prompt files can tell an agent what to do.

Haxaml can check whether the agent followed the path.

Prompt files can include project facts.

Haxaml can validate whether required facts exist.

Prompt files can mention prior decisions.

Haxaml can record decisions in Acts and compact old history.

Prompt files can warn about risky modules.

Haxaml can use Map to detect affected modules and reconcile boundaries.

Prompt files can say "verify before done."

Haxaml can require verification before recording success or partial.

Prompt files can be copied between providers.

Haxaml can export provider-specific files from one memory source.

That is the difference.

Prompt files are instructions.

Haxaml is a governed memory workflow.

## What Haxaml Does Not Try To Do

Haxaml does not try to replace human judgment.

It does not remove code review. It does not make tests optional. It does not
make vague requirements clear by magic. It does not guarantee that every agent
will make the right call.

It also does not try to own every document in the project.

Your README still matters. Your architecture docs still matter. Your issues
still matter. Your design docs still matter.

Haxaml's job is narrower:

Keep the operational memory agents need in a structured, validated, portable
shape, and give agents runtime tools to use that memory correctly.

That is already enough work.

## The Current Limitations

Haxaml is useful, but it is not perfect.

YAML is readable, but it needs validation discipline. Without schemas and
checks, YAML can become a nice-looking mess.

MCP-first is powerful, but MCP support varies by client. Some environments have
great MCP support. Some are still catching up. That is why the CLI and exports
still matter.

Structural governance is not the same as output quality. Haxaml can make the
workflow more consistent, but the code still needs tests, review, and good
engineering judgment.

Benchmarks are currently strongest around structure, token usage, and workflow
overhead. Haxaml would still benefit from deeper real-world cross-provider
quality benchmarking: same tasks, different agents, measured outcomes.

Those limitations are not embarrassing.

They are the honest edges of the system.

## What Good Haxaml Usage Feels Like

Good Haxaml usage should feel calm.

The agent starts with the right brief.

It knows whether the task is governed work.

It starts a session.

It gets the context it needs, not everything in the building.

It does the work.

It verifies.

It records what changed, what was decided, and what risk remains.

Then the next agent can pick up the project without acting like it just woke up
in a random repo.

That is the user experience Haxaml is aiming for.

Not "AI magic."

Not "giant prompt engineering ritual."

Just a project that remembers itself well enough for agents to work inside it.

## The Real Design Philosophy

Haxaml is built on a few simple beliefs.

Project memory should live with the project.

Agents should use structured memory, not scattered vibes.

Runtime tools are better than static instructions alone.

Verification should happen before success is recorded.

Context should be compact by default and expandable when needed.

Provider-specific prompt files should be adapters, not source truth.

History should be recorded, but old history should be compacted.

Small projects should not be crushed by process, but complex projects need
boundaries.

Errors should teach the agent what to fix, not invite infinite retry loops.

That is Haxaml in plain English.

It is FRAME with tools.

It is project memory with gates.

It is agent workflow with a spine.

## Conclusion

FRAME gives the model.

Haxaml makes it move.

FRAME says project memory should be split into Facts, Rules, Acts, Map, and
Expect.

Haxaml stores that memory in YAML, validates it with schemas and semantic
checks, exposes it through MCP tools, mirrors it through CLI commands, exports
it into native agent files via the `PromptRecipe` pipeline, classifies tasks
before build, checks cross-file consistency, builds compact context packs,
records work into Acts, and keeps state from growing forever.

The design choices are not random:

- YAML because humans need to edit the memory.
- JSON/JSON-RPC because machines need transport.
- JSON Schema because structure needs validation.
- Markdown because agents and humans need readable exported instructions.
- MCP-first because agents need runtime tools.
- CLI-second because humans and CI still need commands.
- Five FRAME files because different memory types should not be mashed
  together.
- Lifecycle gates because agent work needs onboarding, scope, classification,
  context, verification, and recording.
- Semantic validation because schema correctness is not the same as lifecycle
  correctness or FRAME completeness.
- PromptRecipe pipeline because export should be deterministic and testable.

That is the thought behind Haxaml.

Not more docs.

Not one more prompt file.

Not provider lock-in dressed up as workflow.

Haxaml is the implementation layer that turns FRAME from a clean idea into a
working system for AI-governed projects.
