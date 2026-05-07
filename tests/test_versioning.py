"""Tests for centralized version helpers and release guard checks."""

from pathlib import Path

import pytest

from haxaml.versioning import (
    PACKAGE_NAME,
    project_version,
    mcp_launcher_version,
    ui_package_version,
    release_version_snapshot,
    validate_release_versions,
)


def test_versions_are_aligned_in_repo():
    assert project_version() == mcp_launcher_version()
    assert project_version() == ui_package_version()


def test_release_snapshot_for_valid_tag():
    current = project_version()
    snap = release_version_snapshot(f"v{current}")
    assert snap["tag_version"] == current
    assert snap["versions_match"] is True
    assert snap["mcp_dependency_aligned"] is True
    assert snap["ui_dependency_aligned"] is True


def test_validate_release_versions_rejects_mismatched_tag():
    with pytest.raises(ValueError, match="Tag/version mismatch"):
        validate_release_versions("v9.9.9")


def test_release_snapshot_accepts_prerelease_tag():
    snap = release_version_snapshot("v0.6.7b1")
    assert snap["tag_version"] == "0.6.7b1"


def test_get_version_prefers_local_pyproject(monkeypatch):
    import haxaml.versioning as versioning

    versioning.get_version.cache_clear()
    monkeypatch.setattr(versioning, "project_version", lambda: "1.2.3")
    monkeypatch.setattr(versioning, "pkg_version", lambda _pkg: "9.9.9")
    assert versioning.get_version() == "1.2.3"


def test_get_version_falls_back_to_installed_metadata_when_no_local_pyproject(monkeypatch):
    import haxaml.versioning as versioning

    versioning.get_version.cache_clear()
    monkeypatch.setattr(versioning, "PROJECT_PYPROJECT", Path("/tmp/does-not-exist-pyproject.toml"))
    monkeypatch.setattr(versioning, "pkg_version", lambda pkg: "2.3.4" if pkg == PACKAGE_NAME else "0.0.0")
    assert versioning.get_version() == "2.3.4"
