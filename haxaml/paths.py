"""Shared canonical path resolution for FRAME files."""

from pathlib import Path


FRAME_DIR = ".haxaml"
ARCHIVE_DIR = "archive"


def frame_dir(project_dir: str | Path) -> Path:
    """Return the default FRAME directory for a project."""
    return Path(project_dir) / FRAME_DIR


def frame_path(project_dir: str | Path, filename: str) -> Path:
    """Return the default path for a FRAME file."""
    return frame_dir(project_dir) / filename


def archive_dir(project_dir: str | Path) -> Path:
    """Return the Haxaml-managed archive directory."""
    return frame_dir(project_dir) / ARCHIVE_DIR


def acts_history_path(project_dir: str | Path) -> Path:
    """Return the canonical hot/cold acts history archive path."""
    return archive_dir(project_dir) / "acts-history.yaml"


def detect_project_root(start_dir: str | Path = ".") -> Path | None:
    """Find the nearest ancestor that contains .haxaml/."""
    current = Path(start_dir).resolve()
    for candidate in [current, *current.parents]:
        if frame_dir(candidate).exists():
            return candidate
    return None


def resolve_frame_file(project_dir: str | Path, filename: str) -> Path | None:
    """Resolve a canonical FRAME file inside .haxaml/."""
    project = Path(project_dir)
    candidate = frame_path(project, filename)
    if candidate.exists():
        return candidate
    return None
