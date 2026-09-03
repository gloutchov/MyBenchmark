"""Build a privacy-bounded dataset for the offline results dashboard."""

from __future__ import annotations

import hashlib
import json
import math
import os
import tempfile
from collections import defaultdict
from pathlib import Path, PureWindowsPath
from typing import Any, Iterable


DASHBOARD_SCHEMA_VERSION = 1
SUPPORTED_RUN_SCHEMA_VERSIONS = {2, 3}
SUPPORTED_REPORT_SCHEMA_VERSIONS = {2, 3}
MAX_SOURCE_BYTES = 32 * 1024 * 1024
PROFILE_PIPELINE = ("smoke", "standard", "full", "showcase")


class DashboardDataError(ValueError):
    """Raised when dashboard sources or output violate the export contract."""


def _inside(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


def _load_object(path: Path) -> tuple[dict[str, Any], str]:
    try:
        if path.is_symlink():
            raise DashboardDataError(f"La sorgente dashboard non può essere un symlink: {path}")
        size = path.stat().st_size
        if size > MAX_SOURCE_BYTES:
            raise DashboardDataError(
                f"Sorgente dashboard troppo grande: {path.name} (massimo {MAX_SOURCE_BYTES} byte)"
            )
        raw = path.read_bytes()
        payload = json.loads(raw.decode("utf-8"))
    except DashboardDataError:
        raise
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DashboardDataError(f"Impossibile leggere {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise DashboardDataError(f"La radice di {path} deve essere un oggetto JSON")
    return payload, hashlib.sha256(raw).hexdigest()


def _text(value: Any, *, default: str = "", maximum: int = 256) -> str:
    if not isinstance(value, str):
        return default
    cleaned = value.strip()
    if not cleaned or len(cleaned) > maximum or any(ord(character) < 32 for character in cleaned):
        return default
    if cleaned.startswith("/") or PureWindowsPath(cleaned).is_absolute():
        return default
    return cleaned


def _number(value: Any, *, minimum: float | None = None) -> float | int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    numeric = float(value)
    if not math.isfinite(numeric) or (minimum is not None and numeric < minimum):
        return None
    return int(value) if isinstance(value, int) else round(numeric, 6)


def _boolean(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None


def _integer(value: Any, *, minimum: int = 0) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        return None
    return value


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return list(dict.fromkeys(label for item in value if (label := _text(item))))


def _sanitize_case_scores(value: Any) -> dict[str, float | int]:
    if not isinstance(value, dict):
        return {}
    output: dict[str, float | int] = {}
    for raw_case, raw_score in sorted(value.items(), key=lambda item: str(item[0])):
        case_id = _text(raw_case, maximum=64)
        score = _number(raw_score, minimum=0)
        if case_id and score is not None:
            output[case_id] = score
    return output


def _sanitize_leaderboard(rows: Any) -> list[dict[str, Any]]:
    if not isinstance(rows, list):
        return []
    output: list[dict[str, Any]] = []
    for raw in rows:
        if not isinstance(raw, dict):
            continue
        model = _text(raw.get("model"))
        if not model:
            continue
        row = {
            "rank": len(output) + 1,
            "model": model,
            "overall_score": _number(raw.get("overall_score"), minimum=0),
            "quality_score": _number(raw.get("quality_score"), minimum=0),
            "completion_rate": _number(raw.get("completion_rate"), minimum=0),
            "speed_score": _number(raw.get("speed_score"), minimum=0),
            "token_efficiency_score": _number(raw.get("token_efficiency_score"), minimum=0),
            "median_duration_seconds": _number(raw.get("median_duration_seconds"), minimum=0),
            "median_output_tokens": _number(raw.get("median_output_tokens"), minimum=0),
            "median_cpu_seconds": _number(raw.get("median_cpu_seconds"), minimum=0),
            "median_energy_joules": _number(raw.get("median_energy_joules"), minimum=0),
            "score_stddev": _number(raw.get("score_stddev"), minimum=0),
            "successful_tasks": _integer(raw.get("successful_tasks")),
            "total_tasks": _integer(raw.get("total_tasks")),
            "case_scores": _sanitize_case_scores(raw.get("case_scores")),
        }
        output.append(row)
    return output


def _task_state(status: str, score: float | int | None, valid_for_ranking: bool | None) -> str:
    if valid_for_ranking is False:
        return "integrity_excluded"
    if status == "timeout":
        return "timeout"
    if status != "ok":
        return "error"
    if score is None:
        return "missing_score"
    return "passed" if float(score) >= 60 else "below_threshold"


def _sanitize_tasks(rows: Any) -> list[dict[str, Any]]:
    if not isinstance(rows, list):
        return []
    output: list[dict[str, Any]] = []
    for raw in rows:
        if not isinstance(raw, dict):
            continue
        model = _text(raw.get("model"))
        case_id = _text(raw.get("case_id"), maximum=64)
        if not model or not case_id:
            continue
        grade = raw.get("grade") if isinstance(raw.get("grade"), dict) else {}
        metrics = raw.get("metrics") if isinstance(raw.get("metrics"), dict) else {}
        usage = metrics.get("usage") if isinstance(metrics.get("usage"), dict) else {}
        system = raw.get("system_metrics") if isinstance(raw.get("system_metrics"), dict) else {}
        process = system.get("process") if isinstance(system.get("process"), dict) else {}
        energy = system.get("energy") if isinstance(system.get("energy"), dict) else {}
        integrity = raw.get("integrity") if isinstance(raw.get("integrity"), dict) else {}
        status = _text(raw.get("status"), default="unknown", maximum=32)
        score = _number(grade.get("score"), minimum=0)
        valid_for_ranking = _boolean(integrity.get("valid_for_ranking"))
        task = {
            "model": model,
            "case_id": case_id,
            "case_title": _text(raw.get("case_title"), default=case_id, maximum=200),
            "case_title_en": _text(raw.get("case_title_en"), default=case_id, maximum=200),
            "category": _text(raw.get("case_category"), default="unknown", maximum=64),
            "repetition": _integer(raw.get("repetition"), minimum=1) or 1,
            "status": status,
            "state": _task_state(status, score, valid_for_ranking),
            "score": score,
            "max_score": _number(grade.get("max_score"), minimum=0),
            "duration_seconds": _number(raw.get("duration_seconds"), minimum=0),
            "output_tokens": _integer(usage.get("output")),
            "tool_calls": _integer(metrics.get("tool_calls")),
            "tool_errors": _integer(metrics.get("tool_errors")),
            "cpu_seconds": None,
            "energy_joules": None,
            "integrity_valid": valid_for_ranking,
        }
        if process.get("available") is True:
            user_seconds = _number(process.get("user_seconds"), minimum=0)
            system_seconds = _number(process.get("system_seconds"), minimum=0)
            if user_seconds is not None and system_seconds is not None:
                task["cpu_seconds"] = round(float(user_seconds) + float(system_seconds), 6)
        if energy.get("available") is True:
            task["energy_joules"] = _number(energy.get("energy_joules"), minimum=0)
        output.append(task)
    return output


def _profile_order(profiles: Iterable[str]) -> list[str]:
    available = set(profiles)
    ordered = [profile for profile in PROFILE_PIPELINE if profile in available]
    ordered.extend(sorted(available - set(PROFILE_PIPELINE)))
    return ordered


def _build_funnel(runs: list[dict[str, Any]], profile_order: list[str]) -> list[dict[str, Any]]:
    run_ids: dict[str, list[str]] = defaultdict(list)
    participants: dict[str, set[str]] = defaultdict(set)
    for run in runs:
        profile = run["profile"]
        run_ids[profile].append(run["id"])
        participants[profile].update(run["participants"])
    funnel: list[dict[str, Any]] = []
    for index, profile in enumerate(profile_order):
        current = participants[profile]
        previous = participants[profile_order[index - 1]] if index else set()
        next_profile = profile_order[index + 1] if index + 1 < len(profile_order) else None
        following = participants[next_profile] if next_profile else set()
        funnel.append(
            {
                "profile": profile,
                "run_ids": sorted(run_ids[profile]),
                "participants": sorted(current),
                "new_participants": sorted(current - previous) if index else sorted(current),
                "next_profile": next_profile,
                "continued_to_next": sorted(current & following) if next_profile else [],
                "not_run_in_next": sorted(current - following) if next_profile else [],
            }
        )
    return funnel


def build_dashboard_data(run_dirs: Iterable[Path]) -> dict[str, Any]:
    """Load report artifacts and return a strictly whitelisted dashboard dataset."""
    resolved_dirs = [Path(path).resolve() for path in run_dirs]
    if not resolved_dirs:
        raise DashboardDataError("Indicare almeno una directory di run")
    if len(set(resolved_dirs)) != len(resolved_dirs):
        raise DashboardDataError("Le directory di run devono essere distinte")

    runs: list[dict[str, Any]] = []
    run_ids: set[str] = set()
    for run_dir in resolved_dirs:
        if not run_dir.is_dir():
            raise DashboardDataError(f"Directory di run mancante: {run_dir}")
        manifest, run_sha256 = _load_object(run_dir / "run.json")
        report, report_sha256 = _load_object(run_dir / "report.json")
        run_schema = manifest.get("schema_version")
        report_schema = report.get("schema_version")
        if isinstance(run_schema, bool) or run_schema not in SUPPORTED_RUN_SCHEMA_VERSIONS:
            raise DashboardDataError(f"Schema run non supportato in {run_dir.name}: {run_schema!r}")
        if isinstance(report_schema, bool) or report_schema not in SUPPORTED_REPORT_SCHEMA_VERSIONS:
            raise DashboardDataError(f"Schema report non supportato in {run_dir.name}: {report_schema!r}")
        report_run = report.get("run") if isinstance(report.get("run"), dict) else {}
        manifest_profile = _text(manifest.get("profile"), maximum=64)
        report_profile = _text(report_run.get("profile"), maximum=64)
        if manifest_profile and report_profile and manifest_profile != report_profile:
            raise DashboardDataError(f"Profilo incoerente fra run e report: {run_dir.name}")
        profile = report_profile or manifest_profile
        if not profile:
            raise DashboardDataError(f"Profilo mancante nel run: {run_dir.name}")
        run_id = _text(run_dir.name, maximum=120)
        if not run_id or run_id in run_ids:
            raise DashboardDataError(f"ID run non valido o duplicato: {run_dir.name!r}")
        run_ids.add(run_id)

        leaderboard = _sanitize_leaderboard(report.get("leaderboard"))
        tasks = _sanitize_tasks(report.get("results"))
        report_integrity = report.get("integrity") if isinstance(report.get("integrity"), dict) else {}
        disqualified = _string_list(report_integrity.get("disqualified_models"))
        participants = set(_string_list(manifest.get("models")))
        participants.update(row["model"] for row in leaderboard)
        participants.update(task["model"] for task in tasks)
        participants.update(disqualified)
        repository = manifest.get("repository") if isinstance(manifest.get("repository"), dict) else {}
        sandbox = report_run.get("sandbox") if isinstance(report_run.get("sandbox"), dict) else {}
        if not sandbox:
            sandbox = manifest.get("sandbox") if isinstance(manifest.get("sandbox"), dict) else {}
        runs.append(
            {
                "id": run_id,
                "profile": profile,
                "benchmark_version": _text(manifest.get("benchmark_version"), default="unknown", maximum=32),
                "started_at": _text(manifest.get("started_at"), maximum=64) or None,
                "finished_at": _text(manifest.get("finished_at"), maximum=64) or None,
                "provenance": {
                    "run_schema_version": run_schema,
                    "report_schema_version": report_schema,
                    "run_sha256": run_sha256,
                    "report_sha256": report_sha256,
                    "repository_commit": _text(repository.get("commit"), maximum=128) or None,
                },
                "sandbox": {
                    "backend": _text(sandbox.get("backend"), default="unknown", maximum=64),
                    "enforced": bool(sandbox.get("enforced") is True),
                    "filesystem_isolation": bool(sandbox.get("filesystem_isolation") is True),
                    "process_isolation": bool(sandbox.get("process_isolation") is True),
                    "network_isolation": bool(sandbox.get("network_isolation") is True),
                },
                "integrity": {
                    "status": _text(report_integrity.get("status"), default="not_recorded", maximum=64),
                    "disqualified_models": disqualified,
                },
                "participants": sorted(participants),
                "leaderboard": leaderboard,
                "tasks": tasks,
            }
        )

    order = _profile_order(run["profile"] for run in runs)
    profile_index = {profile: index for index, profile in enumerate(order)}
    runs.sort(key=lambda run: (profile_index[run["profile"]], run["id"]))
    dataset = {
        "schema_version": DASHBOARD_SCHEMA_VERSION,
        "profile_order": order,
        "runs": runs,
        "funnel": _build_funnel(runs, order),
    }
    validate_dashboard_data(dataset)
    return dataset


def validate_dashboard_data(dataset: Any) -> None:
    """Validate the public dashboard dataset shape without external packages."""
    if (
        not isinstance(dataset, dict)
        or isinstance(dataset.get("schema_version"), bool)
        or dataset.get("schema_version") != DASHBOARD_SCHEMA_VERSION
    ):
        raise DashboardDataError("Dataset dashboard non valido o schema non supportato")
    if set(dataset) != {"schema_version", "profile_order", "runs", "funnel"}:
        raise DashboardDataError("Campi radice del dataset dashboard non validi")
    profiles = dataset.get("profile_order")
    runs = dataset.get("runs")
    funnel = dataset.get("funnel")
    if not isinstance(profiles, list) or not profiles or not all(_text(item, maximum=64) for item in profiles):
        raise DashboardDataError("profile_order deve contenere profili validi")
    if len(profiles) != len(set(profiles)):
        raise DashboardDataError("profile_order contiene duplicati")
    if not isinstance(runs, list) or not runs:
        raise DashboardDataError("runs deve contenere almeno un run")
    ids: set[str] = set()
    for run in runs:
        if not isinstance(run, dict) or not _text(run.get("id"), maximum=120):
            raise DashboardDataError("Run dashboard non valido")
        if run["id"] in ids:
            raise DashboardDataError(f"ID run duplicato: {run['id']}")
        ids.add(run["id"])
        if run.get("profile") not in profiles:
            raise DashboardDataError(f"Profilo run non dichiarato: {run.get('profile')!r}")
        for key in ("participants", "leaderboard", "tasks"):
            if not isinstance(run.get(key), list):
                raise DashboardDataError(f"{key} deve essere una lista nel run {run['id']}")
    if not isinstance(funnel, list) or [item.get("profile") for item in funnel if isinstance(item, dict)] != profiles:
        raise DashboardDataError("Funnel non coerente con profile_order")


def write_dashboard_data(
    run_dirs: Iterable[Path],
    output_path: Path,
    *,
    workspace_root: Path | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Write a validated dataset atomically without modifying source run directories."""
    resolved_dirs = [Path(path).resolve() for path in run_dirs]
    output = Path(output_path).resolve()
    if workspace_root is not None:
        root = workspace_root.resolve()
        if not _inside(output, root) or any(not _inside(run_dir, root) for run_dir in resolved_dirs):
            raise DashboardDataError("Input e output dashboard devono restare nella root del progetto")
    if any(_inside(output, run_dir) for run_dir in resolved_dirs):
        raise DashboardDataError("L'output dashboard non può modificare una directory sorgente")
    if output.exists() and not overwrite:
        raise DashboardDataError(f"Output già esistente: {output}; usare --force per sostituirlo")
    dataset = build_dashboard_data(resolved_dirs)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary_name = ""
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=output.parent,
            prefix=f".{output.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_name = handle.name
            json.dump(dataset, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, output)
    finally:
        if temporary_name:
            Path(temporary_name).unlink(missing_ok=True)
    return dataset
