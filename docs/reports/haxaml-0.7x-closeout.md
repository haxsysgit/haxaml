# Haxaml `0.7.x` Close-Out

Date: 2026-05-19

`0.7.x` was the setup, workflow, and trust line. It started with "how does Haxaml install into this repo?" and ends with "can an agent actually enter the governed flow without the setup, state, or release machinery feeling sketchy?"

Short answer: the line is ready to close. The remaining work is not another `0.7.x` patch train. It belongs to `0.8.0`, where FRAME and the governance protocol can change shape deliberately.

## Review Slices

This close-out reviewed the shipped line in three slices:

- Setup and TUI: setup engine, target planning, provider evidence, reruns, doctor output, and the terminal wizard.
- Lifecycle and state: hot `acts.yaml`, archive compaction, runtime cache behavior, MCP lifecycle gates, and handoff summaries.
- Release and docs: version alignment, PyPI publishing, GitHub release plumbing, roadmap consistency, and public docs.

The point was to close the line from evidence, not from vibes.

## What `0.7.x` Finished

### Setup Is Now A Real Entry Point

`0.7.0` created the setup package and made `haxaml setup` the onboarding command. Later releases made that setup flow provider-aware, inspectable, and safer to rerun.

Done:

- `haxaml setup`, `haxaml setup print`, and `haxaml setup doctor` are the setup-owned entry points.
- Setup planning uses one target registry instead of scattered provider rules.
- Explicit `--targets` selection wins over weak shared evidence.
- `generic` is fallback behavior, not something that should silently override a selected provider.
- Known MCP config shapes merge only the Haxaml-owned entry.
- Existing native instruction files can be adopted with managed pointer blocks instead of overwritten.
- Interactive setup now reads like a scaffold command instead of a raw prompt chain.

Evidence:

- `haxaml/setup/planner.py`
- `haxaml/setup/service.py`
- `haxaml/setup/interactive.py`
- `haxaml/setup/doctor.py`
- `tests/test_cli.py`
- `tests/test_setup_docs.py`

### Workflow Accommodation Exists Where The Surface Is Real

The line added workflow outputs without pretending every vendor UI is automatable.

Done:

- `workflow` is a first-class setup asset category.
- Workflow checks have CLI-safe output for project automation.
- Provider-specific workflow assets exist where the integration point is file-backed or config-backed.
- Unsupported or UI-only surfaces stay advisory.

Evidence:

- `haxaml/setup/registry.py`
- `haxaml/setup/workflow.py`
- `haxaml/cli.py`
- `0.7.x_Roadmap.md`

### Hot State Is Usable Again

The original state problem was simple: hot `acts.yaml` was turning into a replay archive. `0.7.5` moved the design toward active continuity instead.

Done:

- Hot Acts compaction is byte-pressure aware, not only count-based.
- Completed task history is bounded as compact stubs.
- Recent decisions stay hot, but old detail moves cold.
- Archive reads are shallow by default and hydrate details only when requested.
- Legacy archive input remains readable for older projects.
- Hot state carries a compact continuity summary for the next agent.

Evidence:

- `haxaml/state_manager.py`
- `haxaml/acts_archive.py`
- `haxaml/runtime_cache.py`
- `tests/test_state_manager.py`
- `tests/test_runtime_cache.py`

### Lifecycle Gates Got Less Advisory

`0.7.x` did not finish every enforcement goal, but it did move obvious blockers into the governed path.

Done:

- Structured blocking materials can stop prebuild progress.
- Structured blocking questions can stop prebuild progress.
- Context pack re-checks blockers instead of trusting stale session state.
- Handoff summaries now surface blockers, decisions, failure context, and context pressure.

Evidence:

- `haxaml/mcp/tools_prebuild.py`
- `haxaml/mcp/tools_lifecycle.py`
- `haxaml/mcp/lifecycle_helpers.py`
- `tests/mcp/test_lifecycle.py`

### Release Plumbing Is Less Fragile

The `0.7.6` publish failure showed one real operator footgun: a tag-triggered publish should not fail halfway through when PyPI already has the exact version.

Done in `0.7.7`:

- `publish.yml` checks PyPI before upload.
- Package publish steps skip exact versions that already exist.
- Version validation still runs before release publishing.
- Core, MCP, and UI package versions stay aligned.

Evidence:

- `.github/workflows/publish.yml`
- `haxaml/versioning.py`
- `scripts/bump_version.py`
- `tests/test_versioning.py`

## Rough Edges Deferred To `0.8.0`

These are real, but they should not keep `0.7.x` open:

- Legacy archive compatibility is still present. That bridge should be kept until `0.8` has migration helpers.
- `setup doctor` is advisory. Stricter governance belongs in explicit checks and protocol gates, not surprise doctor failures.
- Some provider integrations still require manual follow-up because their stable public surface is not file-backed enough.
- `--force` remains a broad setup option. A sharper FRAME reset story belongs with `0.8` migration and protocol work.
- Plain string materials/questions remain advisory for compatibility. Full structured gate semantics belong to `0.8`.
- Verification still needs a stronger blueprint comparison model before "no evidence, no done" is truly enforced.

## `0.8.0` Handoff

`0.8.0` should not spend its energy rediscovering the setup and state problems from this line. It should start from the settled `0.7.x` contract:

- Setup is the onboarding surface.
- Workflow accommodation routes real provider assets into the Haxaml lifecycle.
- Hot Acts state is active continuity, not archive replay.
- Archive keeps cold evidence and hydrates detail selectively.
- Blocking metadata can stop progress when it is structured.
- Release automation validates versions and avoids duplicate PyPI uploads.

The next line can now focus on FRAME itself:

- mature `expect.yaml` into the project-level governed run guideline
- define stronger boundaries for Facts, Rules, Acts, Map, and Expect
- add first-class blueprint / prebuild gate semantics
- make materials receipts and question answers explicit
- compare verification evidence against planned scope
- add migration helpers for older FRAME projects

## Close-Out Criteria

`0.7.x` is done when:

- the roadmap names `0.7.7` as the final close-out release
- this close-out report is linked from public docs
- the changelog explains the release as a wrap-up and handoff
- package versions are aligned at `0.7.7`
- tag-triggered publishing can no-op cleanly for already-published package versions

