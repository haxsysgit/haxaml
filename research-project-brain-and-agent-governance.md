# Prompton and the missing project brain for coding agents

## Bottom line

As of **April 27, 2026**, I did **not** find a mainstream product that fully matches what you described: a **single, vendor-neutral, human-readable, token-efficient project brain** that can define a project, compile into the instruction formats used by different coding agents, govern long-running agent workflows, and preserve durable project state across IDEs, models, and sessions. What I did find is a strong convergence toward the **pieces** of that system: **AGENTS.md** as an open cross-tool instruction file, entity["company","Anthropic","ai company"]'s `CLAUDE.md` plus project settings and memory, entity["organization","GitHub","software platform"] Copilot and VS Code instructions, prompt files, custom agents, and Agent Skills, entity["company","Cursor","ai code editor company"] Rules and Agent Skills, and entity["company","OpenAI","ai company"] Codex plus MCP as the emerging tool-integration layer. citeturn22view0turn23view0turn23view3turn12view0turn12view1turn10view5turn14view0turn25view3turn18search0

So the idea is real. The gap is not whether the need exists. The gap is that today’s solutions are **fragmented across files, vendors, and runtime layers**. That is exactly where Prompton can have a legitimate product identity: **not another agent**, and not another giant prompt file, but a **project-brain compiler and governor**. citeturn8view0turn21view0turn25view1turn25view0

## What already exists

The closest existing standard is **AGENTS.md**. Its own site describes it as a simple open format, “a README for agents,” used by over 60,000 open-source projects. It is intentionally just Markdown, with **no required fields**, and it is meant to work across many coding agents. GitHub’s docs now support one or more `AGENTS.md` files in a repo and state that the **nearest** one in the directory tree takes precedence. VS Code likewise supports `AGENTS.md` as an always-on instruction file and can apply nested `AGENTS.md` files in subfolders. A 2026 study of 2,923 repositories found that **18.1%** used `AGENTS.md` alone, without any vendor-specific artifact, and argued that it is becoming a tool-agnostic baseline. citeturn22view0turn23view0turn23view3turn23view5turn8view0

But the modern tool stack has already moved beyond a **single file**. VS Code and Copilot split customization into **always-on instructions**, **path-scoped instructions**, **prompt files** with **YAML frontmatter**, **custom agents** stored as `.agent.md`, and **Agent Skills** as an open standard that are loaded when relevant. Claude Code has a similar decomposition: `CLAUDE.md` for persistent startup instructions, JSON settings for permissions and tooling, Markdown subagents with YAML frontmatter, hooks, skills, and separate scopes for user, project, and local configuration. Claude Code’s own docs explicitly say that skills load only when used, which is a token-efficiency feature, not just an organization choice. citeturn2view1turn12view0turn12view1turn2view3turn10view7turn28view0turn10view5

The hosted agents are also closer to your vision than a plain LLM prompt. Copilot cloud agent can research a repository, create an implementation plan, make code changes on a branch, and iterate before opening a pull request. Codex runs tasks in isolated environments, can work in parallel, and can be guided by `AGENTS.md` files to understand navigation, testing, and project practices. In other words, the market has already accepted that serious coding agents need **repository instructions, environment context, and workflow scaffolding**, not just bare prompts. citeturn12view2turn25view3turn25view4

## What the evidence says about context files

The most important research result for your idea is that **context files help, but only when they stay sharp**. The 2026 exploratory study found that context files were the **most commonly adopted** configuration mechanism across agentic coding tools and recommended maintaining `AGENTS.md` as a shared baseline when teams use multiple tools, with vendor-specific files acting as adapters on top. citeturn8view0

But the performance evidence is mixed in a revealing way. One 2026 paper found that adding `AGENTS.md` to repositories was associated with a **28.64% lower median runtime** and **16.58% lower output token consumption**, while keeping task completion behavior comparable. Another 2026 paper reached the opposite warning: across multiple agents and LLMs, repository context files tended to **reduce task success rates** relative to providing no repository context and increased inference cost by **over 20%**. Its conclusion was not “never use context files,” but rather that human-written files should describe **only minimal requirements**. citeturn8view2turn8view1

That apparent contradiction actually sharpens the product design. A good project brain is not a **large dump of everything you know**. It is a **minimal, high-signal control plane**. This is consistent with VS Code’s own advice for custom instructions: keep instructions short and self-contained, explain why rules exist, show preferred patterns with examples, and focus on non-obvious rules rather than everything a linter could enforce anyway. citeturn2view1

So if Prompton becomes “a giant directory of progress logs, plans, summaries, UI notes, and random metadata loaded every run,” it will likely recreate the failure mode the papers are warning about. If it becomes a **thin canonical manifest plus generated views plus dynamic retrieval**, it matches the direction the tools and the evidence are both pointing toward. citeturn8view1turn8view2turn21view0

## Why token bloat is the real design constraint

