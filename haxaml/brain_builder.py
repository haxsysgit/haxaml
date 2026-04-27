"""Facts builder — guided, interactive facts.yaml construction from intent.

Enforces completeness before execution. Prevents placeholders.
Implements the Requirement Completion Engine (Phase 0).
"""

import re
from pathlib import Path
from typing import Optional

import yaml

from haxaml.validator import validate_facts, detect_missing_facts_fields


# Fields the builder must collect, in order.
REQUIRED_SECTIONS = [
    {
        "key": "identity",
        "label": "Project Identity",
        "questions": [
            {"field": "name", "prompt": "Project name", "required": True,
             "reject_pattern": r"^(my-project|untitled|test|TODO)$",
             "reject_msg": "Use a real project name, not a placeholder."},
            {"field": "version", "prompt": "Version", "required": True, "default": "0.1.0"},
            {"field": "description", "prompt": "One-line description",
             "required": True, "min_length": 10,
             "reject_msg": "Description must be meaningful (10+ chars)."},
        ],
    },
    {
        "key": "goal",
        "label": "Project Goal",
        "questions": [
            {"field": "purpose", "prompt": "Why does this project exist?",
             "required": True, "min_length": 15,
             "reject_msg": "Purpose must be specific (15+ chars). No vague goals."},
            {"field": "scope", "prompt": "What is being built right now?",
             "required": True, "min_length": 10},
            {"field": "out_of_scope", "prompt": "What is explicitly excluded? (comma-separated)",
             "required": False, "is_list": True},
        ],
    },
    {
        "key": "stack",
        "label": "Technology Stack",
        "questions": [
            {"field": "language", "prompt": "Primary language (e.g. python, typescript, go)",
             "required": True,
             "reject_pattern": r"^(any|tbd|TBD|TODO|none)$",
             "reject_msg": "Language must be a real choice. No 'any' or 'TBD'."},
            {"field": "backend", "prompt": "Backend framework (e.g. fastapi, express, none)",
             "required": False},
            {"field": "frontend", "prompt": "Frontend framework (e.g. react, svelte, none)",
             "required": False},
            {"field": "runtime", "prompt": "Runtime (e.g. python 3.11+, node 20+)",
             "required": False},
            {"field": "package_manager", "prompt": "Package manager (e.g. pip, npm, pnpm)",
             "required": False},
        ],
    },
    {
        "key": "architecture",
        "label": "Architecture",
        "questions": [
            {"field": "pattern", "prompt": "Architecture pattern (e.g. layered, monolith, microservices, hexagonal)",
             "required": True,
             "reject_pattern": r"^(any|tbd|TBD|TODO|none|default)$",
             "reject_msg": "Architecture must be a real decision."},
            {"field": "reasoning", "prompt": "Why this architecture pattern?",
             "required": True, "min_length": 10,
             "reject_msg": "Reasoning must be substantive (10+ chars)."},
            {"field": "boundaries", "prompt": "System boundaries/modules (comma-separated)",
             "required": False, "is_list": True},
        ],
    },
    {
        "key": "database",
        "label": "Database",
        "questions": [
            {"field": "type", "prompt": "Database type (e.g. postgres, mongodb, sqlite, none)",
             "required": True,
             "reject_pattern": r"^(any|tbd|TBD|TODO|default|we.ll decide later)$",
             "reject_msg": "Database must be a real choice. If no DB needed, say 'none'."},
            {"field": "connection", "prompt": "Connection method/URI (or 'none')",
             "required": True},
            {"field": "migrations", "prompt": "Migration strategy (e.g. alembic, prisma, none)",
             "required": False},
        ],
    },
    {
        "key": "constraints",
        "label": "Constraints",
        "questions": [
            {"field": "_list", "prompt": "Hard rules the project must follow (one per line, empty line to finish)",
             "required": True, "is_multiline_list": True, "min_items": 1,
             "reject_msg": "At least one real constraint is required."},
        ],
    },
    {
        "key": "success_criteria",
        "label": "Success Criteria",
        "questions": [
            {"field": "_list", "prompt": "How do you know this project works? (one per line, empty line to finish)",
             "required": True, "is_multiline_list": True, "min_items": 1,
             "reject_msg": "At least one success criterion is required."},
        ],
    },
]

OPTIONAL_SECTIONS = [
    {
        "key": "tools",
        "label": "Tools & Integrations",
        "questions": [
            {"field": "testing", "prompt": "Test framework (e.g. pytest, jest, vitest)"},
            {"field": "mcp", "prompt": "MCP servers used (comma-separated)", "is_list": True},
            {"field": "ci", "prompt": "CI/CD system (e.g. github-actions, none)"},
        ],
    },
    {
        "key": "roles",
        "label": "Roles",
        "questions": [
            {"field": "_object_list",
             "prompt": "Roles involved (format: name:responsibility, one per line, empty to finish)",
             "is_role_list": True},
        ],
    },
]


