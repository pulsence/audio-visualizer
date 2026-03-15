"""
File utility functions.
"""

from pathlib import Path


def ensure_parent_dir(path: Path) -> None:
    """
    Ensure parent directory exists for a file path.

    Args:
        path: File path whose parent directory should exist
    """
    path.parent.mkdir(parents=True, exist_ok=True)
