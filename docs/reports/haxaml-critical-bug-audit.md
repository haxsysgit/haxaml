# Haxaml Critical Bug Audit

Date: 2026-05-17

This audit checks whether Haxaml still matches the README promise: agents should not build until they understand the project, gather materials, plan the end, manage context, verify evidence, and record the result.

Short answer: the vision is still right, but several implementation paths are too soft. In game terms, Haxaml is supposed to be the squad leader, minimap, loadout screen, and match log. Right now some flows still let the agent spawn with missing ammo, the wrong class selected, and a backpack full of old match replays.

## Confirmed Critical Bugs

### 1. `acts.yaml` Is Still Carrying Too Much Active Memory

The copied fixtures show the problem clearly.

- Root `acts.yaml`: 48,456 bytes, 1,279 lines.
- Root `archive/acts-history.yaml`: 71,405 bytes, 2,173 lines.
- `testhaxaml/acts.yaml`: same size as root copy.
- `testhaxaml/archive/acts-history.yaml`: same size as root copy.

Hot `acts.yaml` keeps only 5 runs, 5 sessions, and 5 verifications, but it is still large because `completed_tasks` never gets archived and verbose hot records remain full-size. That means the hot file is not a lean scoreboard. It is still partly a replay archive.

Impact: every agent that reads hot state pays token cost for stale or duplicate history. This weakens the context discipline Haxaml is supposed to enforce.

Fix direction:

- Hot `acts.yaml` should keep short stubs only: id, status, timestamp, short summary, and references.
- Verbose details should move to cold archive.
- `completed_tasks` must be summarized, capped, or archived.
- `max_acts_bytes` must be a real budget, not just a warning.
- Context tools should read hot stubs first and hydrate cold details only on demand.

### 2. Archive Is Lossless But Not Efficient

The archive keeps full records and a large index in the same YAML file. For only 15 archived records, the index is already roughly 24 KB. The archive append path reads the whole archive, appends in memory, and rewrites the whole file.

Game analogy: archive should be the VOD folder on disk. Right now it is a VOD folder copied back into the backpack after every match.

Impact: archive writes get slower as projects live longer, and archive search still has avoidable token and I/O cost.

Fix direction:

- Split archive storage into append-only history chunks plus a capped search index.
- Keep index entries aggressively short.
- Rebuild or validate index from history so corruption does not become permanent truth.
- Avoid hydrating full archive records for short responses or context hints.

### 3. Auto Archive Was Not Actually Default

The default memory policy was `manual`, so agents had to be explicitly told to archive. That is backwards for a tool whose job is to keep context clean.

Status after this audit: patched.

- Default memory policy is now `on_record`.
- Setup templates now scaffold `archive_mode: on_record`.
- `archive_on_record()` can also trigger from file-size pressure even when an older project still says `manual`.

Remaining gap: size pressure currently triggers count-based compaction. It does not yet guarantee the final hot file is under `max_acts_bytes`.

### 4. `acts.lock` Was Polluting Projects

State reads and writes used a visible sidecar lock next to `acts.yaml`, which created empty `acts.lock` files in project trees.

Status after this audit: patched.

- Lock files now live under the system temp directory using a hashed path.
- The zero-byte lock fixtures at `temp/acts.lock` and `testhaxaml/acts.lock` were removed.
- A regression test now asserts that reading state does not create `acts.lock` in the project directory.

### 5. Setup Wizard Can Show Codex But Install Generic

The copied `testhaxaml` setup state proves the target bug:

- `detected_targets`: `codex`, `opencode`, `windsurf`.
- `selected_targets`: `generic`.
- `strong_detected_targets`: empty.
- `weak_detected_targets`: `codex`, `opencode`, `windsurf` from shared `AGENTS.md`.

The wizard displays weak Codex evidence like a selectable target, but the default path can still fall back to `generic`. There is also a shared `SKILL.md` path collision where generic skill output can be planned before provider-specific skill output.

Game analogy: the menu showed the Codex operator skin, then spawned the player as the default recruit.

Impact: users cannot trust setup output. This is release-critical because setup is the first handshake between Haxaml and the agent.

Fix direction:

- The wizard must separate `detected`, `recommended`, and `selected`.
- Weak shared files like `AGENTS.md` must never auto-select Codex, Windsurf, or OpenCode.
- If only weak evidence exists, the wizard must ask explicitly and show what will be installed.
- Provider-specific skill output must win over generic output when a provider is selected.
- The final confirmation must show exact targets, paths, and previews before writing.

### 6. Setup Is Not Safely Idempotent Yet

Rerunning setup over an active project is not a guaranteed no-op. Existing FRAME files may be skipped in normal mode because they are not Haxaml-marked, but a broad force flow can replace populated state with blank templates.

Impact: the user can lose active project memory, which is the worst possible failure for a governance tool.

Fix direction:

- Setup must treat `.haxaml/facts.yaml`, `.haxaml/acts.yaml`, `.haxaml/rules.yaml`, `.haxaml/map.yaml`, and `.haxaml/expect.yaml` as protected state.
- The default setup path should create missing files only.
- Repair should patch schema gaps, not reset content.
- Destructive reset should require a separate explicit command like `haxaml setup reset-frame` or `--reset-frame`.
- `--force` should be scoped to adapters or workflow assets, not blanket FRAME replacement.

### 7. Lifecycle Gates Are Too Advisory

README says the agent should stop for missing materials, vague intent, or high-risk work. Current prebuild and context-pack flow can still return advisory questions and then allow agents to continue.

Impact: Haxaml can tell the agent the right thing without forcing the right thing. That is not deterministic enough for 1.0.

Fix direction:

- Add a first-class Blueprint or PrebuildGate object.
- Required questions need answer records.
- Required materials need receipts.
- `context_pack` should issue a build permit only when gates are satisfied.
- Verification should compare changed files and evidence against the blueprint.

## Immediate Patch Status

This audit produced a small immediate code patch, not the full 1.0 refactor.

- Default archiving changed from manual to on-record.
- Size pressure can trigger compaction for older manual projects.
- Project-local `acts.lock` creation was removed.
- Setup scaffolds now default to `archive_mode: on_record`.
- Regression tests were added for the lock behavior and size-triggered archive behavior.

## Before 1.0

These must be treated as blockers, not polish:

- Hot Acts must obey a real byte budget.
- Archive must stop duplicating bulky searchable state.
- Setup must be idempotent by design.
- Target selection must be explicit and preview-first.
- Prebuild questions and materials must become hard gates.
- Verification must require evidence tied to the actual blueprint.
- Tests must cover the bad real-world fixture shapes, not only clean happy paths.

## Sources

- OpenAI explains that prompt caching depends on exact prompt prefixes and that Codex uses automatic compaction once context grows too large: [Unrolling the Codex agent loop](https://openai.com/index/unrolling-the-codex-agent-loop/).
- OpenAI prompt caching docs recommend stable static content first and variable content later: [Prompt caching](https://developers.openai.com/api/docs/guides/prompt-caching).
- Anthropic recommends simple, composable workflows before adding open-ended agent autonomy: [Building effective agents](https://www.anthropic.com/engineering/building-effective-agents).
- MCP supports structured user input through elicitation, which maps directly to Haxaml's missing-context gates: [MCP elicitation](https://modelcontextprotocol.io/specification/2025-06-18/client/elicitation).
- LangChain summarizes context engineering as write, select, compress, and isolate: [Context Engineering](https://www.langchain.com/blog/context-engineering-for-agents).
