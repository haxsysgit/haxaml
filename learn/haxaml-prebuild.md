# haxaml_prebuild — Task Classification & Semantic Validation

New in Haxaml 0.6.

`haxaml_prebuild` is an optional lifecycle phase that runs between `haxaml_guidance` and `haxaml_session_start`. It classifies the task, runs semantic validation against FRAME, and produces a readiness report.

## When to Call It

Call `haxaml_prebuild` for:

- Refactor, migration, or architecture tasks (high impact, high complexity)
- Any task where FRAME quality directly affects agent accuracy
- Any task the agent needs to classify before choosing context strategy

Skip for simple utility tasks (fix a typo, run a command). Utility mode detection is automatic — `haxaml_prebuild` will short-circuit with `utility_mode` status.

## Lifecycle Position

```
about -> guidance -> prebuild (optional) -> session_start -> session_plan -> context_pack -> ...
```

When `haxaml_prebuild` is called successfully, the lifecycle contract advances to allow `haxaml_context_pack` to be called directly (skipping the normal session_start/plan requirement only for context pack ordering; session_start is still required before verify/record).

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
    "readiness": "ready",
    "task_type": "feature",
    "template": "feature_implementation",
    "session_id": "ses-abc123",
    "blocking_issues": [],
    "advisory_warnings": ["facts.goal.scope is missing"],
    "required_questions": ["What is the expected interface contract for this feature?"],
    "context_policy": "balanced",
    "message": "..."
  }
}
```

When `detail="full"`, `data.template_detail` includes the full template definition.

## Readiness Values

| Value | Meaning |
|-------|---------|
| `ready` | FRAME is valid and complete; proceed to session_start |
| `ready_with_warnings` | FRAME has advisory gaps; agent should note warnings |
| `blocked` | FRAME has semantic blocking issues; fix before proceeding |
| `utility_mode` | Task is off-topic or utility; skip governed lifecycle |

## Task Types (12 Templates)

Each template defines: required context questions, done criteria, risk signals, and context pack policy.

| Task Type | Template Key |
|-----------|--------------|
| Feature implementation | `feature_implementation` |
| Bug fix | `bug_fix` |
| Refactoring | `refactoring` |
| Testing | `testing` |
| Documentation | `documentation` |
| Configuration | `configuration` |
| Database migration | `database_migration` |
| API design | `api_design` |
| Performance optimization | `performance_optimization` |
| Security audit | `security_audit` |
| Dependency upgrade | `dependency_upgrade` |
| Architecture decision | `architecture_decision` |

Classification is keyword-based. If no template matches, `feature_implementation` is used as the fallback.

## Semantic Validation

`haxaml_prebuild` runs `semantic_validate(FrameModel.load(project_dir))` before the readiness report.

**Blocking issues** (surfaced in `data.blocking_issues`):
- `facts.identity` section absent
- `facts.identity.name` key absent
- `facts.goal` section absent
- `facts.goal.purpose` key absent
- `active_task` set but all sessions closed (stale lifecycle state)
- `expect.yaml` run marked active but no matching `acts` record

**Advisory warnings** (surfaced in `data.advisory_warnings`):
- Empty `identity.name` or `goal.purpose` (valid for fresh scaffolds, should be filled in)
- Missing `identity.description`, `goal.scope`, `goal.out_of_scope`
- Very short (≤2 word) rule values

`haxaml_validate` and `haxaml_doctor` also surface these through the same semantic pipeline.

## Error Codes

| Code | Cause |
|------|-------|
| `lifecycle_contract_violation` | Called before `haxaml_guidance` |
| `missing_facts` | `facts.yaml` not found |
| `semantic_blocking` | Blocking semantic issues; see `error.details.blocking_issues` |

## Example Call

```python
haxaml_prebuild(
    task="Refactor the authentication module to support OAuth2",
    project_dir=".",
    detail="short",
)
```

Expected response pattern:
- `data.readiness` == `"ready"` or `"ready_with_warnings"`
- `data.task_type` == `"refactoring"`
- `data.template` == `"refactoring"`
- `data.session_id` — use this in subsequent `haxaml_session_start` call
- `data.required_questions` — answer before coding if present
- `data.context_policy` — suggested pack level (`minimal`, `balanced`, `comprehensive`)

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
