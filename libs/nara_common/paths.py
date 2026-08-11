"""Repository path helpers."""

from __future__ import annotations

from pathlib import Path


def find_project_root(start: Path) -> Path:
    """Return the nearest directory pinned by a regular ``.nara-root`` file.

    The input is inspected before its ancestors. If no marker is found, the
    legacy convention treats the input's parent as the project root. Paths
    remain lexical: this helper deliberately does not resolve or canonicalize
    them.
    """
    for candidate in (start, *start.parents):
        if (candidate / ".nara-root").is_file():
            return candidate
    return start.parent
