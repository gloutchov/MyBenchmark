"""Filesystem boundary for SafeNotes."""

from __future__ import annotations

from pathlib import Path


def resolve_workspace_path(root: str | Path, relative_path: str | Path) -> Path:
    """Return a path intended to live below root."""
    return Path(root) / Path(relative_path)


def atomic_write_text(root: str | Path, relative_path: str | Path, text: str) -> Path:
    """Write text to a workspace path and return the destination."""
    destination = resolve_workspace_path(root, relative_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(text, encoding="utf-8")
    return destination
