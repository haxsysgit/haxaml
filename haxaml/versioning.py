"""Runtime version helpers.

Single source of truth for package version is pyproject metadata.
Runtime reads installed package metadata first, then falls back to pyproject.toml.
"""

from __future__ import annotations

from functools import lru_cache
from importlib.metadata import PackageNotFoundError, version as pkg_version
from pathlib import Path
import tomllib


PACKAGE_NAME = "haxaml"
MCP_LAUNCHER_PACKAGE = "haxaml-mcp"


@lru_cache(maxsize=1)
def get_version() -> str:
    """Return runtime package version from a single authoritative source."""
    try:
        return pkg_version(PACKAGE_NAME)
    except PackageNotFoundError:
        pyproject = Path(__file__).resolve().parent.parent / "pyproject.toml"
        if pyproject.exists():
            with open(pyproject, "rb") as f:
                data = tomllib.load(f)
            return str(data.get("project", {}).get("version", "0.0.0"))
    return "0.0.0"


def version_spec(package: str, target_version: str | None = None) -> str:
    """Build an install/upgrade spec for a package."""
    if target_version:
        return f"{package}=={target_version}"
    return package
