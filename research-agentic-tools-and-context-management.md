# Existing Agentic Tools & Manifests

Modern AI coding tools increasingly use **structured blueprints** (YAML/JSON) together with human-friendly prompts.  For example, **Claude Code subagents** are defined in Markdown files with YAML frontmatter【2†L214-L222】, and the **Software Factory** concept uses a Project Manifest (describing product, domain, goals) plus a Factory Manifest (agent configs)【14†L497-L505】.  Open-source efforts like *Antigravity Architect* go further: each generated project includes an `AGENT_MAP.yaml` which is a “human-readable YAML digest” of the whole repo (so the AI reads one file instead of traversing directories)【18†L405-L413】.  It also compacts its memory log (`.agent/memory/scratchpad.md`) by summarizing completed tasks to avoid context bloat【18†L413-L419】.  In practice, the de facto pattern is: **Markdown for narrative (briefs, agent prompts)** and **YAML/JSON for structured data** (config, state, manifests)【2†L214-L222】【14†L497-L505】.

# Token-Efficient Context Management

A key challenge is keeping the LLM context **focused and small**. Loading *everything* wastes tokens (Dev. post example: 8,000+ tokens of unused data)【28†L112-L120】. Best practice is **lazy loading**: start with a minimal context (a few core fields) and let the agent fetch more data via tools only when needed【28†L130-L139】【28†L179-L186】.  In one case, lazy-loading cut the context from ~12,000 tokens to ~4,500 per request (62% cost reduction)【28†L179-L187】【28†L189-L197】.  Similarly, use **task-specific contexts**: each agent only gets the fields it truly needs (like the “Quality Planning” agent sees machines and specs, while “Maintenance” sees service history)【12†L274-L282】.  And **summarize chat history**: keep recent turns in full, but collapse older dialogue into a brief summary.  More advanced approaches (e.g. **xMemory**) build a hierarchical memory: they chunk convo into “episodes” and “semantics” and retrieve only key facts【9†L115-L123】.  All these techniques (lazy loading, profiling, summarization) ensure the agent’s prompt stays lean and relevant, avoiding the bloat of dumping all files or logs each run【28†L179-L187】【9†L115-L123】.

# Multi-Agent Workflow & Governance

For larger projects, a **multi-agent pipeline** with clear state tracking is essential. One effective pattern is **file-based coordination** (not monolithic prompts): agents read/write a shared `STATE.yaml` (or task list) rather than messaging through a central orchestrator【6†L226-L234】.  In this model, each agent has its own context and works independently: it completes a task, writes results to `STATE.yaml`, and moves on.  Other agents poll this file and proceed when dependencies clear.  As BrainRoad notes, “when an agent finishes a task, it writes its output to STATE.yaml and immediately moves to its next task” – no central queue bottleneck【6†L225-L234】.  Likewise, Claude Code’s *Agent Teams* use a shared task list with states (pending/in-progress/completed) and dependencies【26†L315-L323】. Each teammate (separate Claude session) can claim tasks in parallel; the lead or agents mark tasks done and unblock dependent tasks automatically【26†L315-L323】. In both cases, **labeling and registry** avoid orphaned agents: e.g. a `PROJECT_REGISTRY.md` tracks live sessions【7†L25-L28】, and an `AGENTS.md` file can impose rules (like “main agent only uses 0–2 tools, max 3 agents at a time”) to enforce discipline【6†L285-L293】.  

**Best practices:** use **short agent responses** (1–3 sentences, only spawn/send tools) so the main thread stays thin【6†L269-L278】.  Commit state changes to git for audit history.  Give tasks explicit IDs and owners.  Name agents systematically (e.g. `planner-<project>`, `coder-<feature>`) to avoid confusion【6†L285-L293】【7†L25-L28】.   For high-level coordination, Claude’s teams illustrate that **direct agent-to-agent messaging** plus a shared task table allows complex collaboration (cross-layer modules, reviews, etc)【24†L169-L178】【26†L315-L323】, albeit at higher token cost per agent.

# Proposed ‘Prompton’ Blueprint & Workflow

Building on these patterns, **Prompton’s approach** would be:

