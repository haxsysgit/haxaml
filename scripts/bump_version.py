#!/usr/bin/env python3
"""Bump version across all haxaml package manifests atomically.

Usage:
    uv run python scripts/bump_version.py 0.7.0

Updates:
  - pyproject.toml (haxaml)
  - packages/haxaml-mcp/pyproject.toml (haxaml-mcp version + dependency range)
  - packages/haxaml-ui/pyproject.toml (haxaml-ui version + dependency range)

Then validates alignment via versioning.validate_release_versions().
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CORE_PYPROJECT = REPO_ROOT / "pyproject.toml"
MCP_PYPROJECT = REPO_ROOT / "packages" / "haxaml-mcp" / "pyproject.toml"
UI_PYPROJECT = REPO_ROOT / "packages" / "haxaml-ui" / "pyproject.toml"


def _bump(path: Path, pattern: str, replacement: str, *, count: int = 1) -> None:
    text = path.read_text(encoding="utf-8")
    new_text, n = re.subn(pattern, replacement, text, count=count, flags=re.MULTILINE)
    if n == 0:
        raise ValueError(f"Pattern not found in {path}: {pattern!r}")
    path.write_text(new_text, encoding="utf-8")
    print(f"  Updated {path.relative_to(REPO_ROOT)} ({n} replacements)")


def bump(new_version: str) -> None:
    if not re.fullmatch(r"\d+\.\d+\.\d+(?:a\d+|b\d+|rc\d+)?", new_version):
        raise ValueError(f"Invalid version format: {new_version!r}. Expected X.Y.Z or prerelease like X.Y.Zb0")

    major, minor, _ = new_version.split(".")
    next_minor = f"{major}.{int(minor) + 1}.0"

    print(f"Bumping to {new_version} (mcp dep range: >={new_version},<{next_minor})")

    _bump(
        CORE_PYPROJECT,
        r'^(version = ")[^"]+(")$',
        rf'\g<1>{new_version}\g<2>',
    )
    _bump(
        MCP_PYPROJECT,
        r'^(version = ")[^"]+(")$',
        rf'\g<1>{new_version}\g<2>',
    )
    _bump(
        MCP_PYPROJECT,
        r'"haxaml>=[^"]+,<[\d.]+"',
        f'"haxaml>={new_version},<{next_minor}"',
    )
    _bump(
        UI_PYPROJECT,
        r'^(version = ")[^"]+(")$',
        rf'\g<1>{new_version}\g<2>',
    )
    _bump(
        UI_PYPROJECT,
        r'"haxaml>=[^"]+,<[\d.]+"',
        f'"haxaml>={new_version},<{next_minor}"',
    )
    _bump(
        CORE_PYPROJECT,
        r'"haxaml-ui==[^"]+"',
        f'"haxaml-ui=={new_version}"',
        count=0,
    )
    _bump(
        CORE_PYPROJECT,
        r'"haxaml-mcp==[^"]+"',
        f'"haxaml-mcp=={new_version}"',
        count=0,
    )

    # Invalidate lru_cache so validate_release_versions re-reads fresh files
    import haxaml.versioning as v
    v.project_version.cache_clear()
    v.mcp_launcher_version.cache_clear()
    v.ui_package_version.cache_clear()
    v.get_version.cache_clear()

    from haxaml.versioning import validate_release_versions
    snapshot = validate_release_versions(f"v{new_version}")
    print(f"  Validation OK: {snapshot}")
    print(f"\nDone. Commit with:")
    print(
        f"  git add {CORE_PYPROJECT.relative_to(REPO_ROOT)} "
        f"{MCP_PYPROJECT.relative_to(REPO_ROOT)} {UI_PYPROJECT.relative_to(REPO_ROOT)}"
    )
    print(f"  git commit -m 'chore: bump version to {new_version}'")
    print(f"  git tag -a v{new_version} -m 'v{new_version}'")
    print(f"  git push origin main --tags")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <X.Y.Z>", file=sys.stderr)
        sys.exit(1)
    bump(sys.argv[1])
