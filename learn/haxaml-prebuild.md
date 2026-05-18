# haxaml_prebuild — Task Classification & Semantic Validation

`haxaml_prebuild` is the recommended high-level lifecycle phase that runs after `haxaml_guidance`. It classifies the task, runs semantic validation against FRAME, opens the governed session internally, and produces a readiness report.

Use [haxaml-mcp.md](./haxaml-mcp.md) for the full governed operator flow. This page stays focused on what `prebuild` itself decides.

## When to Call It

Call `haxaml_prebuild` for:

- Refactor, migration, or architecture tasks (high impact, high complexity)
- Any task where FRAME quality directly affects agent accuracy
- Any task the agent needs to classify before choosing context strategy

Skip for simple utility tasks (fix a typo, run a command). Utility mode detection is automatic — `haxaml_prebuild` will short-circuit with `utility_mode` status.

## Lifecycle Position

`haxaml_prebuild` sits between task classification and context loading. When it succeeds, it already creates the governed session and advances the lifecycle contract to `haxaml_context_pack`.

## Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `task` | required | Task description string |
| `project_dir` | `"."` | Path to the project root |
| `detail` | `"short"` | `short` or `full` |

## Response Payload (short)

```json
{
  "ok": true,
  "tool": "haxaml_prebuild",
  "data": {
    "readiness_status": "ready_to_build_with_warnings",
    "task_type": "api_endpoint",
    "guidance_type": "implementation",
    "session_id": "session-abc123",
    "required_questions": ["What is the expected interface contract for this feature?"],
    "message": "..."
  }
}
```

The full payload also includes `classification_reason`, `materials_needed`, `done_criteria`, `likely_impact`, `risks`, `plan`, `verification_expectations`, `frame_health`, `context_policy`, and `next_step`.

## Readiness Values

| Value | Meaning |
|-------|---------|
| `ready_to_build` | FRAME is ready; proceed to `haxaml_context_pack` |
| `ready_to_build_with_warnings` | FRAME has advisory gaps; proceed, but carry the warnings |
| `needs_user_input` | Required questions must be answered before governed build work |
| `needs_project_inspection` | More local inspection is needed before the task is ready |
| `blocked_by_missing_context` | FRAME is missing blocking information |
| `blocked_by_policy` | Lifecycle or policy issues block the task |
| `utility_mode` | Task is off-topic or utility; skip governed lifecycle |

## Task Types (12 Templates)

Each template defines: required context questions, done criteria, risk signals, and context pack policy.

| Task Type | Template Key |
|-----------|--------------|
| Authentication | `authentication` |
| Payment | `payment` |
| API endpoint | `api_endpoint` |
| Database migration | `database_migration` |
| Bug fix | `bug_fix` |
| Refactor | `refactor` |
| Testing | `testing` |
| Documentation | `documentation` |
| CLI command | `cli_command` |
| MCP integration | `mcp_integration` |
| Frontend feature | `frontend_feature` |
| Deployment | `deployment` |

Classification is keyword-based. If no template matches, `api_endpoint` is used as the fallback.

## Semantic Validation

`haxaml_prebuild` runs `semantic_validate(FrameModel.load(project_dir))` before the readiness report.

**Blocking issues** (surfaced in `data.frame_health.blocking`):
- `facts.identity` section absent
- `facts.identity.name` key absent
- `facts.goal` section absent
- `facts.goal.purpose` key absent
- `active_task` set but all sessions closed (stale lifecycle state)
- `expect.yaml` run marked active but no matching `acts` record

**Advisory warnings** (surfaced in `data.frame_health.warnings`):
- Empty `identity.name` or `goal.purpose` (valid for fresh scaffolds, should be filled in)
- Missing `identity.description`, `goal.scope`, `goal.out_of_scope`
- Very short (≤2 word) rule values

`haxaml_validate` and `haxaml_doctor` also surface these through the same semantic pipeline.

## Error Codes

| Code | Cause |
|------|-------|
| `about_required` | `haxaml_about` was not called in the active MCP session |
| `lifecycle_contract_violation` | Called out of order, usually before `haxaml_guidance` |
| `missing_facts` | `facts.yaml` not found |

## Example Call

```python
haxaml_prebuild(
    task="Refactor the authentication module to support OAuth2",
    project_dir=".",
    detail="short",
)
```

Expected response pattern:
- `data.readiness_status` == `"ready_to_build"` or `"ready_to_build_with_warnings"`
- `data.task_type` matches the classified template, for example `"authentication"` or `"api_endpoint"`
- `data.guidance_type` maps to the abstract workflow profile
- `data.session_id` — use this in subsequent `haxaml_context_pack` / verify / record calls
- `data.required_questions` — answer before coding if present
- `data.context_policy` — suggested context scope and pack policy

## Integration with haxaml_validate and haxaml_doctor

The same `semantic_validate` function is called by:

- `haxaml_validate` — blocking semantic errors cause validation failure
- `haxaml_doctor` — blocking and advisory issues are reported as recommendations
- `haxaml_prebuild` — blocking issues prevent readiness; advisory issues are forwarded as warnings

This means semantic quality gaps surface at all three checkpoints in the lifecycle:
pre-build (classification), build-gate (validate), and completeness-check (doctor).
