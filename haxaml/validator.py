"""FRAME model validation against schemas (facts/rules/acts/map/expect)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml
from jsonschema import Draft202012Validator

from haxaml.acts_archive import ActsArchive, ArchiveError, archive_metadata, normalize_memory_policy
from haxaml.lifecycle_state import expect_sync_state as _base_expect_sync_state
from haxaml.utils import normalized_text
from haxaml.yaml_utils import load_yaml as _load_yaml_file

if TYPE_CHECKING:
    from haxaml.frame_model import FrameModel


_normalized_text = normalized_text


@dataclass
class SemanticValidationResult:
    """Result of semantic_validate().

    blocking: hard errors — haxaml_validate should return ok=false for these.
    warnings: quality gaps — haxaml_doctor surfaces these; agents can still proceed.
    """
    blocking: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def is_clean(self) -> bool:
        return not self.blocking and not self.warnings

    def has_blocking(self) -> bool:
        return bool(self.blocking)


@dataclass
class ConsistencyFinding:
    """Deterministic advisory or blocking finding derived from existing FRAME."""

    code: str
    severity: str
    area: str
    message: str
    hint: str = ""
    paths: list[str] = field(default_factory=list)


def _normalized_task_name(value: Any) -> str:
    if isinstance(value, dict):
        value = value.get("name", "")
    text = _normalized_text(value).lower()
    return "" if text in {"", "none", "null"} else text


def _normalized_session_task(value: Any) -> str:
    if isinstance(value, dict):
        value = value.get("task", value.get("name", ""))
    text = _normalized_text(value).lower()
    return "" if text in {"", "none", "null"} else text


def _open_sessions(acts: dict[str, Any]) -> list[dict[str, Any]]:
    sessions = acts.get("sessions") or []
    if not isinstance(sessions, list):
        return []
    open_statuses = {"started", "planned", "acting", "verified"}
    return [
        session
        for session in sessions
        if isinstance(session, dict) and _normalized_text(session.get("status", "")).lower() in open_statuses
    ]


def _recorded_sessions(acts: dict[str, Any]) -> list[dict[str, Any]]:
    sessions = acts.get("sessions") or []
    if not isinstance(sessions, list):
        return []
    final_statuses = {"recorded", "failed"}
    return [
        session
        for session in sessions
        if isinstance(session, dict) and _normalized_text(session.get("status", "")).lower() in final_statuses
    ]


def _expect_sync_state(acts: dict[str, Any]) -> dict[str, str | bool]:
    state = _base_expect_sync_state(acts)
    return {
        "required": bool(state.get("required", False)),
        "pending_run_id": _normalized_text(state.get("pending_run_id", "")),
        "pending_run_number": int(state.get("pending_run_number", 0) or 0),
        "pending_task": _normalized_text(state.get("pending_task", "")),
        "pending_result": _normalized_text(state.get("pending_result", "")),
        "last_synced_run_id": _normalized_text(state.get("last_synced_run_id", "")),
        "last_synced_run_number": int(state.get("last_synced_run_number", 0) or 0),
    }


def _archive_run_ids(project_dir: Path, acts: dict[str, Any]) -> tuple[set[str], list[str]]:
    meta = archive_metadata(acts)
    archive_path = meta.get("path", "")
    archived_total = sum(int(meta.get("archived_counts", {}).get(key, 0) or 0) for key in ("runs", "sessions", "verifications"))
    if not archive_path and archived_total <= 0:
        return set(), []

    archive = ActsArchive(project_dir)
    expected_path = archive.path.resolve()
    actual_path = (project_dir / archive_path).resolve() if archive_path and not Path(archive_path).is_absolute() else Path(archive_path).resolve() if archive_path else expected_path
    if archive_path and actual_path != expected_path:
        return set(), [f"acts.archive.path points to '{archive_path}' but expected '{archive.path}'."]
    if archived_total > 0 and not archive.exists():
        return set(), [f"acts.archive reports archived history but '{archive.path}' is missing."]

    try:
        entries = archive.index_entries()
    except ArchiveError as exc:
        return set(), [f"Archive history is unreadable: {exc}"]

    run_ids = {
        _normalized_text(item.get("id", ""))
        for item in entries
        if isinstance(item, dict) and _normalized_text(item.get("kind", "")) == "run" and _normalized_text(item.get("id", ""))
    }
    return run_ids, []


def frame_consistency_report(frame: "FrameModel") -> dict[str, Any]:
    """Return deterministic consistency findings and a derived progress summary."""

    facts: dict[str, Any] = frame.facts or {}
    rules: dict[str, Any] = frame.rules or {}
    acts: dict[str, Any] = frame.acts or {}
    expect: dict[str, Any] = frame.expect or {}
    memory_policy = normalize_memory_policy((rules.get("memory_policy") or {}))
    project_dir = Path(getattr(frame, "project_dir", Path(".")))
    memory_policy = normalize_memory_policy((rules.get("memory_policy") or {}))
    project_dir = Path(getattr(frame, "project_dir", Path(".")))
    findings: list[ConsistencyFinding] = []
    project_dir = getattr(frame, "project_dir", Path("."))

    phases = [item for item in (expect.get("phases") or []) if isinstance(item, dict)]
    phase_names = {_normalized_text(item.get("name", "")) for item in phases if _normalized_text(item.get("name", ""))}
    active_phases = [
        _normalized_text(item.get("name", ""))
        for item in phases
        if _normalized_text(item.get("status", "")).lower() == "active" and _normalized_text(item.get("name", ""))
    ]
    done_phases = {
        _normalized_text(item.get("name", ""))
        for item in phases
        if _normalized_text(item.get("status", "")).lower() == "done" and _normalized_text(item.get("name", ""))
    }
    runbook = [item for item in (expect.get("runbook") or []) if isinstance(item, dict)]
    done_runs = {
        int(item.get("run"))
        for item in runbook
        if isinstance(item.get("run"), int) and _normalized_text(item.get("status", "")).lower() == "done"
    }
    active_runs = [
        item for item in runbook if _normalized_text(item.get("status", "")).lower() == "active"
    ]

    for run in active_runs:
        run_no = run.get("run")
        phase_name = _normalized_text(run.get("phase", ""))
        if phase_name and phase_names and phase_name not in phase_names:
            findings.append(
                ConsistencyFinding(
                    code="run_unknown_phase",
                    severity="warning",
                    area="run_phase_coherence",
                    message=(
                        f"expect.yaml run {run_no} references phase '{phase_name}' "
                        "that is not declared in expect.phases."
                    ),
                    hint="Add the missing phase entry or move the run to a declared phase.",
                    paths=[".haxaml/expect.yaml:phases", ".haxaml/expect.yaml:runbook"],
                )
            )
        if active_phases and phase_name and phase_name not in active_phases:
            findings.append(
                ConsistencyFinding(
                    code="active_phase_run_mismatch",
                    severity="warning",
                    area="run_phase_coherence",
                    message=(
                        f"expect.yaml run {run_no} is active in phase '{phase_name}' "
                        f"but active phases are {active_phases}."
                    ),
                    hint="Align the run status with the active phase, or move the phase status forward.",
                    paths=[".haxaml/expect.yaml:phases", ".haxaml/expect.yaml:runbook"],
                )
            )
        unmet = [
            dep for dep in (run.get("depends_on") or [])
            if isinstance(dep, int) and dep not in done_runs
        ]
        if unmet:
            findings.append(
                ConsistencyFinding(
                    code="active_run_unmet_dependencies",
                    severity="warning",
                    area="run_phase_coherence",
                    message=(
                        f"expect.yaml run {run_no} is active but still depends on unfinished run(s): {unmet}."
                    ),
                    hint="Mark prerequisites done or return this run to planned/blocked until they are complete.",
                    paths=[".haxaml/expect.yaml:runbook"],
                )
            )

    for phase_name in sorted(done_phases):
        conflicting_runs = [
            item.get("run")
            for item in runbook
            if _normalized_text(item.get("phase", "")) == phase_name
            and _normalized_text(item.get("status", "")).lower() in {"planned", "active"}
        ]
        if conflicting_runs:
            findings.append(
                ConsistencyFinding(
                    code="done_phase_has_open_runs",
                    severity="warning",
                    area="run_phase_coherence",
                    message=(
                        f"expect.yaml phase '{phase_name}' is marked done while run(s) {conflicting_runs} "
                        "under that phase are still planned or active."
                    ),
                    hint="Either reopen the phase or close the remaining runs underneath it.",
                    paths=[".haxaml/expect.yaml:phases", ".haxaml/expect.yaml:runbook"],
                )
            )

    active_task = _normalized_task_name(acts.get("active_task"))
    open_sessions = _open_sessions(acts)
    latest_open_session = open_sessions[-1] if open_sessions else None
    latest_open_task = _normalized_session_task(latest_open_session or {})
    if active_task and latest_open_task and active_task != latest_open_task:
        findings.append(
            ConsistencyFinding(
                code="active_task_session_mismatch",
                severity="warning",
                area="session_state_coherence",
                message=(
                    f"acts.active_task is '{active_task}' but the latest open session is "
                    f"for '{latest_open_task}'."
                ),
                hint="Sync active_task to the current session task, or close the stale session.",
                paths=[".haxaml/acts.yaml:active_task", ".haxaml/acts.yaml:sessions"],
            )
        )

    contract_raw = acts.get("lifecycle_contract", {})
    contract = contract_raw if isinstance(contract_raw, dict) else {}
    contract_session_id = _normalized_text(contract.get("active_session_id", ""))
    if contract_session_id:
        sessions = acts.get("sessions") or []
        matching = None
        if isinstance(sessions, list):
            for session in sessions:
                if isinstance(session, dict) and _normalized_text(session.get("id", "")) == contract_session_id:
                    matching = session
                    break
        if not matching:
            findings.append(
                ConsistencyFinding(
                    code="contract_session_missing",
                    severity="warning",
                    area="session_state_coherence",
                    message=(
                        f"acts.lifecycle_contract points to session '{contract_session_id}' "
                        "but that session is not present in acts.sessions."
                    ),
                    hint="Clear the stale lifecycle_contract pointer or restore the missing session entry.",
                    paths=[".haxaml/acts.yaml:lifecycle_contract", ".haxaml/acts.yaml:sessions"],
                )
            )
        else:
            contract_task = _normalized_task_name(contract.get("active_task", ""))
            session_task = _normalized_session_task(matching)
            if contract_task and session_task and contract_task != session_task:
                findings.append(
                    ConsistencyFinding(
                        code="contract_task_session_mismatch",
                        severity="warning",
                        area="session_state_coherence",
                        message=(
                            f"acts.lifecycle_contract active_task '{contract_task}' does not match "
                            f"session '{contract_session_id}' task '{session_task}'."
                        ),
                        hint="Update lifecycle_contract.active_task to match the active session task.",
                        paths=[".haxaml/acts.yaml:lifecycle_contract", ".haxaml/acts.yaml:sessions"],
                    )
                )

    runs = [item for item in (acts.get("runs") or []) if isinstance(item, dict)]
    run_ids = {_normalized_text(item.get("id", "")) for item in runs if _normalized_text(item.get("id", ""))}
    archived_run_ids, archive_errors = _archive_run_ids(Path(project_dir), acts)
    run_ids.update(archived_run_ids)
    for message in archive_errors:
        findings.append(
            ConsistencyFinding(
                code="archive_corrupt",
                severity="blocking",
                area="archive_coherence",
                message=message,
                hint="Repair acts.archive metadata or restore .haxaml/archive/acts-history.yaml.",
                paths=[".haxaml/acts.yaml:archive", ".haxaml/archive/acts-history.yaml"],
            )
        )
    expect_sync = _expect_sync_state(acts)
    if bool(expect_sync["required"]):
        if not expect_sync["pending_run_id"] or not expect_sync["pending_task"] or not expect_sync["pending_result"]:
            findings.append(
                ConsistencyFinding(
                    code="expect_sync_missing_pending_fields",
                    severity="warning",
                    area="session_state_coherence",
                    message=(
                        "acts.expect_sync says sync is required but the pending run/task/result fields are incomplete."
                    ),
                    hint="Repair acts.expect_sync so the next sync target is explicit.",
                    paths=[".haxaml/acts.yaml:expect_sync"],
                )
            )
        elif expect_sync["pending_run_id"] not in run_ids:
            findings.append(
                ConsistencyFinding(
                    code="expect_sync_unknown_run",
                    severity="warning",
                    area="session_state_coherence",
                    message=(
                        f"acts.expect_sync references pending run '{expect_sync['pending_run_id']}' "
                        "but that run is not present in acts.runs."
                    ),
                    hint="Repair expect_sync.pending_run_id or restore the missing run record.",
                    paths=[".haxaml/acts.yaml:expect_sync", ".haxaml/acts.yaml:runs"],
                )
            )
    elif expect_sync["pending_run_id"] or expect_sync["pending_task"] or expect_sync["pending_result"]:
        findings.append(
            ConsistencyFinding(
                code="expect_sync_stale_pending_fields",
                severity="warning",
                area="session_state_coherence",
                message=(
                    "acts.expect_sync is marked clean but still carries pending run/task/result fields."
                ),
                hint="Clear the stale pending sync fields after a successful sync.",
                paths=[".haxaml/acts.yaml:expect_sync"],
            )
        )
    if expect_sync["last_synced_run_id"] and expect_sync["last_synced_run_id"] not in run_ids:
        findings.append(
            ConsistencyFinding(
                code="expect_sync_unknown_last_synced_run",
                severity="warning",
                area="session_state_coherence",
                message=(
                    f"acts.expect_sync last_synced_run_id '{expect_sync['last_synced_run_id']}' "
                    "does not match any run currently recorded in acts.runs."
                ),
                hint="Repair the sync metadata or restore the matching run record.",
                paths=[".haxaml/acts.yaml:expect_sync", ".haxaml/acts.yaml:runs"],
            )
        )

    verifications = [
        item for item in (acts.get("verifications") or [])
        if isinstance(item, dict)
    ]
    verification_session_ids = {
        _normalized_text(item.get("session_id", ""))
        for item in verifications
        if _normalized_text(item.get("session_id", ""))
    }
    recorded_sessions = _recorded_sessions(acts)
    missing_verification_sessions = [
        _normalized_text(item.get("id", ""))
        for item in recorded_sessions
        if _normalized_text(item.get("id", "")) and _normalized_text(item.get("id", "")) not in verification_session_ids
    ]
    if missing_verification_sessions:
        findings.append(
            ConsistencyFinding(
                code="recorded_sessions_missing_verification",
                severity="warning",
                area="verification_governance_coherence",
                message=(
                    "acts.sessions contains recorded/failed sessions without matching verification "
                    f"entries: {missing_verification_sessions}."
                ),
                hint="Record verification evidence for those sessions, or repair stale session states.",
                paths=[".haxaml/acts.yaml:sessions", ".haxaml/acts.yaml:verifications"],
            )
        )

    verify_checks = (rules.get("after_task") or {}).get("verify", []) or []
    verification_policy = rules.get("verification_policy") or {}
    require_checks = verification_policy.get("require_checks", []) if isinstance(verification_policy, dict) else []
    verification_expected = any(isinstance(item, str) and item.strip() for item in verify_checks) or bool(require_checks)
    if verification_expected and runs and not verifications:
        findings.append(
            ConsistencyFinding(
                code="verification_policy_without_recent_evidence",
                severity="warning",
                area="verification_governance_coherence",
                message=(
                    "rules imply verification discipline, but acts.yaml has recorded runs and no verification evidence."
                ),
                hint="Use haxaml_session_verify before record, or backfill the missing verification history.",
                paths=[".haxaml/rules.yaml:after_task", ".haxaml/rules.yaml:verification_policy", ".haxaml/acts.yaml:verifications"],
            )
        )

    runbook_verification_expected = any(run.get("verify") for run in runbook if isinstance(run.get("verify"), list))
    if runbook_verification_expected and recorded_sessions and not verifications:
        findings.append(
            ConsistencyFinding(
                code="runbook_verification_without_evidence",
                severity="warning",
                area="verification_governance_coherence",
                message=(
                    "expect.runbook declares verification checks, but recent governed state shows no verification entries."
                ),
                hint="Ensure governed runs are verified and persisted before they are treated as done.",
                paths=[".haxaml/expect.yaml:runbook", ".haxaml/acts.yaml:verifications"],
            )
        )

    blocking_dependencies = [
        item for item in (acts.get("unresolved_dependencies") or [])
        if isinstance(item, dict) and bool(item.get("blocking"))
    ]
    blocking_questions = [
        item for item in (expect.get("open_questions") or [])
        if isinstance(item, dict) and bool(item.get("blocking"))
    ]
    blocking_facts = [
        item for item in (facts.get("unresolved") or [])
        if isinstance(item, dict) and bool(item.get("blocking"))
    ]
    blocked_reasons: list[str] = []
    if blocking_dependencies:
        blocked_reasons.append("blocking unresolved dependencies exist in acts.yaml")
    if blocking_questions:
        blocked_reasons.append("blocking open questions exist in expect.yaml")
    if blocking_facts:
        blocked_reasons.append("blocking unresolved facts exist in facts.yaml")
    if any(_normalized_text(item.get("status", "")).lower() == "blocked" for item in runbook):
        blocked_reasons.append("runbook contains blocked runs")
    if any(finding.code == "active_run_unmet_dependencies" for finding in findings):
        blocked_reasons.append("active run still has unmet dependencies")

    stale_reasons: list[str] = []
    sessions = acts.get("sessions") or []
    if active_task and isinstance(sessions, list) and sessions and not open_sessions:
        stale_reasons.append("active_task is set but no open session remains")
    if any(
        finding.code
        in {
            "active_task_session_mismatch",
            "contract_session_missing",
            "contract_task_session_mismatch",
            "expect_sync_missing_pending_fields",
            "expect_sync_unknown_run",
            "expect_sync_stale_pending_fields",
            "expect_sync_unknown_last_synced_run",
            "recorded_sessions_missing_verification",
        }
        for finding in findings
    ):
        stale_reasons.append("acts state has stale session or sync metadata")

    if bool(expect_sync["required"]):
        progress_status = "sync_pending"
        reason = (
            f"expect sync is pending for run '{expect_sync['pending_run_id'] or 'unknown'}'"
        )
    elif stale_reasons:
        progress_status = "stale_state"
        reason = stale_reasons[0]
    elif blocked_reasons:
        progress_status = "blocked"
        reason = blocked_reasons[0]
    else:
        progress_status = "on_track"
        if active_runs:
            reason = f"active run {active_runs[0].get('run')} is aligned with current governed state"
        elif active_phases:
            reason = f"active phase '{active_phases[0]}' has no deterministic drift signals"
        else:
            reason = "no active drift signal was detected from expect.yaml and acts.yaml"

    return {
        "status": progress_status,
        "reason": reason,
        "findings": [
            {
                "code": finding.code,
                "severity": finding.severity,
                "area": finding.area,
                "message": finding.message,
                "hint": finding.hint,
                "paths": list(finding.paths),
            }
            for finding in findings
        ],
        "counts": {
            "warnings": sum(1 for finding in findings if finding.severity == "warning"),
            "blocking": sum(1 for finding in findings if finding.severity == "blocking"),
        },
        "active_phase": active_phases[0] if active_phases else "",
        "active_run": active_runs[0].get("run") if active_runs else None,
        "active_task": active_task,
        "open_session_count": len(open_sessions),
        "pending_expect_sync": bool(expect_sync["required"]),
    }


def semantic_validate(frame: "FrameModel") -> SemanticValidationResult:
    """Run semantic checks beyond JSON Schema shape validation.

    Blocking checks: structural gaps that prevent safe Haxaml operation.
    Advisory warnings: quality gaps that weaken FRAME but don't block execution.
    """
    blocking: list[str] = []
    warnings: list[str] = []

    # --- load errors are always blocking ---
    for err in frame.load_errors:
        blocking.append(f"FRAME load error: {err}")

    facts: dict[str, Any] = frame.facts or {}
    rules: dict[str, Any] = frame.rules or {}
    acts: dict[str, Any] = frame.acts or {}
    expect: dict[str, Any] = frame.expect or {}
    memory_policy = normalize_memory_policy((rules.get("memory_policy") or {}))
    project_dir = Path(getattr(frame, "project_dir", Path(".")))

    # --- blocking: required structural facts ---
    # Block only when the key is entirely absent — not when it exists but is
    # empty (that is valid for a freshly scaffolded project).
    identity = facts.get("identity")
    if identity is None:
        blocking.append("facts.identity section is absent — add identity.name and identity.version")
    else:
        if "name" not in (identity or {}):
            blocking.append("facts.identity.name key is absent")

    goal = facts.get("goal")
    if goal is None:
        blocking.append("facts.goal section is absent — add goal.purpose and goal.scope")
    else:
        if "purpose" not in (goal or {}):
            blocking.append("facts.goal.purpose key is absent")

    # Warn (not block) on empty scaffold values. A freshly scaffolded project should
    # still validate, but collaborators should see exactly which values remain placeholders.
    _identity = identity or {}
    _goal = goal or {}
    if "name" in _identity and not str(_identity.get("name") or "").strip():
        warnings.append("facts.identity.name is empty — fill in the project name")
    if "purpose" in _goal and not str(_goal.get("purpose") or "").strip():
        warnings.append("facts.goal.purpose is empty — fill in the project purpose")

    # --- blocking: corrupt/inconsistent lifecycle state ---
    _active_task_raw = acts.get("active_task")
    if isinstance(_active_task_raw, dict):
        _task_name = str(_active_task_raw.get("name") or "").strip().lower()
        active_task = None if _task_name in ("", "none", "null") else _task_name
    elif isinstance(_active_task_raw, str):
        _task_name = _active_task_raw.strip().lower()
        active_task = None if _task_name in ("", "none", "null") else _task_name
    else:
        active_task = None
    sessions = acts.get("sessions") or []
    if active_task and isinstance(sessions, list) and len(sessions) > 0:
        open_sessions = [
            s for s in sessions
            if isinstance(s, dict) and s.get("status") not in ("completed", "failed", "recorded")
        ]
        if not open_sessions:
            blocking.append(
                "acts.yaml has active_task set but no matching open session — "
                "lifecycle state is stale and may block verify/record"
            )

    # --- advisory: description and scope quality ---
    if not _identity.get("description"):
        warnings.append("facts.identity.description is missing — helps agents understand the project")

    if not _goal.get("scope"):
        warnings.append("facts.goal.scope is missing — agents may over-apply changes")

    if not _goal.get("out_of_scope"):
        warnings.append("facts.goal.out_of_scope is missing — agents may attempt out-of-scope work")

    acts_path = project_dir / ".haxaml" / "acts.yaml"
    if acts_path.exists():
        max_acts_bytes = int(memory_policy.get("max_acts_bytes", 16000) or 16000)
        hot_size = acts_path.stat().st_size
        if hot_size > max_acts_bytes:
            warnings.append(
                f"Hot acts state is {hot_size} bytes, above memory_policy.max_acts_bytes={max_acts_bytes} — archive cold history with haxaml_state_compact."
            )

    # --- advisory: vague rules ---
    for key, value in rules.items():
        if isinstance(value, str) and len(value.strip().split()) <= 2:
            warnings.append(
                f"rules.{key} value is very short ('{value.strip()}') — "
                "consider a more descriptive rule"
            )

    # --- advisory: missing verification policy ---
    if not rules.get("verification") and not rules.get("verification_policy"):
        warnings.append(
            "rules.verification policy is absent — "
            "agents may not know how to verify before recording"
        )

    # --- advisory: map quality ---
    map_data: dict[str, Any] = frame.map or {}
    modules = map_data.get("modules") or []
    if isinstance(modules, list):
        for mod in modules:
            if not isinstance(mod, dict):
                continue
            name = mod.get("name", "<unnamed>")
            if not mod.get("owner"):
                warnings.append(f"map module '{name}' has no owner defined")
            if not mod.get("paths") and not mod.get("path"):
                warnings.append(f"map module '{name}' has no paths defined")

    # --- advisory: outstanding blocking unresolved items ---
    unresolved = facts.get("unresolved") or []
    if isinstance(unresolved, list):
        for item in unresolved:
            if isinstance(item, dict) and item.get("blocking"):
                warnings.append(
                    f"facts.unresolved blocking item outstanding: "
                    f"{item.get('item', '?')} — {item.get('reason', 'no reason given')}"
                )

    consistency = frame_consistency_report(frame)
    for finding in consistency["findings"]:
        if finding["severity"] == "blocking":
            blocking.append(finding["message"])
        else:
            warnings.append(finding["message"])

    return SemanticValidationResult(blocking=blocking, warnings=warnings)


SCHEMA_DIR = Path(__file__).parent / "schemas"


def load_yaml(path: str) -> dict:
    """Load a YAML file and return its contents."""
    return _load_yaml_file(path)


def load_schema(schema_name: str) -> dict:
    """Load a schema YAML file from the schemas directory."""
    schema_path = SCHEMA_DIR / schema_name
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema not found: {schema_path}")
    return load_yaml(str(schema_path))


def validate_facts(facts_path: str) -> list[str]:
    """Validate facts.yaml against the facts schema.

    Returns a list of error messages. Empty list = valid.
    """
    schema = load_schema("facts.schema.yaml")
    data = load_yaml(facts_path)
    validator = Draft202012Validator(schema)
    errors = []
    for error in sorted(validator.iter_errors(data), key=lambda e: list(e.path)):
        path = ".".join(str(p) for p in error.absolute_path) or "(root)"
        errors.append(f"[{path}] {error.message}")
    return errors



def validate_acts(acts_path: str) -> list[str]:
    """Validate acts.yaml against the acts schema.

    Returns a list of error messages. Empty list = valid.
    """
    schema = load_schema("acts.schema.yaml")
    data = load_yaml(acts_path)
    validator = Draft202012Validator(schema)
    errors = []
    for error in sorted(validator.iter_errors(data), key=lambda e: list(e.path)):
        path = ".".join(str(p) for p in error.absolute_path) or "(root)"
        errors.append(f"[{path}] {error.message}")
    return errors



def validate_rules(rules_path: str) -> list[str]:
    """Validate rules.yaml against the rules schema.

    Returns a list of error messages. Empty list = valid.
    """
    schema = load_schema("rules.schema.yaml")
    data = load_yaml(rules_path)
    validator = Draft202012Validator(schema)
    errors = []
    for error in sorted(validator.iter_errors(data), key=lambda e: list(e.path)):
        path = ".".join(str(p) for p in error.absolute_path) or "(root)"
        errors.append(f"[{path}] {error.message}")
    return errors


def validate_expect(expect_path: str) -> list[str]:
    """Validate expect.yaml against the expect schema.

    Returns a list of error messages. Empty list = valid.
    """
    schema = load_schema("expect.schema.yaml")
    data = load_yaml(expect_path)
    validator = Draft202012Validator(schema)
    errors = []
    for error in sorted(validator.iter_errors(data), key=lambda e: list(e.path)):
        path = ".".join(str(p) for p in error.absolute_path) or "(root)"
        errors.append(f"[{path}] {error.message}")
    return errors



def validate_map(map_path: str) -> list[str]:
    """Validate map.yaml against the map schema.

    Returns a list of error messages. Empty list = valid.
    """
    schema = load_schema("map.schema.yaml")
    data = load_yaml(map_path)
    validator = Draft202012Validator(schema)
    errors = []
    for error in sorted(validator.iter_errors(data), key=lambda e: list(e.path)):
        path = ".".join(str(p) for p in error.absolute_path) or "(root)"
        errors.append(f"[{path}] {error.message}")
    return errors


def detect_missing_facts_fields(facts_path: str) -> list[str]:
    """Detect fields that are absent but would improve facts completeness.

    Goes beyond schema required fields to check for recommended fields.
    """
    facts = load_yaml(facts_path)
    missing = []

    recommended = {
        "identity.description": facts.get("identity", {}).get("description"),
        "goal.scope": facts.get("goal", {}).get("scope"),
        "goal.out_of_scope": facts.get("goal", {}).get("out_of_scope"),
        "tools": facts.get("tools"),
        "services": facts.get("services"),
        "roles": facts.get("roles"),
        "features": facts.get("features"),
    }

    for field, value in recommended.items():
        if value is None:
            missing.append(f"Recommended field missing: {field}")
        elif isinstance(value, (list, dict)) and len(value) == 0:
            missing.append(f"Recommended field empty: {field}")

    unresolved = facts.get("unresolved", [])
    blocking = [u for u in unresolved if u.get("blocking", False)]
    if blocking:
        for item in blocking:
            missing.append(f"BLOCKING unresolved: {item['item']} — {item.get('reason', 'no reason given')}")

    return missing