PLACEHOLDER_PATTERNS = [
    r"^TODO$", r"^TBD$", r"^tbd$", r"^fixme$",
    r"^placeholder$", r"^fill.?in$", r"^xxx+$",
    r"^we.ll (decide|figure|add|do).*(later|soon)$",
    r"^assume default",
    r"^default config",
]


def is_placeholder(value: str) -> bool:
    """Check if a value looks like a placeholder."""
    if not value or not value.strip():
        return True
    v = value.strip()
    return any(re.match(p, v, re.IGNORECASE) for p in PLACEHOLDER_PATTERNS)


def validate_answer(question: dict, answer: str) -> Optional[str]:
    """Validate a single answer. Returns error message or None."""
    answer = answer.strip()

    if question.get("required") and not answer:
        return "This field is required."

    if not answer:
        return None

    min_length = question.get("min_length", 0)
    if min_length and len(answer) < min_length:
        return question.get("reject_msg", f"Answer must be at least {min_length} characters.")

    reject_pattern = question.get("reject_pattern")
    if reject_pattern and re.match(reject_pattern, answer, re.IGNORECASE):
        return question.get("reject_msg", "This value is not allowed.")

    if is_placeholder(answer):
        return "Placeholders are not allowed. Provide a real value."

    return None


def build_brain_from_answers(answers: dict) -> dict:
    """Construct brain dict from collected answers."""
    brain = {}

    for section in REQUIRED_SECTIONS + OPTIONAL_SECTIONS:
        key = section["key"]
        section_answers = answers.get(key, {})

        if not section_answers:
            continue

        if key in ("constraints", "success_criteria"):
            brain[key] = section_answers.get("_list", [])
        elif "_object_list" in section_answers and key == "roles":
            brain[key] = section_answers["_object_list"]
        else:
            brain[key] = {}
            for q in section["questions"]:
                field = q["field"]
                if field.startswith("_"):
                    continue
                value = section_answers.get(field)
                if value is not None:
                    if q.get("is_list") and isinstance(value, str):
                        brain[key][field] = [
                            v.strip() for v in value.split(",") if v.strip()
                        ]
                    else:
                        brain[key][field] = value

    brain.setdefault("unresolved", [])
    brain.setdefault("features", [])
    brain.setdefault("services", [])

    return brain


def write_facts(facts: dict, output_path: str) -> None:
    """Write facts dict to YAML file."""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        f.write("# Project Facts (FRAME: F) — Generated by Haxaml\n\n")
        yaml.dump(facts, f, default_flow_style=False, sort_keys=False)


# Backward compat alias
write_brain = write_facts


def interactive_build(output_path: str = ".haxaml/facts.yaml",
                      input_fn=None, print_fn=None) -> dict:
    """Run the interactive facts builder.

    Args:
        output_path: Where to write the facts.yaml
        input_fn: Custom input function (for testing). Signature: (prompt) -> str
        print_fn: Custom print function (for testing). Signature: (message) -> None

    Returns:
        The constructed facts dict.
    """
    if input_fn is None:
        input_fn = input
    if print_fn is None:
        print_fn = print

    print_fn("\n╔══════════════════════════════════════╗")
    print_fn("║    Haxaml Facts Builder v0.2.0       ║")
    print_fn("║  Build the end from the beginning.   ║")
    print_fn("╚══════════════════════════════════════╝\n")
    print_fn("Answer each question. No placeholders. No guessing.\n")

    answers = {}

    for section in REQUIRED_SECTIONS:
        print_fn(f"\n── {section['label']} ──")
        answers[section["key"]] = _collect_section(section, input_fn, print_fn)

    print_fn("\n── Optional Sections ──")
    for section in OPTIONAL_SECTIONS:
        response = input_fn(f"Configure {section['label']}? [y/N]: ").strip().lower()
        if response in ("y", "yes"):
            answers[section["key"]] = _collect_section(section, input_fn, print_fn)

    brain = build_brain_from_answers(answers)
    write_facts(brain, output_path)

    print_fn(f"\n✓ Facts written to {output_path}")

    errors = validate_facts(output_path)
    if errors:
        print_fn(f"\n⚠ Facts has {len(errors)} validation error(s):")
        for e in errors:
            print_fn(f"  → {e}")
    else:
        print_fn("✓ Facts passes schema validation")

    missing = detect_missing_facts_fields(output_path)
    if missing:
        print_fn(f"\n⚠ {len(missing)} recommendation(s) for completeness:")
        for m in missing:
            print_fn(f"  → {m}")

    return brain


