"""Read-only local dashboard for FRAME projects."""

from __future__ import annotations

from html import escape
from pathlib import Path
import webbrowser

import uvicorn
import yaml
from jinja2 import DictLoader, Environment, select_autoescape
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, Response
from starlette.routing import Route

from haxaml.frame_model import FrameModel
from haxaml.map_policy import evaluate_map_complexity, format_map_complexity_summary, map_complexity_issues
from haxaml.lifecycle_state import expect_sync_state
from haxaml.paths import detect_project_root, frame_path
from haxaml.reconcile import reconcile_derivation
from haxaml.runner import ExecutionRunner
from haxaml.runtime_cache import runtime_cache
from haxaml.state_manager import StateManager
from haxaml.validator import frame_consistency_report, semantic_validate


DEFAULT_DASHBOARD_HOST = "127.0.0.1"
DEFAULT_DASHBOARD_PORT = 8421
FRAME_PAGE_ORDER = ["facts", "rules", "acts", "expect", "map"]


TEMPLATES = {
    "base.html": """
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{{ title }}</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="/static/app.css">
  </head>
  <body>
    <header class="site-header">
      <div>
        <p class="eyebrow">Haxaml Dashboard</p>
        <h1>{{ heading }}</h1>
        <p class="meta">{{ project_dir }}</p>
      </div>
      <div class="pill-row">
        <span class="pill">{{ "Read-only" if read_only else "Mutable" }}</span>
        {% if project_name %}<span class="pill accent">{{ project_name }}</span>{% endif %}
      </div>
    </header>
    <nav class="nav">
      <a href="/">Overview</a>
      {% for item in frame_nav %}
      <a href="/frame/{{ item }}">{{ item }}</a>
      {% endfor %}
      <a href="/archive">archive</a>
    </nav>
    <main class="page">
      {{ body | safe }}
    </main>
  </body>
</html>
""",
}


CSS = """
:root {
  --bg: #f4f0e8;
  --panel: #fffaf2;
  --ink: #1d1b19;
  --muted: #6a645c;
  --line: #d8cfc1;
  --accent: #0d6b57;
  --accent-2: #2557a7;
  --accent-3: #a24f2a;
  --accent-soft: #d9f0ea;
  --accent-2-soft: #dfe8fb;
  --warn: #9b4d19;
  --warn-soft: #f7e1cf;
  --mono: "JetBrains Mono", "SFMono-Regular", monospace;
  --sans: "IBM Plex Sans", "Segoe UI", sans-serif;
}
body {
  margin: 0;
  background:
    radial-gradient(circle at top left, rgba(13, 107, 87, 0.12), transparent 34%),
    linear-gradient(180deg, #efe7da 0%, var(--bg) 36%, #f8f5ef 100%);
  color: var(--ink);
  font-family: var(--sans);
}
.site-header, .nav, .page {
  max-width: 1100px;
  margin: 0 auto;
  padding-left: 1rem;
  padding-right: 1rem;
}
.site-header {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  padding-top: 2rem;
}
.eyebrow {
  margin: 0 0 .35rem;
  letter-spacing: .08em;
  text-transform: uppercase;
  color: var(--muted);
  font-size: .8rem;
}
h1, h2, h3 { margin: 0; }
.meta, .subtle { color: var(--muted); }
.pill-row {
  display: flex;
  gap: .5rem;
  align-items: start;
  flex-wrap: wrap;
}
.pill {
  border: 1px solid var(--line);
  background: var(--panel);
  border-radius: 999px;
  padding: .45rem .8rem;
  font-size: .9rem;
}
.pill.accent {
  border-color: var(--accent);
  background: var(--accent-soft);
}
.pill-row .pill:nth-child(3n+2) {
  border-color: var(--accent-2);
  background: var(--accent-2-soft);
}
.nav {
  display: flex;
  gap: .6rem;
  flex-wrap: wrap;
  padding-top: 1rem;
  padding-bottom: 1rem;
}
.nav a, .button-link {
  color: var(--ink);
  text-decoration: none;
  border: 1px solid var(--line);
  background: rgba(255, 255, 255, .68);
  padding: .55rem .8rem;
  border-radius: 999px;
  transition: transform .16s ease, border-color .16s ease, background .16s ease;
}
.nav a:nth-child(3n+1) {
  border-color: rgba(13, 107, 87, .3);
}
.nav a:nth-child(3n+2) {
  border-color: rgba(37, 87, 167, .28);
}
.nav a:nth-child(3n) {
  border-color: rgba(162, 79, 42, .24);
}
.nav a:hover, .button-link:hover {
  transform: translateY(-1px);
  background: linear-gradient(180deg, rgba(255,255,255,.95), rgba(245,239,229,.96));
}
.page {
  padding-bottom: 2rem;
}
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 1rem;
}
.card, .panel, details {
  background: rgba(255, 250, 242, .88);
  border: 1px solid var(--line);
  border-radius: 18px;
  padding: 1rem;
  box-shadow: 0 10px 30px rgba(54, 43, 29, 0.04);
}
.card h3, .panel h2 { margin-bottom: .4rem; }
.plain-list {
  margin: .6rem 0 0;
  padding-left: 1rem;
}
.plain-list li {
  margin: .3rem 0;
}
.warning {
  border-color: var(--warn);
  background: var(--warn-soft);
}
pre, code {
  font-family: var(--mono);
}
pre {
  overflow-x: auto;
  white-space: pre-wrap;
  background: #f7f3ec;
  padding: 1rem;
  border-radius: 12px;
  border: 1px solid #e5dccf;
}
.stack {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}
.toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: .6rem;
  margin-bottom: 1rem;
}
.section-summary {
  font-weight: 600;
}
@media (max-width: 720px) {
  .site-header {
    flex-direction: column;
  }
}
"""


