"""Shared canonical path resolution for FRAME files."""

from pathlib import Path


FRAME_DIR = ".haxaml"


def frame_dir(project_dir: str | Path) -> Path:
    """Return the default FRAME directory for a project."""
    return Path(project_dir) / FRAME_DIR


def frame_path(project_dir: str | Path, filename: str) -> Path:
    """Return the default path for a FRAME file."""
    return frame_dir(project_dir) / filename


def resolve_frame_file(project_dir: str | Path, filename: str) -> Path | None:
    """Resolve a canonical FRAME file inside .haxaml/."""
    project = Path(project_dir)
    candidate = frame_path(project, filename)
    if candidate.exists():
        return candidate
    return None
