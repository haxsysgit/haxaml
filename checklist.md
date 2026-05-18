# Haxaml 1.0 Readiness Checklist

This checklist is the practical lock-in list before 1.0. It tracks what still needs to become mechanically true in the governed system.

The product vision lives in [goals.md](./goals.md). This file is only the readiness tracker.

Status legend:

- `[x]` done or patched enough to protect the current behavior
- `[~]` partially true, but still not release-safe
- `[ ]` missing or not enforced

## Level 0: Immediate Firebreaks

- [x] Default new FRAME projects to `memory_policy.archive_mode: on_record`.
- [x] Let size pressure trigger archive on record for older projects that still say `manual`.
- [x] Stop creating project-local `acts.lock` files.
- [x] Remove the copied zero-byte `acts.lock` fixtures from this repo.
- [x] Add regression tests for no project-local lock files.
- [x] Add regression tests for size-pressure archiving.
- [x] Add setup scaffold test coverage for `archive_mode: on_record`.

## Level 1: Acts And Archive Must Stop Eating Context

- [~] Hot `acts.yaml` keeps recent runs, sessions, and verifications capped by count.
- [ ] Hot `acts.yaml` must obey `max_acts_bytes` after compaction, not only warn about it.
- [x] `completed_tasks` must be capped, summarized, or archived.
- [ ] Verbose run/session/verification bodies must move cold while hot state keeps stubs.
- [ ] Archive index entries must be short enough to stay search-friendly.
- [ ] Archive storage must avoid full-file rewrite on every append.
- [ ] Archive index must be rebuildable from history.
- [ ] Short context fetch must not hydrate full archive records and then drop them.
- [ ] Context pack should compute sections, hints, and markers once per call.

## Level 2: Setup Must Be Trustworthy

- [~] `haxaml setup` has an interactive path.
- [ ] Wizard UI must clearly show selected target, detected evidence, planned files, and previews.
- [ ] Weak shared evidence like `AGENTS.md` must never auto-select multiple providers.
- [ ] Codex selection must never silently install generic output.
- [ ] Provider-specific skills must not be shadowed by shared generic skill paths.
- [ ] Running setup twice over an active project must be a no-op by default.
- [ ] FRAME files must be create-missing or schema-repair only.
- [ ] Destructive reset must require an explicit reset command or reset-specific flag.
- [ ] `--force` must be scoped to adapters/workflow assets, not full FRAME state.
- [ ] Dry-run and apply output must show the same planned path list.

## Level 3: Lifecycle Must Become A Real Gate

- [~] `about -> guidance -> prebuild -> context_pack -> verify -> record -> expect_sync` exists.
- [ ] `prebuild` must create a structured Blueprint or PrebuildGate.
- [ ] Required user questions must block build until answered or explicitly waived.
- [ ] Required materials must have receipts before build.
- [ ] `context_pack` must issue a build permit only when blocking gates pass.
- [ ] The build permit must carry planned files/modules, done criteria, and verification obligations.
- [ ] Verification must compare changed files against planned scope.
- [ ] Verification must compare inspected context against required reads.
- [ ] Record must reject stale, missing, failed, or unrelated verification.
- [ ] Agents must get a clear "stop and ask the user" response when gates are blocked.

## Level 4: Context Engineering Must Be Measurable

- [~] Context packs avoid full-file dumps by default.
- [~] Archive retrieval exists for follow-up memory.
- [ ] Every context pack should report budget, selected sources, omitted sources, and why.
- [ ] Stable instructions should stay separate from variable task data for prompt-cache friendliness.
- [ ] Haxaml adapters should keep provider instruction files short and point into governed flow.
- [ ] Subagent or parallel-work guidance should isolate heavy investigation from active build context.
- [ ] Hot state should contain only what the next agent needs to continue.
- [ ] Cold state should preserve details without entering context unless requested.

## Level 5: Tests Must Simulate Real Damage

- [~] CLI, MCP functions, setup rendering, validation, and state manager basics are tested.
- [ ] Large `acts.yaml` fixtures must prove hot state stays under budget.
- [ ] Setup rerun tests must prove active `.haxaml` state is preserved.
- [ ] Wizard tests must simulate target selection and weak-only evidence.
- [ ] Codex selected must mean Codex installed.
- [ ] Config merge tests must cover malformed TOML/JSON and unknown shapes.
- [ ] Lifecycle state-machine tests must cover blocked questions/materials and bad order.
- [ ] Verification tests must require actual evidence receipts, not only claimed summaries.
- [ ] MCP tests must include real stdio/client contract coverage.
- [ ] Docs examples must be executable or snapshot-checked.

## Level 6: Docs And Product Story

- [x] README states the core philosophy: no planning, no building.
- [x] `0.7.x_Roadmap.md` names `0.7.4` as the setup UX release.
- [x] `v1.0_Roadmap.md` is the stable-kernel path.
- [x] Audit reports exist for bugs, vision, and test strategy.
- [ ] README must avoid claiming setup behavior as fully solved until idempotency and target selection are fixed.
- [ ] Changelog must separate shipped fixes from planned hardening.
- [ ] Provider-specific claims must stay tied to official docs or be marked guidance-only.
- [ ] Release notes must call out state/archive migration risks clearly.

## 1.0 Go / No-Go

Haxaml is a go for 1.0 only when:

- [ ] A real adopted project can run setup twice without losing state.
- [ ] The selected provider is exactly the provider installed.
- [ ] Hot `acts.yaml` remains small after repeated work.
- [ ] Missing user answers block build.
- [ ] Missing materials block build.
- [ ] Verification requires evidence tied to the plan.
- [ ] The next agent can continue from Haxaml without rereading the whole repo.

If any of those fail, the release is still beta-level governance, not a stable kernel.
