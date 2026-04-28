"""Runtime version helpers.

Single source of truth for package version is pyproject metadata.
Runtime reads installed package metadata first, then falls back to pyproject.toml.
Release checks are centralized here so CI and runtime use the same logic.
"""

from __future__ import annotations

from functools import lru_cache
from importlib.metadata import PackageNotFoundError, version as pkg_version
from pathlib import Path
import re
import tomllib


PACKAGE_NAME = "haxaml"
MCP_LAUNCHER_PACKAGE = "haxaml-mcp"
REPO_ROOT = Path(__file__).resolve().parent.parent
PROJECT_PYPROJECT = REPO_ROOT / "pyproject.toml"
MCP_PYPROJECT = REPO_ROOT / "packages" / "haxaml-mcp" / "pyproject.toml"


def _load_project(path: Path) -> dict:
    with open(path, "rb") as f:
        return tomllib.load(f).get("project", {})


@lru_cache(maxsize=1)
def project_version() -> str:
    """Return the core package version declared in pyproject.toml."""
    return str(_load_project(PROJECT_PYPROJECT).get("version", "0.0.0"))


@lru_cache(maxsize=1)
def mcp_launcher_version() -> str:
    """Return the launcher package version declared in packages/haxaml-mcp/pyproject.toml."""
    return str(_load_project(MCP_PYPROJECT).get("version", "0.0.0"))


@lru_cache(maxsize=1)
def get_version() -> str:
    """Return runtime package version from a single authoritative source."""
    try:
        return pkg_version(PACKAGE_NAME)
    except PackageNotFoundError:
        if PROJECT_PYPROJECT.exists():
            return project_version()
    return "0.0.0"


def version_spec(package: str, target_version: str | None = None) -> str:
    """Build an install/upgrade spec for a package."""
    if target_version:
        return f"{package}=={target_version}"
    return package


def release_version_snapshot(tag_ref: str | None = None) -> dict[str, object]:
    """Return deterministic version alignment details for release checks."""
    core = project_version()
    launcher = mcp_launcher_version()
    mcp_deps = _load_project(MCP_PYPROJECT).get("dependencies", [])
    expected_dep_prefix = f"{PACKAGE_NAME}>={core}"
    dep_aligned = any(str(dep).startswith(expected_dep_prefix) for dep in mcp_deps)

    tag_version = None
    if tag_ref:
        match = re.fullmatch(r"v(\d+\.\d+\.\d+)", tag_ref.strip())
        if not match:
            raise ValueError(f"Invalid tag format '{tag_ref}'. Expected vX.Y.Z.")
        tag_version = match.group(1)

    return {
        "tag_ref": tag_ref,
        "tag_version": tag_version,
        "core_version": core,
        "mcp_version": launcher,
        "versions_match": core == launcher,
        "mcp_dependency_aligned": dep_aligned,
        "expected_dependency_prefix": expected_dep_prefix,
    }


def validate_release_versions(tag_ref: str | None = None) -> dict[str, object]:
    """Validate release version alignment and raise ValueError on mismatch."""
    snapshot = release_version_snapshot(tag_ref=tag_ref)
    if not snapshot["versions_match"]:
        raise ValueError(
            "Version mismatch: "
            f"{PACKAGE_NAME}={snapshot['core_version']} vs {MCP_LAUNCHER_PACKAGE}={snapshot['mcp_version']}"
        )
    if tag_ref and snapshot["tag_version"] != snapshot["core_version"]:
        raise ValueError(
            "Tag/version mismatch: "
            f"tag={snapshot['tag_version']} vs pyproject={snapshot['core_version']}"
        )
    if not snapshot["mcp_dependency_aligned"]:
        raise ValueError(
            f"{MCP_LAUNCHER_PACKAGE} dependency must start with "
            f"'{snapshot['expected_dependency_prefix']}', but it does not."
        )
    return snapshot