- **Project Blueprint (YAML/JSON):** a single concise manifest (e.g. `project.yaml`) capturing all critical metadata. Fields might include: project name/desc, chosen stack (e.g. “FastAPI + Vue”), UI style/theme or inspiration, architecture style with rationale, database choice/URI, planning tool (Notion vs Obsidian), key features/goals, and agent roles.  For example:

  ```yaml
  project:
    name: "E-Commerce App"
    domain: "Retail"
    description: "Scalable webstore API with auth, product catalog, and checkout"
  stack:
    backend: fastapi
    frontend: vue
    database: postgresql
  ui:
    theme: "modern dark"
    library: bootstrap
  architecture:
    pattern: "MVC"
    justification: "Easy to scale and test"
  planning_tool: notion
  agents:
    - planner
    - backend_developer
    - frontend_developer
    - tester
  features:
    - user_auth
    - product_crud
    - shopping_cart
    - payment
  ```
  
  This **blueprint file** (human-readable) is the “site brain” – an authoritative summary of what to build.  AI agents and the CLI read it to understand scope, tools, and constraints without bloating the conversation with raw context. (This mirrors the “Project Manifest” concept【14†L497-L505】 and Antigravity’s AGENT_MAP【18†L405-L413】, but in your custom schema.) 

- **Agent Prompts (Markdown + Frontmatter):** Define each role (planner, coder, tester, etc.) in `agents/*.md`. Example `planner.md`:
  ```markdown
  ---
  name: planner
  tools: [Write, Read]
  ---
  You are a senior architect. Use the project blueprint (project.yaml) to break down work into phases and tasks. Each task should be testable and obey the architecture rules from the manifest.
  ```
  Each prompt includes YAML frontmatter (like Claude Code subagents) and a plain-language description.

- **State/Task File (YAML):** A simple `state.yaml` tracks ongoing work. Example:
  ```yaml
  tasks:
    - id: 1
      title: "Initialize repo + setup DB"
      status: completed
      owner: planner
      blocked_by: []
    - id: 2
      title: "Implement user auth"
      status: in_progress
      owner: backend_developer
      blocked_by: [1]
  ```
  Agents update this file to mark progress. New tasks are appended by the planner. This file is the **single source of truth** for workflow, as in BrainRoad’s pattern and Claude’s task list【6†L226-L234】【26†L315-L323】.

- **Policy/Registry:** Include a simple `AGENTS.md` (or inline in blueprint) specifying rules: e.g. “Max 3 agents at once”, “Main agent only 1 tool call at a time”.  Track active sessions in `PROJECT_REGISTRY.md` if using subagents, to avoid orphans【7†L25-L28】.

**Runtime Orchestration:** A CLI (`prompton`) could implement commands like `prompton init` (generate blueprint), `prompton plan` (launch the planner agent to break down tasks), `prompton run` or `prompton build` (spawn coder agents to execute tasks from `state.yaml`), and `prompton review/test`. Under the hood, it would use file-based coordination: for example, spawn a planner subagent to populate `state.yaml`, then spawn code-writer subagents to handle tasks, committing their changes and updating status. This mimics Claude Code’s loop (plan → implement → review → test)【26†L315-L323】 while keeping each agent’s context minimal (only its prompt + current task + needed snippet). Each run can reread the evolving YAML files so the AI “remembers” the overall design without reloading old chat. Over time, the `project.yaml` and `state.yaml` grow into a full blueprint/history of how the site was built.

**Token Efficiency:** Because `prompton` uses structured files, the system need not dump huge file listings into prompts. Agents load only relevant portions (as tools or context) on demand【28†L130-L139】【12†L274-L282】. Summaries (e.g. in `state.yaml`) replace raw logs, and old conversation can be pruned or summarized between runs. The YAML blueprint acts like an external memory: agents can refer to it instead of encoding everything in context. Together, this keeps the LLM prompts concise while still conveying complete instructions.

# Conclusion

No single off-the-shelf tool fully matches this vision yet; existing frameworks provide pieces.  But the pattern is clear: use a **declarative project manifest** (YAML/JSON) as the “source of truth”, enrich it with Markdown prompts for each AI role, and coordinate via a shared state/task file.  This hybrid approach (structure + narrative) is human-readable, machine-actionable, and minimizes token bloat【18†L405-L413】【28†L179-L187】. In short, **Prompton** would sit “above” SuperAPI as the agent orchestration layer: defining what to build and how to coordinate, while SuperAPI still governs individual code edits and architecture rules. By combining these tactics – concise blueprints, just-in-time context, and file-based task management – you get a token-efficient, scalable agentic coding workflow tailored to modern standards【18†L405-L413】【6†L226-L234】.

**Open questions / limitations:** We still need to prototype the exact YAML schema for `project.yaml` and ensure robust locking around `state.yaml` to avoid race conditions. Real-world testing will reveal further adjustments. But the core research suggests this blueprint-plus-coordinator pattern is the right direction.

