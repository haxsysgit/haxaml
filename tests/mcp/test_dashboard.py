"""Tests for the read-only local dashboard."""

import pytest
import yaml
from haxaml.paths import acts_history_path
from haxaml.runtime_cache import runtime_cache

pytest.importorskip("jinja2")
pytest.importorskip("starlette.testclient")
pytest.importorskip("haxaml_ui")

from starlette.testclient import TestClient

from haxaml_ui.dashboard import create_dashboard_app


def test_overview_renders_health_progress_and_archive_signals(governed_project):
    app = create_dashboard_app(project_dir=str(governed_project))
    client = TestClient(app)

    response = client.get("/")
    assert response.status_code == 200
    assert "Overview" in response.text
    assert "test-project" in response.text
    assert "Archive" in response.text
    assert "Map Policy" in response.text


def test_all_frame_pages_render_read_only_views(governed_project):
    app = create_dashboard_app(project_dir=str(governed_project))
    client = TestClient(app)

    for name in ("facts", "rules", "acts", "expect", "map"):
        response = client.get(f"/frame/{name}")
        assert response.status_code == 200
        assert "Read-only" in response.text
        assert f"{name}.yaml" in response.text


def test_archive_overview_is_shallow_and_detail_drilldown_works(monkeypatch, governed_project):
    archive_path = acts_history_path(governed_project)
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    archive_path.write_text(
        yaml.dump(
            {
                "metadata": {
                    "version": "0.6.7",
                    "managed_by": "haxaml",
                    "archive_mode": "manual",
                    "counts": {"runs": 1, "sessions": 0, "verifications": 0},
                },
                "index": [
                    {
                        "kind": "run",
                        "id": "run-1",
                        "task": "dashboard archive",
                        "summary": "archived summary",
                        "status_or_result": "success",
                    }
                ],
                "history": {
                    "runs": [{"id": "run-1", "task": "dashboard archive", "changes": "full archived body"}],
                    "sessions": [],
                    "verifications": [],
                },
            },
            default_flow_style=False,
            sort_keys=False,
        )
    )
    cache = runtime_cache()
    cache.reset()

    calls = {"detail": 0}
    original = cache.load_archive_record_details

    def counted_detail(*args, **kwargs):
        calls["detail"] += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(cache, "load_archive_record_details", counted_detail)
    app = create_dashboard_app(project_dir=str(governed_project))
    client = TestClient(app)

    overview = client.get("/archive")
    assert overview.status_code == 200
    assert "Archive Overview" in overview.text
    assert calls["detail"] == 0

    detail = client.get("/archive/run/run-1")
    assert detail.status_code == 200
    assert "full archived body" in detail.text
    assert calls["detail"] == 1


def test_dashboard_exposes_only_get_routes(governed_project):
    app = create_dashboard_app(project_dir=str(governed_project))
    methods = {method for route in app.routes for method in getattr(route, "methods", set())}
    assert "POST" not in methods
    assert "PUT" not in methods
    assert "PATCH" not in methods
    assert "DELETE" not in methods
