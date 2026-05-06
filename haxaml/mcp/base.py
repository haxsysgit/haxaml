"""Compatibility import surface for MCP tools/resources.

This module intentionally re-exports legacy names so `tools_*` and `resources`
modules can keep `from haxaml.mcp.base import *` while implementation details
move into focused helper modules.
"""

# Stdlib names kept for wildcard-import compatibility in tool modules.
import difflib
import json
import os
import re
import shutil
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from mcp.server.fastmcp import FastMCP

# FrameModel — normalized FRAME loader. Use this in new code.
from haxaml.frame_model import FrameModel

# Core haxaml imports kept for wildcard-import compatibility.
from haxaml.adoption import (
    analyze_adoption_instructions,
    render_adoption_report,
    scan_native_sources,
    write_adoption_scaffold,
)
from haxaml.auto_export import export_if_stale
from haxaml.context import (
    build_context,
    build_context_pack,
    count_tokens,
    format_context_pack,
    load_frame_data,
)
from haxaml.export_engine import (
    AGENT_CONFIGS,
    export_frame_to_markdown,
    export_to_file,
    list_agents,
)
from haxaml.init_templates import write_init_templates, sync_rules_governance_version
from haxaml.map_policy import (
    evaluate_map_complexity,
    format_map_complexity_summary,
    map_complexity_issues,
)
from haxaml.paths import frame_dir, frame_path, resolve_frame_file
from haxaml.reconcile import reconcile_derivation
from haxaml.runner import ExecutionRunner
from haxaml.state_manager import StateError, StateManager
from haxaml.supervision import render_impact, render_needs
from haxaml.validator import (
    SemanticValidationResult,
    detect_missing_facts_fields,
    frame_consistency_report,
    load_yaml,
    semantic_validate,
    validate_acts,
    validate_expect,
    validate_facts,
    validate_map,
    validate_rules,
)
from haxaml.versioning import MCP_LAUNCHER_PACKAGE, PACKAGE_NAME, get_version, version_spec

# Modularized MCP internals.
from haxaml.mcp.adoption_helpers import _adoption_plan_payload
from haxaml.mcp.app_core import (
    ABOUT_PROMPT_VERSION,
    DETAIL_FULL,
    DETAIL_MODES,
    DETAIL_SHORT,
    UTILITY_TASK_HINTS,
    _ABOUT_ACK_CACHE,
    _RETRY_GUARD_CACHE,
    _project,
    mcp_app,
)
from haxaml.mcp.export_helpers import (
    _bootstrap_snippet,
    _build_unified_diff,
    _diff_summary,
    _editor_targets,
    _mcp_server_config,
    _resolve_export_target,
    _write_bootstrap_config,
)
from haxaml.mcp.lifecycle_helpers import (
    _classify_task_type,
    _contract_allows,
    _contract_touch,
    _git_changed_files,
    _find_session,
    _get_state_manager,
    _governed_code_changes,
    _has_governed_evidence_for_changes,
    _lifecycle_hint,
    _guidance_eval,
    _has_conflict_stop_reason,
    _lifecycle_contract_state,
    _expect_sync_state,
    _now_iso,
    _persist_state,
    _rules_policy,
    _set_lifecycle_contract_state,
    _session_read_policy,
    _wrapper_deprecation,
)
from haxaml.mcp.policy_helpers import (
    CONTEXT_PACK_LIMIT_TEXT,
    RETRY_POLICY_TEXT,
    VISIBILITY_POLICY_TEXT,
    _about_ack_status,
    _about_payload,
    _call_budget_for,
    _compact_context_refresh_policy,
    _context_refresh_policy,
    _gate_error_with_retry_policy,
    _normalize_context_refresh_reason,
    _project_key,
    _require_about,
    _retry_guard_clear,
    _retry_guard_key,
    _utility_mode_policy,
    _utility_mode_error,
    _utility_mode_eval,
    _workflow_budget_catalog,
)
from haxaml.mcp.response_helpers import (
    _compact_context_pack_payload,
    _compact_success,
    _err,
    _normalize_detail,
    _normalize_dynamic_text,
    _ok,
    _pick_fields,
    _reconcile_summary,
)

# Export all shared symbols (including single-underscore helpers) so tool and
# resource modules can import the legacy helper surface directly.
__all__ = [
    name
    for name in globals()
    if not (name.startswith("__") and name.endswith("__"))
]

# Convenience: route old load_frame_data callers through FrameModel.as_dict().
# This keeps all existing tool call-sites working without change.
def load_frame_data(project_dir: str = ".") -> dict:  # type: ignore[override]
    return FrameModel.load(project_dir).as_dict()
