"""Markdown export implemented for milestone 2."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


def _inside(root: Path, value: Path) -> Path:
    root = root.resolve()
    if value.is_absolute() or ".." in value.parts:
        raise ValueError("path must be relative to workspace")
    candidate = (root / value).resolve()
    if candidate != root and root not in candidate.parents:
        raise ValueError("path escapes workspace")
    return candidate


def export_markdown(workspace: Path, journal: Path, output: Path) -> Path:
    source = _inside(workspace, journal)
    destination = _inside(workspace, output)
    title = source.stem.replace("-", " ").title()
    body = source.read_text(encoding="utf-8")
    rendered = f"# {title}\n\n{body.rstrip()}\n"
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{destination.name}.", dir=destination.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(rendered)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    except Exception:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise
    return destination