_TEMPLATE_ENV = Environment(
    loader=DictLoader(TEMPLATES),
    autoescape=select_autoescape(["html", "xml"]),
)


def resolve_dashboard_project_dir(project_dir: str = ".") -> Path:
    resolved = detect_project_root(project_dir)
    if resolved is None:
        raise FileNotFoundError(f"No .haxaml directory found from {Path(project_dir).resolve()}")
    return resolved


def dashboard_url(host: str, port: int) -> str:
    return f"http://{host}:{port}/"


def run_dashboard_server(
    *,
    project_dir: str,
    host: str = DEFAULT_DASHBOARD_HOST,
    port: int = DEFAULT_DASHBOARD_PORT,
    open_browser: bool = True,
    read_only: bool = True,
) -> str:
    app = create_dashboard_app(project_dir=project_dir, read_only=read_only)
    url = dashboard_url(host, port)
    if open_browser:
        webbrowser.open(url)
    uvicorn.run(app, host=host, port=port, log_level="warning")
    return url


def main() -> None:
    run_dashboard_server(project_dir=".")


def create_dashboard_app(*, project_dir: str, read_only: bool = True) -> Starlette:
    root = resolve_dashboard_project_dir(project_dir)
    app = Starlette(
        debug=False,
        routes=[
            Route("/", _overview_page),
            Route("/frame/{frame_name}", _frame_page),
            Route("/archive", _archive_page),
            Route("/archive/{kind}/{record_id}", _archive_detail_page),
            Route("/static/app.css", _css_asset),
        ],
    )
    app.state.project_dir = str(root)
    app.state.read_only = bool(read_only)
    return app


def _render_page(
    request: Request,
    *,
    title: str,
    heading: str,
    body: str,
    project_name: str = "",
) -> HTMLResponse:
    template = _TEMPLATE_ENV.get_template("base.html")
    return HTMLResponse(
        template.render(
            title=title,
            heading=heading,
            body=body,
            project_dir=request.app.state.project_dir,
            project_name=project_name,
            read_only=request.app.state.read_only,
            frame_nav=FRAME_PAGE_ORDER,
        )
    )


async def _css_asset(_: Request) -> Response:
    return Response(CSS, media_type="text/css")


def _render_card(title: str, value: str, detail: str = "", *, warning: bool = False) -> str:
    detail_html = f"<p class='subtle'>{escape(detail)}</p>" if detail else ""
    klass = "card warning" if warning else "card"
    return f"<section class='{klass}'><h3>{escape(title)}</h3><p>{escape(value)}</p>{detail_html}</section>"


