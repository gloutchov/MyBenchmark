"""Input snapshots and repository-integrity checks for benchmark runs."""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
from pathlib import Path
from typing import Iterable

from .config import CaseSpec


class InputIntegrityError(RuntimeError):
    """Raised when benchmark inputs are not safe to snapshot."""


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )


def _entry_fingerprint(path: Path) -> str:
    if path.is_symlink():
        return f"symlink:{os.readlink(path)}"
    if path.is_file():
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
        return f"file:{digest.hexdigest()}"
    return "directory"


def fingerprint_tree(root: Path) -> str:
    """Return a deterministic digest for a file or directory tree."""
    root = root.resolve()
    digest = hashlib.sha256()
    if not root.exists():
        digest.update(b"missing")
        return digest.hexdigest()
    if root.is_file() or root.is_symlink():
        digest.update(_entry_fingerprint(root).encode("utf-8"))
        return digest.hexdigest()
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        relative = path.relative_to(root).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(_entry_fingerprint(path).encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()


def repository_fingerprints(root: Path, excluded_roots: Iterable[Path] = ()) -> dict[str, str]:
    """Fingerprint tracked and visible untracked repository files."""
    payload = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=root,
        capture_output=True,
        check=True,
        timeout=30,
    ).stdout
    paths = payload.decode("utf-8", errors="surrogateescape").split("\0")
    excluded = [path.resolve(strict=False) for path in excluded_roots]
    fingerprints: dict[str, str] = {}
    for relative in sorted(path for path in paths if path):
        candidate = root / relative
        resolved = candidate.resolve(strict=False)
        if any(resolved == excluded_root or excluded_root in resolved.parents for excluded_root in excluded):
            continue
        fingerprints[relative] = _entry_fingerprint(candidate) if candidate.exists() or candidate.is_symlink() else "missing"
    return fingerprints


def changed_paths(before: dict[str, str], after: dict[str, str]) -> list[str]:
    """Return sorted paths whose presence or content changed."""
    return sorted(path for path in set(before) | set(after) if before.get(path) != after.get(path))


def _copy_tracked_tree(repository_root: Path, source: Path, destination: Path) -> None:
    """Copy and verify only Git-tracked files below ``source``."""
    relative_source = source.relative_to(repository_root)
    payload = subprocess.run(
        ["git", "ls-files", "-z", "--", str(relative_source)],
        cwd=repository_root,
        capture_output=True,
        check=True,
        timeout=30,
    ).stdout
    tracked = payload.decode("utf-8", errors="surrogateescape").split("\0")
    destination.mkdir(parents=True, exist_ok=False)
    for repository_relative in (path for path in tracked if path):
        source_path = repository_root / repository_relative
        target_path = destination / source_path.relative_to(source)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        if source_path.is_symlink():
            target_path.symlink_to(os.readlink(source_path))
        else:
            shutil.copy2(source_path, target_path)
        if _entry_fingerprint(source_path) != _entry_fingerprint(target_path):
            raise InputIntegrityError(f"Copia snapshot non verificata: {repository_relative}")


def require_clean_inputs(root: Path, cases: Iterable[CaseSpec]) -> None:
    """Reject dirty AGENTS, prompts, graders, or fixture inputs."""
    try:
        repository_root = Path(_git(root, "rev-parse", "--show-toplevel").stdout.strip()).resolve()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise InputIntegrityError(f"Repository Git non disponibile: {exc}") from exc
    if repository_root != root.resolve():
        raise InputIntegrityError(f"La configurazione non punta alla root Git: {root}")
    pathspecs = ["AGENTS.md", ".gitignore", *(str(case.directory.relative_to(root)) for case in cases)]
    status = _git(root, "status", "--porcelain", "--untracked-files=all", "--", *pathspecs).stdout.strip()
    if status:
        raise InputIntegrityError(
            "Input benchmark modificati o non tracciati; ripristinali o committali prima del run:\n" + status
        )


def repository_metadata(root: Path) -> dict[str, object]:
    """Capture Git provenance without storing file contents."""
    status_lines = _git(root, "status", "--porcelain", "--untracked-files=all").stdout.splitlines()
    return {
        "commit": _git(root, "rev-parse", "HEAD").stdout.strip(),
        "branch": _git(root, "branch", "--show-current").stdout.strip(),
        "dirty": bool(status_lines),
        "dirty_paths": [line[3:] if len(line) > 3 else line for line in status_lines],
    }


