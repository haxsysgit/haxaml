# haxaml_prebuild — Task Classification & Semantic Validation

`haxaml_prebuild` is the recommended high-level lifecycle phase that runs after `haxaml_guidance`. It classifies the task, runs semantic validation against FRAME, opens the governed session internally, and produces a readiness report.

## When to Call It

Call `haxaml_prebuild` for:

- Refactor, migration, or architecture tasks (high impact, high complexity)
- Any task where FRAME quality directly affects agent accuracy
- Any task the agent needs to classify before choosing context strategy

Skip for simple utility tasks (fix a typo, run a command). Utility mode detection is automatic — `haxaml_prebuild` will short-circuit with `utility_mode` status.

## Lifecycle Position

```
about -> guidance -> prebuild -> context_pack -> ...
```

When `haxaml_prebuild` succeeds, it already creates the governed session and advances the lifecycle contract to `haxaml_context_pack`. In the recommended path, you do not need a separate `session_start` or `session_plan` call afterward.

The lower-level `session_start` and `session_plan` tools still exist for advanced/manual flows.

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
    "frame_health": {
      "blocking": [],
      "warnings": ["facts.goal.scope is missing"]
    },
    "required_questions": ["What is the expected interface contract for this feature?"],
    "context_policy": {
      "recommended_pack": "balanced"
    },
    "message": "..."
  }
}
```

The full payload also includes `classification_reason`, `materials_needed`, `done_criteria`, `likely_impact`, `risks`, `plan`, `verification_expectations`, and `next_step`.

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

## PromptRecipe Export Pipeline (0.6)

The export engine now routes all exports through a `PromptRecipe` pipeline:

```
FrameModel.load() -> build_recipe(frame, agent) -> _render_recipe(recipe) -> Markdown
```

`PromptRecipe` is the normalised intermediate representation. Sections are keyed, ordered, and filterable:

```python
from haxaml.export_engine import build_recipe, _render_recipe
from haxaml.frame_model import FrameModel

frame = FrameModel.load(".")
recipe = build_recipe(frame, "generic")
# Inspect sections:
for s in recipe.sections:
    print(s.key, s.title)
# Exclude a section:
trimmed = recipe.exclude("acts")
output = _render_recipe(trimmed)
```

This makes export deterministic and testable without a filesystem, and allows targeted section manipulation for custom agent adapters.
