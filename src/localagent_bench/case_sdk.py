"""Case manifests, discovery, validation, and authoring templates."""

from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Iterable


CASE_MANIFEST_NAME = "case.json"
CASE_SCHEMA_VERSION = 1
COMPLETION_THRESHOLD = 60
MAX_CASE_MANIFEST_BYTES = 64 * 1024


class CaseValidationError(ValueError):
    """Raised when a case manifest or grader contract is invalid."""


@dataclass(frozen=True)
class CaseSpec:
    id: str
    title: str
    category: str
    weight: float
    directory: Path
    prompt_path: Path
    fixture_path: Path
    grader_path: Path
    title_en: str = ""
    manifest_path: Path | None = None
    manual_rubric_path: Path | None = None
    manual_rubric_max_score: float | None = None


def safe_case_id(value: str) -> bool:
    """Return whether ``value`` is portable and safe as a case directory name."""
    return bool(value) and len(value) <= 64 and all(ch.isascii() and (ch.isalnum() or ch in "-_") for ch in value)


def _inside(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


def resolve_cases_directory(repository_root: Path, declared: str) -> Path:
    """Resolve the configured cases root without permitting workspace escape."""
    if not isinstance(declared, str) or not declared.strip():
        raise CaseValidationError("cases.directory deve essere una stringa relativa non vuota")
    if "\\" in declared:
        raise CaseValidationError("cases.directory deve usare separatori POSIX ('/')")
    posix = PurePosixPath(declared)
    windows = PureWindowsPath(declared)
    if posix.is_absolute() or windows.is_absolute() or windows.drive or ".." in posix.parts:
        raise CaseValidationError("cases.directory deve restare dentro il repository")
    root = repository_root.resolve()
    resolved = (root / Path(*posix.parts)).resolve(strict=False)
    if resolved == root or not _inside(resolved, root):
        raise CaseValidationError("cases.directory deve indicare una sottodirectory del repository")
    if not resolved.is_dir():
        raise CaseValidationError(f"Directory dei casi mancante: {resolved}")
    return resolved


def _required_string(mapping: dict[str, Any], key: str, context: str, *, max_length: int = 200) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        raise CaseValidationError(f"{context}.{key} deve essere una stringa non vuota")
    value = value.strip()
    if any(ord(character) < 32 for character in value):
        raise CaseValidationError(f"{context}.{key} non può contenere caratteri di controllo")
    if len(value) > max_length:
        raise CaseValidationError(f"{context}.{key} supera {max_length} caratteri")
    return value


def _reject_unknown(mapping: dict[str, Any], allowed: set[str], context: str) -> None:
    unknown = sorted(set(mapping) - allowed)
    if unknown:
        raise CaseValidationError(f"Campi sconosciuti in {context}: {', '.join(unknown)}")


def _resolve_declared_path(case_directory: Path, value: Any, label: str, expected: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise CaseValidationError(f"paths.{label} deve essere una stringa relativa non vuota")
    if "\\" in value:
        raise CaseValidationError(f"paths.{label} deve usare separatori POSIX ('/')")
    posix = PurePosixPath(value)
    windows = PureWindowsPath(value)
    if posix.is_absolute() or windows.is_absolute() or windows.drive or ".." in posix.parts:
        raise CaseValidationError(f"paths.{label} deve restare dentro la directory del caso")
    candidate = case_directory / Path(*posix.parts)
    resolved = candidate.resolve(strict=False)
    if resolved != candidate.absolute():
        raise CaseValidationError(f"paths.{label} non può attraversare symlink")
    if resolved == case_directory or not _inside(resolved, case_directory):
        raise CaseValidationError(f"paths.{label} esce dalla directory del caso")
    if expected == "file" and not resolved.is_file():
        raise CaseValidationError(f"File del caso mancante per paths.{label}: {resolved}")
    if expected == "directory" and not resolved.is_dir():
        raise CaseValidationError(f"Directory del caso mancante per paths.{label}: {resolved}")
    return resolved


def _validate_fixture_links(fixture_path: Path) -> None:
    try:
        entries = fixture_path.rglob("*")
        for entry in entries:
            if entry.is_symlink() and not _inside(entry.resolve(strict=False), fixture_path):
                raise CaseValidationError(f"Symlink della fixture fuori scope: {entry}")
    except (OSError, RuntimeError) as exc:
        raise CaseValidationError(f"Impossibile validare i symlink della fixture {fixture_path}: {exc}") from exc


def load_case_manifest(case_directory: Path) -> CaseSpec:
    """Load and structurally validate one ``case.json`` manifest."""
    case_directory = case_directory.resolve()
    manifest_path = case_directory / CASE_MANIFEST_NAME
    if manifest_path.is_symlink():
        raise CaseValidationError(f"Il manifesto non può essere un symlink: {manifest_path}")
    try:
        if manifest_path.stat().st_size > MAX_CASE_MANIFEST_BYTES:
            raise CaseValidationError(
                f"Manifesto troppo grande: {manifest_path} (massimo {MAX_CASE_MANIFEST_BYTES} byte)"
            )
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CaseValidationError(f"Impossibile leggere {manifest_path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise CaseValidationError(f"La radice di {manifest_path} deve essere un oggetto")
    _reject_unknown(
        raw,
        {"$schema", "schema_version", "id", "title", "category", "weight", "paths", "manual_rubric"},
        str(manifest_path),
    )
    schema_reference = raw.get("$schema")
    if schema_reference is not None and (not isinstance(schema_reference, str) or not schema_reference.strip()):
        raise CaseValidationError("manifest.$schema deve essere una stringa non vuota")
    if raw.get("schema_version") != CASE_SCHEMA_VERSION:
        raise CaseValidationError(
            f"Versione manifesto non supportata in {manifest_path} (attesa: {CASE_SCHEMA_VERSION})"
        )
    case_id = _required_string(raw, "id", "manifest", max_length=64)
    if not safe_case_id(case_id):
        raise CaseValidationError(f"ID caso non valido: {case_id!r}")
    if case_directory.name != case_id:
        raise CaseValidationError(
            f"L'ID {case_id!r} non coincide con la directory {case_directory.name!r}"
        )

    title = raw.get("title")
    if not isinstance(title, dict):
        raise CaseValidationError("manifest.title deve essere un oggetto bilingue")
    _reject_unknown(title, {"it", "en"}, "manifest.title")
    title_it = _required_string(title, "it", "manifest.title")
    title_en = _required_string(title, "en", "manifest.title")
    category = _required_string(raw, "category", "manifest", max_length=64)

    weight = raw.get("weight")
    if isinstance(weight, bool) or not isinstance(weight, (int, float)) or not math.isfinite(float(weight)):
        raise CaseValidationError("manifest.weight deve essere un numero finito positivo")
    weight = float(weight)
    if weight <= 0 or weight > 100:
        raise CaseValidationError("manifest.weight deve essere > 0 e <= 100")

    paths = raw.get("paths")
    if not isinstance(paths, dict):
        raise CaseValidationError("manifest.paths deve essere un oggetto")
    _reject_unknown(paths, {"prompt", "fixture", "grader"}, "manifest.paths")
    prompt_path = _resolve_declared_path(case_directory, paths.get("prompt"), "prompt", "file")
    fixture_path = _resolve_declared_path(case_directory, paths.get("fixture"), "fixture", "directory")
    grader_path = _resolve_declared_path(case_directory, paths.get("grader"), "grader", "file")
    if (
        prompt_path in {grader_path, manifest_path}
        or grader_path == manifest_path
        or fixture_path in prompt_path.parents
        or fixture_path in grader_path.parents
        or fixture_path in manifest_path.parents
    ):
        raise CaseValidationError("Prompt, fixture e grader devono indicare percorsi distinti e non sovrapposti")
    _validate_fixture_links(fixture_path)

    rubric_path: Path | None = None
    rubric_max_score: float | None = None
    rubric = raw.get("manual_rubric")
    if rubric is not None:
        if not isinstance(rubric, dict):
            raise CaseValidationError("manifest.manual_rubric deve essere un oggetto")
        _reject_unknown(rubric, {"path", "max_score"}, "manifest.manual_rubric")
        rubric_path = _resolve_declared_path(
            case_directory,
            rubric.get("path"),
            "manual_rubric",
            "file",
        )
        if rubric_path in {prompt_path, grader_path, manifest_path} or fixture_path in rubric_path.parents:
            raise CaseValidationError("La rubrica manuale deve essere separata da prompt, fixture e grader")
        max_score = rubric.get("max_score")
        if isinstance(max_score, bool) or not isinstance(max_score, (int, float)):
            raise CaseValidationError("manual_rubric.max_score deve essere un numero positivo")
        rubric_max_score = float(max_score)
        if not math.isfinite(rubric_max_score) or rubric_max_score <= 0 or rubric_max_score > 100:
            raise CaseValidationError("manual_rubric.max_score deve essere > 0 e <= 100")

    return CaseSpec(
        id=case_id,
        title=title_it,
        title_en=title_en,
        category=category,
        weight=weight,
        directory=case_directory,
        prompt_path=prompt_path,
        fixture_path=fixture_path,
        grader_path=grader_path,
        manifest_path=manifest_path,
        manual_rubric_path=rubric_path,
        manual_rubric_max_score=rubric_max_score,
    )


def discover_case_manifests(cases_directory: Path) -> dict[str, CaseSpec]:
    """Discover direct child case directories and reject incomplete imports."""
    cases_directory = cases_directory.resolve()
    cases: dict[str, CaseSpec] = {}
    for directory in sorted(cases_directory.iterdir(), key=lambda item: item.name):
        if not directory.is_dir() or directory.name.startswith(".") or directory.name == "__pycache__":
            continue
        resolved = directory.resolve()
        if resolved.parent != cases_directory:
            raise CaseValidationError(f"Directory caso fuori scope o symlink non ammesso: {directory}")
        manifest = resolved / CASE_MANIFEST_NAME
        if not manifest.is_file():
            raise CaseValidationError(f"Manifesto mancante: {manifest}")
        case = load_case_manifest(resolved)
        if case.id in cases:
            raise CaseValidationError(f"ID caso duplicato: {case.id}")
        cases[case.id] = case
    if not cases:
        raise CaseValidationError(f"Nessun caso trovato in {cases_directory}")
    return cases


def validate_case_runtime(case: CaseSpec, timeout_seconds: int = 30) -> dict[str, Any]:
    """Validate a grader's JSON protocol and baseline calibration."""
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        completed = subprocess.run(
            [sys.executable, str(case.grader_path), str(case.fixture_path)],
            cwd=case.directory,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise CaseValidationError(f"Grader {case.id} in timeout dopo {timeout_seconds}s") from exc
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "nessun dettaglio"
        raise CaseValidationError(f"Grader {case.id} terminato con exit {completed.returncode}: {detail}")
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise CaseValidationError(f"Grader {case.id}: output JSON non valido") from exc
    if not isinstance(payload, dict):
        raise CaseValidationError(f"Grader {case.id}: l'output deve essere un oggetto")
    score = payload.get("score")
    max_score = payload.get("max_score")
    checks = payload.get("checks")
    if isinstance(score, bool) or not isinstance(score, (int, float)) or not math.isfinite(float(score)):
        raise CaseValidationError(f"Grader {case.id}: score non valido")
    if max_score != 100:
        raise CaseValidationError(f"Grader {case.id}: max_score deve essere 100")
    if not isinstance(checks, list) or not checks:
        raise CaseValidationError(f"Grader {case.id}: checks deve essere una lista non vuota")
    points_total = 0.0
    earned_total = 0.0
    check_ids: set[str] = set()
    for index, check in enumerate(checks):
        if not isinstance(check, dict):
            raise CaseValidationError(f"Grader {case.id}: check {index + 1} non valido")
        check_id = check.get("id")
        if not isinstance(check_id, str) or not check_id.strip() or check_id in check_ids:
            raise CaseValidationError(f"Grader {case.id}: id mancante o duplicato nel check {index + 1}")
        check_ids.add(check_id)
        points = check.get("points")
        earned = check.get("earned")
        if (
            isinstance(points, bool)
            or not isinstance(points, (int, float))
            or not math.isfinite(float(points))
            or float(points) < 0
        ):
            raise CaseValidationError(f"Grader {case.id}: points non validi nel check {index + 1}")
        if (
            isinstance(earned, bool)
            or not isinstance(earned, (int, float))
            or not math.isfinite(float(earned))
            or float(earned) < 0
            or float(earned) > float(points)
        ):
            raise CaseValidationError(f"Grader {case.id}: earned non valido nel check {index + 1}")
        points_total += float(points)
        earned_total += float(earned)
    if not math.isclose(points_total, 100.0, abs_tol=1e-6):
        raise CaseValidationError(f"Grader {case.id}: la somma dei points deve essere 100")
    if not math.isclose(float(score), earned_total, abs_tol=0.01):
        raise CaseValidationError(f"Grader {case.id}: score e somma earned non coincidono")
    if float(score) >= COMPLETION_THRESHOLD:
        raise CaseValidationError(
            f"Grader {case.id}: la fixture iniziale ottiene {float(score):g}/100, atteso < {COMPLETION_THRESHOLD}"
        )
    return {
        "id": case.id,
        "weight": case.weight,
        "baseline_score": float(score),
        "max_score": 100,
        "checks": len(checks),
        "manual_rubric": case.manual_rubric_path is not None,
    }


def validate_case_selection(cases: Iterable[CaseSpec]) -> list[dict[str, Any]]:
    return [validate_case_runtime(case) for case in cases]


_GRADER_TEMPLATE = '''#!/usr/bin/env python3
"""Replace this scaffold with observable checks worth exactly 100 points."""

from __future__ import annotations

import json
import sys
from pathlib import Path


workspace = Path(sys.argv[1]).resolve()
implemented = (workspace / "IMPLEMENTATION.md").is_file()
checks = [
    {
        "id": "implementation_marker",
        "points": 100,
        "earned": 100 if implemented else 0,
        "detail": "IMPLEMENTATION.md presente" if implemented else "IMPLEMENTATION.md mancante",
    }
]
score = sum(item["earned"] for item in checks)
print(json.dumps({"score": score, "max_score": 100, "checks": checks}, ensure_ascii=False))
'''


def create_case_template(
    cases_directory: Path,
    case_id: str,
    *,
    title_it: str,
    title_en: str,
    category: str,
    weight: float,
    include_manual_rubric: bool = False,
) -> CaseSpec:
    """Atomically create a dependency-free case scaffold and validate it."""
    if not safe_case_id(case_id):
        raise CaseValidationError("L'ID deve usare solo lettere ASCII, numeri, '-' o '_' (massimo 64)")
    title_it = title_it.strip()
    title_en = title_en.strip()
    category = category.strip()
    if not title_it or not title_en or not category:
        raise CaseValidationError("Titoli italiano/inglese e categoria non possono essere vuoti")
    if len(title_it) > 200 or len(title_en) > 200 or len(category) > 64:
        raise CaseValidationError("I titoli devono avere massimo 200 caratteri e la categoria massimo 64")
    if any(ord(character) < 32 for value in (title_it, title_en, category) for character in value):
        raise CaseValidationError("Titoli e categoria non possono contenere caratteri di controllo")
    if isinstance(weight, bool) or not isinstance(weight, (int, float)) or not math.isfinite(float(weight)):
        raise CaseValidationError("Il peso deve essere un numero finito positivo")
    if float(weight) <= 0 or float(weight) > 100:
        raise CaseValidationError("Il peso deve essere > 0 e <= 100")
    cases_directory = cases_directory.resolve()
    target = cases_directory / case_id
    if target.exists() or target.is_symlink():
        raise CaseValidationError(f"Il caso esiste già: {target}")

    staging = Path(tempfile.mkdtemp(prefix=f".{case_id}-", dir=cases_directory))
    try:
        (staging / "fixture").mkdir()
        manifest: dict[str, Any] = {
            "$schema": "../../schemas/case.schema.json",
            "schema_version": CASE_SCHEMA_VERSION,
            "id": case_id,
            "title": {"it": title_it, "en": title_en},
            "category": category,
            "weight": float(weight),
            "paths": {"prompt": "prompt.md", "fixture": "fixture", "grader": "grader.py"},
        }
        if include_manual_rubric:
            manifest["manual_rubric"] = {"path": "manual-rubric.md", "max_score": 100}
        (staging / CASE_MANIFEST_NAME).write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        (staging / "prompt.md").write_text(
            f"# {title_it} / {title_en}\n\n"
            "Descrivi qui il comportamento verificabile richiesto al modello. / "
            "Describe the observable behavior required from the model here.\n",
            encoding="utf-8",
        )
        (staging / "fixture" / "README.md").write_text(
            f"# Fixture: {case_id}\n\n"
            "Baseline sintetica intenzionalmente incompleta. / "
            "Intentionally incomplete synthetic baseline.\n",
            encoding="utf-8",
        )
        grader_path = staging / "grader.py"
        grader_path.write_text(_GRADER_TEMPLATE, encoding="utf-8")
        grader_path.chmod(0o755)
        if include_manual_rubric:
            (staging / "manual-rubric.md").write_text(
                "# Rubrica manuale / Manual rubric\n\n"
                "Il punteggio manuale resta separato dai 100 punti automatici. / "
                "The manual score remains separate from the 100 automatic points.\n\n"
                "- Qualità e leggibilità / Quality and readability: 0–50\n"
                "- Chiarezza della spiegazione / Explanation clarity: 0–50\n",
                encoding="utf-8",
            )
        staging.replace(target)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    case = load_case_manifest(target)
    validate_case_runtime(case)
    return case