def _overview_body(project_dir: str) -> tuple[str, str]:
    frame = FrameModel.load(project_dir)
    project_name = str(((frame.facts or {}).get("identity") or {}).get("name", "")).strip()
    runner = ExecutionRunner(project_dir)
    health = runner.get_project_health()
    stats = StateManager(str(frame_path(project_dir, "acts.yaml"))).get_stats() if frame.has_acts() else {}
    archive_index = runtime_cache().get_archive_index(project_dir)
    reconcile = reconcile_derivation(project_dir)
    semantic = semantic_validate(frame)
    consistency = frame_consistency_report(frame)
    map_assessment = evaluate_map_complexity(project_dir)
    map_errors, map_warnings = map_complexity_issues(map_assessment)
    sync_state = expect_sync_state(frame.acts or {})
    cards = [
        _render_card("Ready", "yes" if health.get("ready") else "no", "Validation and lifecycle readiness", warning=not health.get("ready")),
        _render_card("Context Tokens", str(health.get("context_tokens", 0)), "Current full-context size"),
        _render_card("Archive", f"{len(archive_index.index)} indexed records", "Shallow index loaded from archive"),
        _render_card("Map Policy", format_map_complexity_summary(map_assessment), "Complexity and map expectation", warning=bool(map_errors)),
        _render_card("Runs", str(stats.get("total_runs", 0)), "Hot plus archived"),
        _render_card("Active Task", str(stats.get("active_task", "none")), "Current human-facing state"),
    ]
    warnings: list[str] = []
    warnings.extend(str(item) for item in health.get("errors", []))
    warnings.extend(str(item) for item in semantic.blocking)
    warnings.extend(str(item) for item in semantic.warnings)
    warnings.extend(str(item.get("message", "")) for item in consistency.get("findings", []))
    warnings.extend(str(item) for item in map_warnings)
    if sync_state.get("required"):
        warnings.append(
            f"expect.yaml sync pending for run {sync_state.get('pending_run_id') or 'unknown'}."
        )
    warnings = [item for item in warnings if item]
    recent_decisions = (frame.acts or {}).get("decisions", []) if isinstance(frame.acts, dict) else []
    recent_runs = archive_index.index[-5:] if archive_index.index else []
    body = [
        "<section class='grid'>",
        *cards,
        "</section>",
        "<section class='panel stack'>",
        "<div><h2>Signals</h2><p class='subtle'>Overview-first and read-only. Use drilldown pages for full YAML.</p></div>",
        "<ul class='plain-list'>",
        f"<li>Project: {escape(project_name or '(unnamed)')}</li>",
        f"<li>Phase: {escape(str(stats.get('current_phase', 'unknown')))}</li>",
        f"<li>Archive mode: {escape(str(stats.get('archive_mode', 'manual')))}</li>",
        f"<li>Reconcile: {escape(str(reconcile.get('human_summary', 'No reconcile summary')))}</li>",
        "</ul>",
        "</section>",
    ]
    if warnings:
        body.extend(
            [
                "<section class='panel warning'>",
                "<h2>Lifecycle And Drift Warnings</h2>",
                "<ul class='plain-list'>",
                *[f"<li>{escape(item)}</li>" for item in warnings[:12]],
                "</ul>",
                "</section>",
            ]
        )
    body.extend(
        [
            "<section class='grid'>",
            "<div class='panel'><h2>Recent Decisions</h2><ul class='plain-list'>",
            *[
                f"<li>{escape(str(item.get('decision', '')))}"
                f"{' — ' + escape(str(item.get('reasoning', ''))) if item.get('reasoning') else ''}</li>"
                for item in recent_decisions[-5:]
                if isinstance(item, dict)
            ],
            "</ul></div>",
            "<div class='panel'><h2>Archive Summary</h2><ul class='plain-list'>",
            *[
                f"<li><a href='/archive/{escape(str(item.get('kind', '')))}"
                f"/{escape(str(item.get('id', '')))}'>{escape(str(item.get('id', '')))}</a> "
                f"{escape(str(item.get('summary', '')))}</li>"
                for item in recent_runs
            ],
            "</ul></div>",
            "</section>",
        ]
    )
    return "".join(body), project_name


async def _overview_page(request: Request) -> HTMLResponse:
    body, project_name = _overview_body(request.app.state.project_dir)
    return _render_page(
        request,
        title="Haxaml Dashboard",
        heading="Overview",
        body=body,
        project_name=project_name,
    )