Your PharMax workflow was directionally right. `progress.md`, `ui plan.md`, run logs, and a reference file that tied them together are all versions of what the emerging literature now calls **structured note-taking**, **agentic memory**, or **compaction**. The problem was that those files were trying to act as both **durable memory** and **active context**, which is exactly where token waste begins. citeturn30view0turn30view1

Anthropic’s 2025 context-engineering writeup is the clearest statement of the problem I found. It frames context as a **finite attention budget**, argues that the goal is to find the **smallest possible set of high-signal tokens**, and recommends using **lightweight references** and **just-in-time retrieval** instead of preloading everything. For long-horizon work, it recommends three specific techniques: **compaction**, **structured note-taking**, and **multi-agent architectures**. Its examples are strikingly close to your own intuition: a compacted summary that preserves architectural decisions and unresolved bugs, a `NOTES.md`-style memory that persists outside the active context window, and subagents that explore deeply in separate contexts and only return dense summaries. citeturn21view0turn30view0turn30view1turn10view1turn10view2

The same theme appears in practical coding tools. Aider uses a **repo map** rather than dumping the full repository into the prompt, and its docs explicitly warn against adding too many files because the model can get overwhelmed and confused. Some weaker models even need the repo map disabled, which is another reminder that “more repo context” is not automatically “better.” citeturn20search0turn20search16turn20search3

Recent research supports that caution. `RepoCoder` showed that iterative retrieval-generation can outperform naïve repository retrieval and improve code completion by **over 10%**. `Repository-Level Prompt Generation` showed a **36%** relative improvement over Codex in its experimental setting. `CodexGraph` argues that similarity-only retrieval has low recall for complex tasks and uses code graphs to retrieve structure-aware context. `SWE-Adept` adds selective dependency traversal plus shared working memory with code-state checkpoints. But `CodeIF-Bench` found that adding repository context averaging about **9.8K tokens** caused a pronounced drop in instruction-following accuracy over longer multi-turn sessions. citeturn9view1turn9view0turn8view7turn9view3turn9view2turn29view1

That means the real Prompton problem is **not** “How do I store more context?” It is “How do I make the right context load at the right moment, while everything else stays as retrievable state?” That is a context-engineering product problem, not a prompt-writing problem. citeturn21view0turn30view4

## What Prompton should actually be

Prompton should be a **source-of-truth manifest, adapter generator, and workflow governor**. The source-of-truth should not be plain Markdown alone. It should be a **structured manifest** that machines can validate and humans can still author comfortably. Then Prompton should **compile** that manifest into the files today’s tools actually understand: `AGENTS.md`, `CLAUDE.md`, Copilot instruction files, prompt files, agent definitions, MCP configs, and output schemas. That pattern fits the market reality that different runtimes expect different artifacts even when the underlying intent is shared. citeturn23view3turn12view0turn12view1turn28view0turn14view0

The format split that best matches current tooling is this: the **human-facing, cross-tool instruction layer** should stay in **Markdown** because that is what `AGENTS.md`, `CLAUDE.md`, and Copilot instructions already use. The **canonical project manifest** should be **YAML**, because current tools already use YAML frontmatter around prompts and agents, and YAML is easier to author than raw JSON for nested metadata. The **strict machine contracts** should be **JSON Schema** or structured JSON outputs, because both OpenAI and Anthropic now explicitly recommend schema-bound structured outputs when exact machine conformance matters. That format recommendation is a synthesis from the ecosystem, not a single vendor rule, but it is the most coherent pattern I found. citeturn22view0turn12view0turn12view1turn2view4turn17view1

| Layer | Best format | Role |
|---|---|---|
| Cross-tool instructions | Markdown | Human-readable rules and guidance |
| Canonical project brain | YAML | Structured source of truth for project metadata |
| Output contracts and APIs | JSON Schema / JSON | Exact machine-readable validation and tool contracts |

Prompton also needs to treat **secrets and tool exposure** as first-class governance problems. Do **not** make raw `db_uri` values or credentials part of the always-on project brain. Store **references** like `DATABASE_URL`, secret-provider keys, or environment variable names in the manifest, and keep actual secrets in local or user config. Claude Code explicitly separates user, project, and local scopes, treats API keys as user-level secure settings, supports project-scoped `.mcp.json`, and documents deny rules for `.env` and secret files. OpenAI’s MCP guidance warns about prompt injection, sensitive data flowing to third-party MCP servers, and the cost/latency of exposing too many tools; it recommends `allowed_tools` specifically to constrain the visible tool surface. citeturn28view0turn14view2turn27search3

Finally, Prompton must ship with **evals**, not just prompts. GitHub’s documentation emphasizes build, test, and validation instructions inside repository custom instructions. OpenAI’s eval guides describe an eval loop that is almost BDD-like: describe task behavior, run tests, inspect results, and iterate. If Prompton does not make acceptance checks part of the canonical manifest, it will fail exactly when projects get bigger and agents begin drifting. citeturn27search11turn27search8turn15view3turn15view4

## A concrete reference design