def snapshot_cases(
    cases: Iterable[CaseSpec],
    destination: Path,
    agents_path: Path,
    gitignore_path: Path,
) -> tuple[list[CaseSpec], dict[str, object]]:
    """Create one frozen input copy shared by every attempt in a run."""
    destination.mkdir(parents=True, exist_ok=False)
    agents_snapshot = destination / "AGENTS.snapshot.md"
    gitignore_snapshot = destination / ".gitignore.snapshot"
    source_agents_hash = fingerprint_tree(agents_path)
    source_gitignore_hash = fingerprint_tree(gitignore_path)
    shutil.copy2(agents_path, agents_snapshot)
    shutil.copy2(gitignore_path, gitignore_snapshot)
    if fingerprint_tree(agents_snapshot) != source_agents_hash:
        raise InputIntegrityError("La copia congelata di AGENTS.md non coincide con la sorgente")
    if fingerprint_tree(gitignore_snapshot) != source_gitignore_hash:
        raise InputIntegrityError("La copia congelata di .gitignore non coincide con la sorgente")
    snapshot_specs: list[CaseSpec] = []
    case_manifest: dict[str, dict[str, str]] = {}
    cases_root = destination / "cases"
    cases_root.mkdir()
    repository_root = agents_path.parent
    for case in cases:
        case_root = cases_root / case.id
        fixture = case_root / "fixture"
        case_root.mkdir()
        shutil.copy2(case.prompt_path, case_root / "prompt.md")
        shutil.copy2(case.grader_path, case_root / "grader.py")
        if _entry_fingerprint(case.prompt_path) != _entry_fingerprint(case_root / "prompt.md"):
            raise InputIntegrityError(f"La copia del prompt {case.id} non coincide con la sorgente")
        if _entry_fingerprint(case.grader_path) != _entry_fingerprint(case_root / "grader.py"):
            raise InputIntegrityError(f"La copia del grader {case.id} non coincide con la sorgente")
        _copy_tracked_tree(repository_root, case.fixture_path, fixture)
        snapshot = CaseSpec(
            id=case.id,
            title=case.title,
            category=case.category,
            weight=case.weight,
            directory=case_root,
            prompt_path=case_root / "prompt.md",
            fixture_path=fixture,
            grader_path=case_root / "grader.py",
        )
        snapshot_specs.append(snapshot)
        case_manifest[case.id] = {
            "prompt_sha256": fingerprint_tree(snapshot.prompt_path),
            "fixture_sha256": fingerprint_tree(snapshot.fixture_path),
            "grader_sha256": fingerprint_tree(snapshot.grader_path),
            "input_sha256": fingerprint_tree(snapshot.directory),
        }
    return snapshot_specs, {
        "agents_sha256": source_agents_hash,
        "gitignore_sha256": source_gitignore_hash,
        "cases": case_manifest,
    }


def verify_snapshot(destination: Path, manifest: dict[str, object]) -> list[str]:
    """Return snapshot components that no longer match their initial hashes."""
    changed: list[str] = []
    agents = destination / "AGENTS.snapshot.md"
    if fingerprint_tree(agents) != manifest.get("agents_sha256"):
        changed.append("AGENTS.snapshot.md")
    gitignore = destination / ".gitignore.snapshot"
    if fingerprint_tree(gitignore) != manifest.get("gitignore_sha256"):
        changed.append(".gitignore.snapshot")
    case_manifest = manifest.get("cases", {})
    if not isinstance(case_manifest, dict):
        return ["input-manifest"]
    for case_id, expected in case_manifest.items():
        if not isinstance(expected, dict):
            changed.append(f"cases/{case_id}")
            continue
        case_root = destination / "cases" / case_id
        checks = {
            "prompt.md": fingerprint_tree(case_root / "prompt.md"),
            "fixture": fingerprint_tree(case_root / "fixture"),
            "grader.py": fingerprint_tree(case_root / "grader.py"),
            "input": fingerprint_tree(case_root),
        }
        expected_keys = {
            "prompt.md": "prompt_sha256",
            "fixture": "fixture_sha256",
            "grader.py": "grader_sha256",
            "input": "input_sha256",
        }
        for label, actual in checks.items():
            if actual != expected.get(expected_keys[label]):
                changed.append(f"cases/{case_id}/{label}")
    return sorted(set(changed))