def _collect_section(section: dict, input_fn, print_fn) -> dict:
    """Collect answers for one section."""
    result = {}

    for q in section["questions"]:
        field = q["field"]

        if q.get("is_multiline_list"):
            print_fn(f"  {q['prompt']}")
            items = []
            while True:
                line = input_fn("  > ").strip()
                if not line:
                    break
                if is_placeholder(line):
                    print_fn("  ✗ Placeholders are not allowed.")
                    continue
                items.append(line)

            min_items = q.get("min_items", 0)
            while len(items) < min_items:
                print_fn(f"  ✗ {q.get('reject_msg', f'At least {min_items} item(s) required.')}")
                line = input_fn("  > ").strip()
                if line and not is_placeholder(line):
                    items.append(line)

            result["_list"] = items
            continue

        if q.get("is_role_list"):
            print_fn(f"  {q['prompt']}")
            roles = []
            while True:
                line = input_fn("  > ").strip()
                if not line:
                    break
                if ":" in line:
                    name, resp = line.split(":", 1)
                    roles.append({"name": name.strip(), "responsibility": resp.strip()})
                else:
                    print_fn("  ✗ Format: name:responsibility")
            result["_object_list"] = roles
            continue

        default = q.get("default", "")
        prompt_suffix = f" [{default}]" if default else ""
        prompt_text = f"  {q['prompt']}{prompt_suffix}: "

        while True:
            answer = input_fn(prompt_text).strip()
            if not answer and default:
                answer = default

            error = validate_answer(q, answer)
            if error:
                print_fn(f"  ✗ {error}")
                continue

            if answer:
                result[field] = answer
            break

    return result


