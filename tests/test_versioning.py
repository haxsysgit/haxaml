"""Tests for centralized version helpers and release guard checks."""

import pytest

from haxaml.versioning import (
    project_version,
    mcp_launcher_version,
    release_version_snapshot,
    validate_release_versions,
)


def test_versions_are_aligned_in_repo():
    assert project_version() == mcp_launcher_version() == "0.4.5"


def test_release_snapshot_for_valid_tag():
    snap = release_version_snapshot("v0.4.5")
    assert snap["tag_version"] == "0.4.5"
    assert snap["versions_match"] is True
    assert snap["mcp_dependency_aligned"] is True


def test_validate_release_versions_rejects_mismatched_tag():
    with pytest.raises(ValueError, match="Tag/version mismatch"):
        validate_release_versions("v9.9.9")
