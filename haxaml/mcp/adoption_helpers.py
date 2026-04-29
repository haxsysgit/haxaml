"""MCP adoption helper functions."""

from typing import Any

from haxaml.adoption import (
    analyze_adoption_instructions,
    scan_native_sources,
)


def _adoption_plan_payload(project_dir: str, plan: Any = None) -> tuple[dict[str, Any], list[str]]:
    plan = plan or scan_native_sources(project_dir)
    analysis = analyze_adoption_instructions(plan)
    native_files = [{"kind": f.kind, "label": f.label, "path": f.path} for f in plan.native_files]
    context_files = [{"kind": f.kind, "label": f.label, "path": f.path} for f in plan.context_files]
    risks = []
    if len(native_files) >= 3:
        risks.append("Multiple native instruction sources detected; precedence conflicts are likely.")
    if plan.existing_frame_files:
        risks.append("Existing FRAME files detected; preserve unless explicit overwrite is requested.")
    if not native_files and not context_files:
        risks.append("No known native/context files were discovered; adoption may require manual context capture.")
    if analysis["counts"]["conflicts"] > 0:
        risks.append("Instruction conflicts detected; explicit precedence decision is required before FRAME derivation.")

    migration_steps = [
        "Run haxaml_reconcile to detect derivation boundary conflicts.",
        "Decide precedence for conflicting native instructions before editing FRAME.",
        "Fill/update FRAME files from evidence, then run haxaml_validate.",
        "Export native files from FRAME only after validate passes.",
    ]
    next_actions = [
        "Call haxaml_reconcile(project_dir='.')",
        "Resolve blocking conflicts from reconcile report.",
        "Choose authoritative instruction source(s) where adoption conflicts exist.",
        "Call haxaml_validate(project_dir='.')",
    ]
    conflict_count = analysis["counts"]["conflicts"]
    duplicate_count = analysis["counts"]["duplicates"]
    precedence_required = analysis["precedence_decision_required"]
    human_summary = (
        f"Inventory complete: {len(native_files)} native file(s), "
        f"{len(context_files)} context file(s), {len(plan.existing_frame_files)} existing FRAME file(s). "
        f"Instruction analysis: {conflict_count} conflict(s), {duplicate_count} duplicate rule group(s), "
        f"precedence decision required: {'yes' if precedence_required else 'no'}."
    )
    warnings = []
    if conflict_count:
        warnings.append(
            f"Adoption instruction conflicts detected ({conflict_count}); choose authoritative source before deriving FRAME."
        )
    if duplicate_count:
        warnings.append(
            f"Adoption duplicate rule groups detected ({duplicate_count}); consolidate to reduce instruction drift."
        )

    payload = {
        "project_dir": str(plan.project_dir),
        "native_files": native_files,
        "context_files": context_files,
        "existing_frame_files": list(plan.existing_frame_files),
        "counts": {
            "native_files": len(native_files),
            "context_files": len(context_files),
            "existing_frame_files": len(plan.existing_frame_files),
        },
        "instruction_analysis": analysis,
        "migration_plan": migration_steps,
        "risk_notes": risks,
        "next_actions": next_actions,
        "non_destructive": True,
        "human_summary": human_summary,
    }
    return payload, warnings