The most promising version of Prompton is a **canonical YAML manifest** that is never injected whole into the model unless needed. Instead, it produces a **task slice**. The active context should contain only the current objective, the few architectural constraints relevant to that task, the smallest set of files or summaries needed for execution, and the validation rules for that step. The rest remains retrievable state. That is consistent with token-counting APIs, compaction systems, selective skill loading, and the memory-index pattern used in current agents. citeturn15view2turn15view1turn10view0turn10view7turn30view0

A Prompton manifest could look like this:

```yaml
schema_version: 0.1

project:
  name: pharmax
  type: ecommerce-web
  goal: Build a scalable online pharmacy storefront and admin system
  success_metrics:
    - users can browse products and add to cart
    - checkout flow works end to end
    - admin can manage inventory and orders

product:
  audience:
    - retail customers
    - pharmacy admins
  inspirations:
    - clean, modern medical UI
  theme:
    mode: ai-assisted
    notes: Favor accessible, trustworthy, minimal design

stack:
  frontend: react
  backend: fastapi
  db: postgres
  auth: jwt
  deployment: docker

architecture:
  style: modular-monolith
  rationale: Faster iteration now, preserves service boundaries for later extraction
  boundaries:
    - auth
    - catalog
    - cart
    - checkout
    - admin

integrations:
  planning_sources:
    - kind: notion
      ref: PRODUCT_SPEC_PAGE_ID
  mcp:
    - label: github
      scope: readwrite
      allowed_tools:
        - search_issues
        - create_pull_request
    - label: figma
      scope: read
      allowed_tools:
        - fetch_file

state:
  milestone: checkout-v1
  accepted_decisions:
    - postgres over sqlite for concurrency and migrations
    - service-layer business logic only
  open_questions:
    - payment provider choice
  recent_summary: |
    Catalog and auth are stable. Cart endpoints pass tests.
    Checkout models drafted but payment integration not finalized.

retrieval:
  core_files:
    - docs/architecture.md
    - docs/domain-model.md
  maps:
    - .prompton/repo-map.md
  exclude:
    - .env
    - secrets/**
    - build/**
    - logs/full-run-*

evals:
  build: npm run build
  backend_tests: pytest -q
  lint_frontend: npm run lint
  acceptance_checks:
    - user registration works
    - add-to-cart persists
    - checkout creates order

budgets:
  max_prompt_tokens: 12000
  max_files_per_run: 8
  max_tool_results: 5

security:
  secret_refs:
    DATABASE_URL: env
    STRIPE_SECRET_KEY: env
  deny_patterns:
    - .env
    - secrets/**
    - credentials.json

adapters:
  generate:
    - AGENTS.md
    - CLAUDE.md
    - .github/copilot-instructions.md
    - .github/agents/planner.agent.md
    - .github/agents/reviewer.agent.md
    - output-schemas/plan.json
```

The important architectural move is what happens **after every run**. Instead of preserving entire transcripts, Prompton should write a **delta summary**: what changed, what was validated, what remains uncertain, which decisions were accepted, and which files are now the new reference points. That follows the same pattern as Claude Code’s `MEMORY.md` index plus topic files and Anthropic’s recommendation for structured note-taking outside the active context window. Your old `progress.md` idea was not wrong; it just needed to become **compressed durable memory**, not a file that every agent reads in full every time. citeturn10view0turn30view1

The other key move is compilation. Prompton should generate a **short universal adapter** in `AGENTS.md`, a **Claude-specific adapter** in `CLAUDE.md`, **Copilot** instruction files and agents, and **JSON schemas** for planner/reviewer/tester outputs. That is what makes the system survive switching IDEs or models. The open standard is not “one file forever.” The open standard is “one source of truth that can emit multiple compatible views.” citeturn22view0turn23view3turn12view0turn12view1turn25view3

## Verdict

Yes, **something like this exists in fragments**. No, I could not find a **widely adopted, end-to-end product** that already does exactly what you described. The closest established artifact is `AGENTS.md`. The closest surrounding capabilities are Claude-style memory and subagents, Copilot/VS Code prompt files and custom agents, Codex and Copilot cloud-agent planning loops, Agent Skills, MCP configuration, repo maps, compaction, and eval-driven iteration. But the burden of turning those pieces into a coherent **project brain** still falls on the developer. citeturn22view0turn23view0turn10view0turn12view1turn25view3turn15view4

So Prompton is viable **if** it is positioned correctly. It should **not** be another giant prompt file, another memory dump, or another agent runner. It should be a **project-brain layer** with four jobs: keep canonical project truth in structured form, generate the tool-specific files current agents already understand, compress evolving state into durable low-token memory, and enforce validation/eval loops as the project grows. That is the gap the current ecosystem still leaves open. citeturn8view0turn8view1turn8view2turn21view0turn25view0turn15view3

In one sentence: **AGENTS.md is the README for agents; Prompton could be the source-of-truth manifest and context governor that generates the README, the adapters, and the durable project memory.** citeturn22view0turn23view3turn28view0