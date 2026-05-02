"""Prebuild task type templates for haxaml_prebuild.

Each template defines:
  task_type             — one of the 12 domain types
  default_guidance_type — maps to one of the 5 abstract guidance types
  risk                  — high / medium / low
  keywords              — used for task classification
  required_questions    — agent must surface these before building
  materials_needed      — files/artefacts the agent should inspect
  done_criteria         — concrete completion conditions
  likely_impact         — files/modules likely to be touched
  risks                 — known hazards for this task type

High-risk types (authentication, payment, database_migration, deployment) block
governed execution when FRAME is in a bad state, regardless of task intent.
"""

from __future__ import annotations

from typing import Any


PREBUILD_TEMPLATES: list[dict[str, Any]] = [
    {
        "task_type": "authentication",
        "default_guidance_type": "implementation",
        "risk": "high",
        "keywords": [
            "auth", "login", "logout", "register", "registration", "password",
            "token", "jwt", "oauth", "session", "credential", "identity",
            "sign in", "sign up", "api key", "access control",
        ],
        "required_questions": [
            "What authentication mechanism should be used: JWT, session, OAuth, API key, or another method?",
            "Which routes or actions should be protected?",
            "Does a user model already exist?",
            "Should registration, login, logout, refresh, or password reset be included?",
        ],
        "materials_needed": [
            "existing user model",
            "auth requirements",
            "route protection scope",
            "security configuration",
            "test expectations",
        ],
        "done_criteria": [
            "auth mechanism matches confirmed requirement",
            "protected routes reject unauthenticated requests",
            "successful auth flow is documented or tested",
            "no unrelated modules are changed",
        ],
        "likely_impact": [
            "user model",
            "auth routes",
            "security helpers",
            "settings or config",
            "tests",
        ],
        "risks": [
            "auth method may be guessed without user confirmation",
            "wrong route protection can break existing flows",
            "password or token handling may introduce security risk",
        ],
    },
    {
        "task_type": "payment",
        "default_guidance_type": "implementation",
        "risk": "high",
        "keywords": [
            "payment", "billing", "stripe", "paypal", "invoice", "checkout",
            "subscription", "charge", "refund", "transaction", "pricing",
            "webhook", "payment gateway",
        ],
        "required_questions": [
            "Which payment provider should be used?",
            "What payment flows are in scope: one-time, subscription, refunds?",
            "Does an existing payment model or billing module exist?",
            "Should webhooks be handled?",
        ],
        "materials_needed": [
            "payment provider documentation",
            "existing billing model",
            "webhook configuration",
            "test card or sandbox credentials",
        ],
        "done_criteria": [
            "payment provider is confirmed before implementation",
            "payment flow matches specified scope",
            "webhook handling is correct for the provider",
            "no real credentials appear in code or tests",
        ],
        "likely_impact": [
            "billing model",
            "payment routes",
            "webhook handlers",
            "settings or config",
            "tests",
        ],
        "risks": [
            "wrong provider assumed without confirmation",
            "real credentials accidentally committed",
            "webhook signature validation skipped",
            "billing state may become inconsistent on partial failure",
        ],
    },
    {
        "task_type": "api_endpoint",
        "default_guidance_type": "implementation",
        "risk": "medium",
        "keywords": [
            "api", "endpoint", "route", "rest", "graphql", "handler",
            "controller", "view", "response", "request", "http",
        ],
        "required_questions": [
            "What HTTP method and path should this endpoint use?",
            "What input does it expect and what does it return?",
            "Are there authentication or permission requirements?",
            "Does a similar endpoint already exist?",
        ],
        "materials_needed": [
            "route structure or router file",
            "request and response schema",
            "auth or permission middleware",
            "existing similar endpoints for reference",
        ],
        "done_criteria": [
            "endpoint responds correctly to valid input",
            "auth requirements are enforced",
            "error cases return appropriate status codes",
            "endpoint is tested",
        ],
        "likely_impact": [
            "router or URL config",
            "handler or controller",
            "serializer or schema",
            "auth middleware",
            "tests",
        ],
        "risks": [
            "missing auth check on a protected resource",
            "breaking change to an existing API contract",
            "unvalidated input reaching the handler",
        ],
    },
    {
        "task_type": "database_migration",
        "default_guidance_type": "implementation",
        "risk": "high",
        "keywords": [
            "migration", "migrate", "schema", "database", "db", "table",
            "column", "index", "alter", "drop table", "add column",
            "rename column", "foreign key", "constraint",
        ],
        "required_questions": [
            "What schema change is needed: add column, rename, drop, add table, index?",
            "Is this migration reversible?",
            "Will existing data need to be backfilled or transformed?",
            "Has this been tested against a copy of production data?",
        ],
        "materials_needed": [
            "current schema or migration history",
            "target schema or model changes",
            "backfill or data transformation requirements",
            "rollback plan",
        ],
        "done_criteria": [
            "migration runs forward without errors",
            "rollback is defined and tested if the provider supports it",
            "existing data is preserved or transformed correctly",
            "no unrelated schema changes are included",
        ],
        "likely_impact": [
            "migration files",
            "model definitions",
            "seed data or fixtures",
            "tests that depend on schema",
        ],
        "risks": [
            "irreversible migration without a rollback path",
            "data loss from incorrect column drop or rename",
            "production deployment order matters — migration before code or after",
            "long-running migration may lock tables",
        ],
    },
    {
        "task_type": "bug_fix",
        "default_guidance_type": "debug",
        "risk": "medium",
        "keywords": [
            "bug", "fix", "broken", "error", "exception", "crash",
            "failure", "incorrect", "wrong output", "regression", "issue",
            "traceback", "stacktrace",
        ],
        "required_questions": [
            "What is the observed incorrect behavior?",
            "What is the expected behavior?",
            "Has the bug been reproduced consistently?",
            "Is there a known related recent change?",
        ],
        "materials_needed": [
            "error message or traceback",
            "steps to reproduce",
            "affected code path",
            "existing tests if any",
        ],
        "done_criteria": [
            "root cause is identified before changing code",
            "fix targets the root cause, not just the symptom",
            "a test covers the fixed behavior",
            "no unrelated code is changed",
        ],
        "likely_impact": [
            "the module containing the bug",
            "tests covering that module",
            "possibly related utilities or helpers",
        ],
        "risks": [
            "fixing symptom without addressing root cause",
            "introducing regression in adjacent code",
            "fix that works in dev but not production",
        ],
    },
    {
        "task_type": "refactor",
        "default_guidance_type": "implementation",
        "risk": "medium",
        "keywords": [
            "refactor", "restructure", "reorganize", "clean up", "cleanup",
            "rename", "extract", "simplify", "decouple", "abstract",
        ],
        "required_questions": [
            "What is the specific scope of the refactor?",
            "Should behavior remain identical after the refactor?",
            "Are there known callers or dependents of the code being changed?",
            "What is the stopping condition for this refactor?",
        ],
        "materials_needed": [
            "current code structure",
            "known callers or dependents",
            "existing test coverage",
        ],
        "done_criteria": [
            "behavior is preserved or improvement is documented",
            "all existing tests pass after refactor",
            "scope did not expand beyond the defined boundary",
        ],
        "likely_impact": [
            "the module being refactored",
            "callers or dependents of changed interfaces",
            "tests",
        ],
        "risks": [
            "scope creep beyond the agreed boundary",
            "breaking callers that were not identified upfront",
            "refactor that changes behavior silently",
        ],
    },
    {
        "task_type": "testing",
        "default_guidance_type": "implementation",
        "risk": "low",
        "keywords": [
            "test", "tests", "spec", "unit test", "integration test",
            "coverage", "pytest", "fixture", "mock", "assert",
        ],
        "required_questions": [
            "What behavior should the tests cover?",
            "Are these unit tests, integration tests, or end-to-end tests?",
            "Should existing tests be extended or are these new tests?",
            "What does a passing test look like?",
        ],
        "materials_needed": [
            "the code to be tested",
            "existing test files if extending",
            "test configuration or fixtures",
        ],
        "done_criteria": [
            "tests cover the specified behavior",
            "tests pass in CI",
            "test names clearly describe what they verify",
            "no production code is changed as a side effect",
        ],
        "likely_impact": [
            "test files",
            "test fixtures",
            "possibly test configuration",
        ],
        "risks": [
            "tests that pass but do not actually verify the intended behavior",
            "over-mocking that hides real integration issues",
        ],
    },
    {
        "task_type": "deployment",
        "default_guidance_type": "implementation",
        "risk": "high",
        "keywords": [
            "deploy", "deployment", "release", "publish", "ci", "cd",
            "pipeline", "production", "staging", "environment", "infra",
            "dockerfile", "container", "kubernetes", "helm", "serverless",
        ],
        "required_questions": [
            "Which environment is this targeting: staging, production, both?",
            "Is there a rollback plan if this deployment fails?",
            "Are there pending migrations or data changes that must precede this?",
            "Who approves the release?",
        ],
        "materials_needed": [
            "deployment target and credentials",
            "CI/CD pipeline configuration",
            "migration or data change requirements",
            "rollback procedure",
        ],
        "done_criteria": [
            "deployment target confirmed before making changes",
            "rollback path is defined",
            "required pre-deployment steps are completed",
            "deployment is verified in the target environment",
        ],
        "likely_impact": [
            "CI/CD configuration",
            "infrastructure config",
            "environment variables or secrets",
            "application version marker",
        ],
        "risks": [
            "deploying to wrong environment",
            "missing migration before deployment",
            "no rollback plan if deployment fails",
            "secrets accidentally committed",
        ],
    },
    {
        "task_type": "documentation",
        "default_guidance_type": "outcome",
        "risk": "low",
        "keywords": [
            "docs", "documentation", "readme", "guide", "tutorial",
            "changelog", "docstring", "comment", "explain", "describe",
        ],
        "required_questions": [
            "Who is the audience for this documentation?",
            "What should the reader understand after reading it?",
            "Is this new documentation or an update to existing docs?",
            "Should it include examples?",
        ],
        "materials_needed": [
            "the feature or module being documented",
            "existing docs to check for consistency",
            "audience and tone expectations",
        ],
        "done_criteria": [
            "documentation covers the intended topic clearly",
            "audience is correctly targeted",
            "existing docs are not contradicted",
            "examples are accurate if included",
        ],
        "likely_impact": [
            "docs or learn files",
            "README",
            "docstrings in relevant modules",
        ],
        "risks": [
            "contradicting existing documentation",
            "outdated examples that do not match current behavior",
        ],
    },
    {
        "task_type": "cli_command",
        "default_guidance_type": "implementation",
        "risk": "low",
        "keywords": [
            "cli", "command", "command line", "subcommand", "argument",
            "flag", "option", "terminal", "script",
        ],
        "required_questions": [
            "What should the command do?",
            "What arguments or flags does it take?",
            "How should it handle errors?",
            "Should it have a help message?",
        ],
        "materials_needed": [
            "existing CLI entry point or cli.py",
            "argument parser or Click setup",
            "related functionality to expose",
        ],
        "done_criteria": [
            "command is registered and callable",
            "help message is correct",
            "error cases are handled gracefully",
            "command is tested",
        ],
        "likely_impact": [
            "cli.py or CLI entry module",
            "argument parser setup",
            "tests for CLI commands",
        ],
        "risks": [
            "conflicting command names with existing commands",
            "missing help or description for new flags",
        ],
    },
    {
        "task_type": "mcp_integration",
        "default_guidance_type": "implementation",
        "risk": "medium",
        "keywords": [
            "mcp", "mcp tool", "mcp server", "fastmcp", "tool registration",
            "mcp integration", "model context protocol",
        ],
        "required_questions": [
            "What MCP tool or resource is being added or changed?",
            "What does the tool return and what are its inputs?",
            "Does this change an existing tool contract?",
            "Are there lifecycle or gate constraints on this tool?",
        ],
        "materials_needed": [
            "existing MCP tool structure in tools_*.py",
            "base.py and mcp/app_core.py for patterns",
            "lifecycle contract if the tool participates in governed flow",
        ],
        "done_criteria": [
            "tool is registered with @mcp_app.tool()",
            "tool signature matches agreed contract",
            "tool returns correct ok/error envelope",
            "tool is tested",
        ],
        "likely_impact": [
            "tools_*.py module",
            "base.py exports if new helpers are added",
            "tools.py __all__ list",
            "tests/mcp/ tests",
        ],
        "risks": [
            "breaking an existing tool contract",
            "tool not appearing in MCP discovery due to missing registration",
            "lifecycle gate not enforced on a governed tool",
        ],
    },
    {
        "task_type": "frontend_feature",
        "default_guidance_type": "implementation",
        "risk": "low",
        "keywords": [
            "frontend", "ui", "component", "page", "view", "react",
            "vue", "svelte", "html", "css", "style", "layout",
            "button", "form", "modal", "sidebar",
        ],
        "required_questions": [
            "What does this feature look like and how does the user interact with it?",
            "Does it require new API calls or can it use existing data?",
            "Are there design mockups or specifications?",
            "Which existing components or pages does it relate to?",
        ],
        "materials_needed": [
            "design spec or mockup if available",
            "existing component structure",
            "API endpoints the feature depends on",
        ],
        "done_criteria": [
            "feature renders and behaves as specified",
            "no existing UI is broken",
            "API calls are correctly handled",
            "basic interaction tests pass if the project has them",
        ],
        "likely_impact": [
            "component files",
            "page or route files",
            "styles or CSS",
            "API integration layer",
        ],
        "risks": [
            "feature depends on API that does not yet exist",
            "visual regression in adjacent components",
        ],
    },
]