def _frame_body(project_dir: str, frame_name: str, q: str = "", view: str = "human") -> tuple[str, str]:
    frame = FrameModel.load(project_dir)
    data = frame.frame_file(frame_name)
    path = frame_path(project_dir, f"{frame_name}.yaml")
    project_name = str((((frame.facts or {}).get("identity")) or {}).get("name", "")).strip()
    filter_text = q.strip().lower()
    if view == "raw":
        raw = yaml.dump(data or {}, default_flow_style=False, sort_keys=False)
        return (
            "<section class='toolbar'>"
            f"<a class='button-link' href='/frame/{frame_name}?view=human'>Human view</a>"
            f"<span class='pill'>{escape(str(path))}</span></section>"
            f"<pre>{escape(raw)}</pre>",
            project_name,
        )

    blocks: list[str] = [
        "<section class='toolbar'>"
        f"<a class='button-link' href='/frame/{frame_name}?view=raw'>Raw YAML</a>"
        f"<span class='pill'>{escape(str(path))}</span>"
        "</section>"
    ]
    if not isinstance(data, dict):
        blocks.append(f"<section class='panel warning'><h2>{escape(frame_name)}</h2><p>File is missing.</p></section>")
        return "".join(blocks), project_name

    for key, value in data.items():
        preview = yaml.dump(value, default_flow_style=False, sort_keys=False).strip()
        haystack = f"{key}\n{preview}".lower()
        if filter_text and filter_text not in haystack:
            continue
        blocks.append(
            "<details open>"
            f"<summary class='section-summary'>{escape(str(key))}</summary>"
            f"<pre>{escape(preview)}</pre>"
            "</details>"
        )
    if len(blocks) == 1:
        blocks.append("<section class='panel'><p>No sections matched this filter.</p></section>")
    return "".join(blocks), project_name


async def _frame_page(request: Request) -> HTMLResponse:
    frame_name = request.path_params["frame_name"]
    if frame_name not in FRAME_PAGE_ORDER:
        return HTMLResponse("Not found", status_code=404)
    body, project_name = _frame_body(
        request.app.state.project_dir,
        frame_name,
        q=str(request.query_params.get("q", "")),
        view=str(request.query_params.get("view", "human")),
    )
    return _render_page(
        request,
        title=f"FRAME: {frame_name}",
        heading=f"{frame_name}.yaml",
        body=body,
        project_name=project_name,
    )


def _archive_body(project_dir: str, q: str = "") -> tuple[str, str]:
    frame = FrameModel.load(project_dir)
    project_name = str((((frame.facts or {}).get("identity")) or {}).get("name", "")).strip()
    archive_index = runtime_cache().get_archive_index(project_dir)
    if not archive_index.exists:
        return "<section class='panel'><h2>Archive</h2><p>No archive file found.</p></section>", project_name
    filter_text = q.strip().lower()
    items = archive_index.index
    if filter_text:
        items = [
            item for item in items
            if filter_text in yaml.dump(item, default_flow_style=False, sort_keys=False).lower()
        ]
    counts = archive_index.metadata.get("counts", {})
    body = [
        "<section class='panel'>",
        "<h2>Archive Overview</h2>",
        "<ul class='plain-list'>",
        f"<li>Runs: {int(counts.get('runs', 0) or 0)}</li>",
        f"<li>Sessions: {int(counts.get('sessions', 0) or 0)}</li>",
        f"<li>Verifications: {int(counts.get('verifications', 0) or 0)}</li>",
        "</ul>",
        "</section>",
        "<section class='panel'><h2>Indexed Records</h2><ul class='plain-list'>",
    ]
    for item in reversed(items[-25:]):
        kind = str(item.get("kind", "")).strip()
        record_id = str(item.get("id", "")).strip()
        body.append(
            f"<li><a href='/archive/{escape(kind)}/{escape(record_id)}'>{escape(record_id or kind)}</a> "
            f"{escape(str(item.get('summary', '')))}</li>"
        )
    body.append("</ul></section>")
    return "".join(body), project_name


async def _archive_page(request: Request) -> HTMLResponse:
    body, project_name = _archive_body(
        request.app.state.project_dir,
        q=str(request.query_params.get("q", "")),
    )
    return _render_page(
        request,
        title="Archive",
        heading="Archive",
        body=body,
        project_name=project_name,
    )


async def _archive_detail_page(request: Request) -> HTMLResponse:
    kind = str(request.path_params["kind"])
    record_id = str(request.path_params["record_id"])
    record = runtime_cache().load_archive_record_details(request.app.state.project_dir, kind, record_id)
    if record is None:
        return HTMLResponse("Not found", status_code=404)
    frame = FrameModel.load(request.app.state.project_dir)
    project_name = str((((frame.facts or {}).get("identity")) or {}).get("name", "")).strip()
    body = (
        f"<section class='toolbar'><a class='button-link' href='/archive'>Back to archive</a></section>"
        f"<section class='panel'><h2>{escape(kind)}:{escape(record_id)}</h2>"
        f"<pre>{escape(yaml.dump(record, default_flow_style=False, sort_keys=False))}</pre></section>"
    )
    return _render_page(
        request,
        title=f"Archive {kind}:{record_id}",
        heading=f"Archive {kind}:{record_id}",
        body=body,
        project_name=project_name,
    )
