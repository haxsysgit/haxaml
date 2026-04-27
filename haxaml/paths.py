"""Shared path resolution for FRAME files."""

from pathlib import Path


FRAME_DIR = ".haxaml"


def frame_dir(project_dir: str | Path) -> Path:
    """Return the default FRAME directory for a project."""
    return Path(project_dir) / FRAME_DIR


def frame_path(project_dir: str | Path, filename: str) -> Path:
    """Return the default path for a FRAME file."""
    return frame_dir(project_dir) / filename


def resolve_frame_file(project_dir: str | Path, filename: str,
                       legacy_filename: str | None = None) -> Path | None:
    """Resolve a FRAME file across new, root, and legacy locations.

    Search order:
    1. .haxaml/<filename>        canonical location
    2. ./<filename>              root compatibility
    3. .haxaml/<legacy_filename> legacy compatibility
    4. ./<legacy_filename>       legacy root compatibility
    """
    project = Path(project_dir)
    candidates = [
        frame_path(project, filename),
        project / filename,
    ]
    if legacy_filename:
        candidates.extend([
            frame_path(project, legacy_filename),
            project / legacy_filename,
        ])

    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None