HIGH_RISK_TASK_TYPES = {"authentication", "payment", "database_migration", "deployment"}

_TEMPLATE_INDEX: dict[str, dict[str, Any]] | None = None


def get_template(task_type: str) -> dict[str, Any] | None:
    """Return the template for a given task_type, or None if not found."""
    global _TEMPLATE_INDEX
    if _TEMPLATE_INDEX is None:
        _TEMPLATE_INDEX = {t["task_type"]: t for t in PREBUILD_TEMPLATES}
    return _TEMPLATE_INDEX.get(task_type)


def classify_task(task: str, description: str = "") -> tuple[str, str, str]:
    """Classify a task string into (task_type, guidance_type, reason).

    Uses keyword matching against all 12 templates. Falls back to 'api_endpoint'
    for unrecognized tasks.

    Intent override: prefixes in task text can override guidance_type:
      - 'design ...' or 'design:' → guidance_type = design
      - 'strategy ...' / 'should I ...' / 'compare ...' → guidance_type = strategy
      - 'summarize ...' / 'explain ...' / 'review ...' → guidance_type = outcome
      - 'fix ...' / 'debug ...' → guidance_type = debug
    """
    text = f"{task} {description}".lower().strip()

    best_type = "api_endpoint"
    best_score = 0
    for tmpl in PREBUILD_TEMPLATES:
        score = sum(1 for kw in tmpl["keywords"] if kw in text)
        if score > best_score:
            best_score = score
            best_type = tmpl["task_type"]

    tmpl = get_template(best_type) or {}
    default_guidance = tmpl.get("default_guidance_type", "implementation")
    matched_kws = [kw for kw in (tmpl.get("keywords") or []) if kw in text]

    # intent override
    guidance_type = default_guidance
    if any(text.startswith(p) for p in ("design ", "design:", "architecture ")):
        guidance_type = "design"
    elif any(p in text for p in ("should i ", "compare ", "strategy:", "which is better")):
        guidance_type = "strategy"
    elif any(text.startswith(p) for p in ("summarize ", "explain ", "review ", "describe ")):
        guidance_type = "outcome"
    elif any(text.startswith(p) for p in ("fix ", "debug ", "why is ", "investigate ")):
        guidance_type = "debug"

    if matched_kws:
        reason = (
            f"Matched '{best_type}' because the task mentions: "
            + ", ".join(f"'{kw}'" for kw in matched_kws[:4])
        )
    else:
        reason = f"No strong keyword match; defaulted to '{best_type}'"

    return best_type, guidance_type, reason


def context_policy_for(task_type: str, risk: str) -> dict[str, Any]:
    """Return a context_policy dict for a given task_type and risk."""
    if risk == "high":
        pack = "balanced"
    elif risk == "low":
        pack = "minimal"
    else:
        pack = "balanced"

    return {
        "recommended_pack": pack,
        "max_context_packs": 1,
        "allow_refresh_when": [
            "scope_changed",
            "new_risk",
            "pack_stale",
            "verification_blocked",
        ],
    }