def derive_facts_from_intent(intent: str) -> dict:
    """Derive partial facts from a natural language intent string.

    This creates a draft facts.yaml with what can be inferred,
    and marks everything else as unresolved.
    Returns a dict with filled fields and an 'unresolved' list.

    This is a heuristic-based approach. In production, this would
    be enhanced with LLM-assisted parsing.
    """
    intent_lower = intent.lower()
    brain = {
        "identity": {"name": "", "version": "0.1.0", "description": ""},
        "goal": {"purpose": intent, "scope": "", "out_of_scope": []},
        "stack": {"language": ""},
        "architecture": {"pattern": "", "reasoning": ""},
        "database": {"type": "", "connection": ""},
        "constraints": [],
        "success_criteria": [],
        "unresolved": [],
        "features": [],
        "services": [],
    }

    # --- Language detection ---
    lang_hints = {
        "python": ["python", "fastapi", "django", "flask", "pip", "uvicorn"],
        "typescript": ["typescript", "next", "node", "npm", "express", "nestjs", "deno"],
        "javascript": ["javascript", "vanilla js"],
        "go": ["golang", " go ", "gin", "fiber"],
        "rust": ["rust", "cargo", "actix", "axum"],
        "java": ["java", "spring", "springboot"],
        "csharp": ["c#", "csharp", ".net", "dotnet", "blazor"],
    }
    for lang, keywords in lang_hints.items():
        if any(kw in intent_lower for kw in keywords):
            brain["stack"]["language"] = lang
            break

    # --- Backend framework detection ---
    backend_hints = {
        "fastapi": "fastapi", "django": "django", "flask": "flask",
        "express": "express", "nestjs": "nestjs", "gin": "gin",
        "spring": "spring", "actix": "actix", "axum": "axum",
    }
    for keyword, framework in backend_hints.items():
        if keyword in intent_lower:
            brain["stack"]["backend"] = framework
            break

    # --- Frontend framework detection ---
    frontend_hints = {
        "vue": "vue", "react": "react", "svelte": "svelte",
        "angular": "angular", "next": "nextjs", "nuxt": "nuxt",
        "solid": "solidjs", "htmx": "htmx", "tailwind": "tailwind css",
    }
    detected_frontend = []
    for keyword, framework in frontend_hints.items():
        if keyword in intent_lower:
            detected_frontend.append(framework)
    if detected_frontend:
        brain["stack"]["frontend"] = " + ".join(detected_frontend)

    # --- Database detection ---
    db_hints = {
        "postgres": ["postgres", "postgresql", "pg"],
        "mongodb": ["mongo", "mongodb"],
        "sqlite": ["sqlite"],
        "mysql": ["mysql", "mariadb"],
        "redis": ["redis"],
        "dynamodb": ["dynamodb", "dynamo"],
        "supabase": ["supabase"],
    }
    db_found = False
    for db, keywords in db_hints.items():
        if any(kw in intent_lower for kw in keywords):
            brain["database"]["type"] = db
            db_found = True
            break
    # If no DB mentioned and it looks like a simple/demo project, default to none
    no_db_hints = ["no database", "no db", "json file", "file-based", "static",
                   "demo", "prototype", "proof of concept", "poc"]
    if not db_found:
        if any(h in intent_lower for h in no_db_hints):
            brain["database"]["type"] = "none"
            brain["database"]["connection"] = "none"

    # --- Architecture inference ---
    arch_hints = {
        "microservices": ["microservice", "micro-service"],
        "monolith": ["monolith", "monolithic"],
        "serverless": ["serverless", "lambda", "cloud function"],
        "hexagonal": ["hexagonal", "ports and adapters"],
        "event-driven": ["event-driven", "event driven", "message queue", "kafka"],
    }
    for pattern, keywords in arch_hints.items():
        if any(kw in intent_lower for kw in keywords):
            brain["architecture"]["pattern"] = pattern
            break
    # Infer layered if we detected both backend and frontend
    if not brain["architecture"]["pattern"]:
        has_backend = bool(brain["stack"].get("backend"))
        has_frontend = bool(brain["stack"].get("frontend"))
        if has_backend and has_frontend:
            brain["architecture"]["pattern"] = "layered"
            brain["architecture"]["reasoning"] = (
                f"Inferred from {brain['stack'].get('backend', '')} backend + "
                f"{brain['stack'].get('frontend', '')} frontend separation."
            )
        elif has_backend:
            brain["architecture"]["pattern"] = "layered"
            brain["architecture"]["reasoning"] = "Inferred from backend framework."

    # --- Deployment detection ---
    deploy_hints = {
        "render": ["render"], "vercel": ["vercel"], "netlify": ["netlify"],
        "aws": ["aws", "amazon"], "gcp": ["gcp", "google cloud"],
        "heroku": ["heroku"], "railway": ["railway"], "fly.io": ["fly.io", "flyio"],
        "docker": ["docker", "container"],
    }
    for platform, keywords in deploy_hints.items():
        if any(kw in intent_lower for kw in keywords):
            brain["services"] = [{
                "name": f"{platform}-deployment",
                "type": "deployment",
                "purpose": f"Deployed on {platform} (inferred from intent)",
            }]
            break

    # --- Tool/dependency detection ---
    tool_hints = {
        "openai": ["openai", "gpt", "gpt-4", "gpt-3", "chatgpt"],
        "anthropic": ["anthropic", "claude"],
        "langchain": ["langchain"],
        "llm": ["llm", "language model"],
    }
    detected_tools = []
    for tool, keywords in tool_hints.items():
        if any(kw in intent_lower for kw in keywords):
            detected_tools.append(tool)
    if detected_tools:
        brain.setdefault("tools", {})
        brain["tools"]["other"] = detected_tools

    # --- Runtime detection ---
    if brain["stack"]["language"] == "python":
        brain["stack"]["runtime"] = "python 3.12+"
        brain["stack"]["package_manager"] = "pip"
    elif brain["stack"]["language"] in ("typescript", "javascript"):
        brain["stack"]["runtime"] = "node 20+"
        brain["stack"]["package_manager"] = "npm"

    # --- Build unresolved list (only for things truly unknown) ---
    required_unresolved = []
    if not brain["stack"]["language"]:
        required_unresolved.append({
            "item": "Programming language",
            "reason": "Could not infer from intent",
            "blocking": True,
        })
    if not brain["database"]["type"]:
        required_unresolved.append({
            "item": "Database choice",
            "reason": "Could not infer from intent — specify a DB or 'none'",
            "blocking": True,
        })
    if not brain["architecture"]["pattern"]:
        required_unresolved.append({
            "item": "Architecture pattern",
            "reason": "Could not infer from intent",
            "blocking": True,
        })

    required_unresolved.append({
        "item": "Project name",
        "reason": "Must be explicitly chosen",
        "blocking": True,
    })

    # Always produce schema-valid constraints and success_criteria
    # with a single unresolved marker — never leave them empty
    if not brain["constraints"]:
        brain["constraints"] = ["UNRESOLVED — define project constraints before execution"]
        required_unresolved.append({
            "item": "Constraints",
            "reason": "Must be explicitly defined",
            "blocking": True,
        })
    if not brain["success_criteria"]:
        brain["success_criteria"] = ["UNRESOLVED — define success criteria before execution"]
        required_unresolved.append({
            "item": "Success criteria",
            "reason": "Must be explicitly defined",
            "blocking": True,
        })

    brain["unresolved"] = required_unresolved

    return brain


# Backward compat alias
derive_brain_from_intent = derive_facts_from_intent
