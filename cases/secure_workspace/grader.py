#!/usr/bin/env python3
from __future__ import annotations

import importlib
import inspect
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


workspace = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(workspace / "src"))
checks: list[dict] = []


def check(name: str, points: float, test, detail: str = "") -> None:
    try:
        passed = bool(test())
        result_detail = detail if passed else (detail or "condizione non soddisfatta")
    except Exception as exc:
        passed = False
        result_detail = f"{type(exc).__name__}: {exc}"
    checks.append({"id": name, "points": points, "earned": points if passed else 0, "detail": result_detail})


try:
    module = importlib.import_module("safenotes")
    resolve_workspace_path = module.resolve_workspace_path
    atomic_write_text = module.atomic_write_text
    redact_message = module.redact_message
except Exception as exc:
    resolve_workspace_path = atomic_write_text = redact_message = None
    import_error = str(exc)
else:
    import_error = ""

check("package_import", 3, lambda: resolve_workspace_path is not None, import_error)


def rejects(root: Path, value: str | Path) -> bool:
    try:
        resolve_workspace_path(root, value)
    except (ValueError, OSError):
        return True
    return False


def simple_path() -> bool:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory).resolve()
        return resolve_workspace_path(root, "note.md") == root / "note.md"


check("simple_relative_path", 2, simple_path)


def rejects_absolute() -> bool:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory) / "root"
        root.mkdir()
        return rejects(root, Path(directory).resolve() / "outside.txt")


check("reject_absolute", 8, rejects_absolute)


def rejects_traversal() -> bool:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory) / "root"
        root.mkdir()
        return rejects(root, "../outside.txt") and rejects(root, "notes/../../outside.txt")


check("reject_dotdot", 10, rejects_traversal)


def rejects_symlink_escape() -> bool:
    if not hasattr(os, "symlink"):
        return True
    with tempfile.TemporaryDirectory() as directory:
        base = Path(directory)
        root = base / "root"
        outside = base / "outside"
        root.mkdir()
        outside.mkdir()
        try:
            (root / "escape").symlink_to(outside, target_is_directory=True)
        except OSError:
            return True
        return rejects(root, "escape/stolen.txt")


check("reject_symlink_escape", 15, rejects_symlink_escape)


def allows_nonexistent_nested() -> bool:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory).resolve()
        expected = root / "new" / "nested" / "note.md"
        return resolve_workspace_path(root, "new/nested/note.md") == expected


check("allow_nonexistent_nested", 7, allows_nonexistent_nested)


def writes_utf8() -> bool:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        target = atomic_write_text(root, "nested/note.md", "caffè ☕")
        return target == root.resolve() / "nested/note.md" and target.read_text(encoding="utf-8") == "caffè ☕"


check("atomic_write_creates", 10, writes_utf8)


def overwrites() -> bool:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        atomic_write_text(root, "note.md", "old")
        atomic_write_text(root, "note.md", "new")
        return (root / "note.md").read_text(encoding="utf-8") == "new"


check("atomic_write_overwrites", 5, overwrites)


def no_temp_leftovers() -> bool:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        atomic_write_text(root, "notes/note.md", "content")
        files = [path for path in root.rglob("*") if path.is_file()]
        source = inspect.getsource(atomic_write_text).casefold()
        uses_atomic_replace = "os.replace" in source or ".replace(" in source
        return files == [root / "notes" / "note.md"] and uses_atomic_replace


check("atomic_replace_no_leftovers", 5, no_temp_leftovers)


def redacts() -> bool:
    marker_a = "alpha" + "-private"
    marker_b = "beta" + "-private"
    marker_c = "gamma" + "-private"
    source = f"connect API_KEY={marker_a}, token: {marker_b}; PASSWORD = {marker_c} done"
    output = redact_message(source)
    return all(marker not in output for marker in (marker_a, marker_b, marker_c)) and "connect" in output and "done" in output


check("redact_supported_secrets", 15, redacts)
check("preserve_regular_message", 5, lambda: redact_message("saved note 42") == "saved note 42")


def candidate_tests() -> bool:
    result = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
        cwd=workspace,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        capture_output=True,
        text=True,
        timeout=30,
    )
    test_text = "\n".join(path.read_text(encoding="utf-8", errors="ignore") for path in (workspace / "tests").glob("*.py"))
    return result.returncode == 0 and "travers" in test_text.casefold() and "redact" in test_text.casefold()


check("candidate_security_tests", 5, candidate_tests)
security = (workspace / "SECURITY_MODEL.md").read_text(encoding="utf-8", errors="ignore") if (workspace / "SECURITY_MODEL.md").exists() else ""
security_lower = security.casefold()
check(
    "security_model_updated",
    10,
    lambda: all(term in security_lower for term in ("symlink", "atomic", "redact")) and "not implemented yet" not in security_lower,
)

score = round(sum(item["earned"] for item in checks), 2)
print(json.dumps({"score": score, "max_score": 100, "checks": checks}, ensure_ascii=False))
