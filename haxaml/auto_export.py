"""Auto re-export — keeps agent-native files in sync with FRAME changes.

Provides:
- export_if_stale(): checks mtimes and re-exports only if FRAME files are newer
- install_git_hook(): writes a pre-commit hook that runs haxaml export (generic)
- watch_and_export(): polling watcher for dev use
"""

import os
import stat
import time
from pathlib import Path
from typing import Optional

from haxaml.paths import frame_dir, resolve_frame_file
from haxaml.export_engine import export_to_file, list_agents, AGENT_CONFIGS


FRAME_FILES = ["facts.yaml", "rules.yaml", "acts.yaml", "expect.yaml", "map.yaml"]


def _frame_mtime(project_dir: Path) -> Optional[float]:
    """Get the newest mtime across all FRAME files."""
    newest = None
    for name in FRAME_FILES:
        path = resolve_frame_file(project_dir, name)
        if path and path.exists():
            mt = path.stat().st_mtime
            if newest is None or mt > newest:
                newest = mt
    return newest


def _export_mtime(project_dir: Path) -> Optional[float]:
    """Get the oldest mtime across all exported agent files."""
    oldest = None
    for agent in AGENT_CONFIGS.values():
        p = project_dir / agent["filename"]
        if p.exists():
            mt = p.stat().st_mtime
            if oldest is None or mt < oldest:
                oldest = mt
    return oldest


def is_stale(project_dir: str) -> bool:
    """Check if any exported agent files are older than FRAME files."""
    p = Path(project_dir).resolve()
    frame_mt = _frame_mtime(p)
    if frame_mt is None:
        return False

    export_mt = _export_mtime(p)
    if export_mt is None:
        return True

    return frame_mt > export_mt


def export_if_stale(project_dir: str, agents: Optional[list[str]] = None) -> list[str]:
    """Re-export only if FRAME files are newer than exported files.

    Returns list of paths that were re-exported, empty if nothing was stale.
    """
    if not is_stale(project_dir):
        return []

    exported = []
    targets = agents or ["generic"]
    for agent in targets:
        try:
            path = export_to_file(project_dir, agent)
            exported.append(path)
        except (KeyError, FileNotFoundError, FileExistsError):
            continue

    return exported


def export_all(project_dir: str) -> list[str]:
    """Force re-export all agents regardless of staleness."""
    exported = []
    for agent in list_agents():
        try:
            path = export_to_file(project_dir, agent["name"])
            exported.append(path)
        except (KeyError, FileNotFoundError, FileExistsError):
            continue
    return exported


# ─── Git hook ────────────────────────────────────────────────────────────────


_HOOK_SCRIPT = """\
#!/bin/sh
# Haxaml auto-export pre-commit hook
# Re-exports FRAME files to agent-native formats before each commit.
# Installed by: haxaml install-hook

if command -v haxaml >/dev/null 2>&1; then
    haxaml export --quiet 2>/dev/null
    git add HAXAML.md 2>/dev/null
fi
"""


def install_git_hook(project_dir: str, force: bool = False) -> str:
    """Install a git pre-commit hook that auto-exports FRAME on commit.

    Returns a status message.
    """
    p = Path(project_dir).resolve()
    git_dir = p / ".git"

    if not git_dir.is_dir():
        return "✗ Not a git repository — no .git/ directory found."

    hooks_dir = git_dir / "hooks"
    hooks_dir.mkdir(exist_ok=True)
    hook_path = hooks_dir / "pre-commit"

    if hook_path.exists() and not force:
        content = hook_path.read_text()
        if "haxaml" in content.lower():
            return "✓ Haxaml pre-commit hook already installed."
        return (
            f"⚠ A pre-commit hook already exists at {hook_path}.\n"
            f"  Use --force to overwrite, or manually add the haxaml export line."
        )

    hook_path.write_text(_HOOK_SCRIPT)
    hook_path.chmod(hook_path.stat().st_mode | stat.S_IEXEC)

    return f"✓ Installed pre-commit hook at {hook_path}"


def uninstall_git_hook(project_dir: str) -> str:
    """Remove the haxaml pre-commit hook."""
    p = Path(project_dir).resolve()
    hook_path = p / ".git" / "hooks" / "pre-commit"

    if not hook_path.exists():
        return "✗ No pre-commit hook found."

    content = hook_path.read_text()
    if "haxaml" not in content.lower():
        return "✗ Pre-commit hook exists but was not installed by Haxaml."

    hook_path.unlink()
    return "✓ Removed Haxaml pre-commit hook."


# ─── File watcher ────────────────────────────────────────────────────────────


def watch_and_export(project_dir: str, interval: float = 2.0,
                     callback=None) -> None:
    """Poll .haxaml/ for changes and re-export when stale.

    This is a blocking loop intended for dev use. Ctrl+C to stop.
    callback is called with (exported_paths) after each re-export.
    """
    p = Path(project_dir).resolve()
    last_mtime = _frame_mtime(p)

    while True:
        time.sleep(interval)
        current_mtime = _frame_mtime(p)

        if current_mtime and (last_mtime is None or current_mtime > last_mtime):
            exported = export_if_stale(project_dir, agents=["generic"])
            last_mtime = current_mtime
            if callback and exported:
                callback(exported)
            elif exported:
                print(f"Re-exported {len(exported)} agent file(s)")
