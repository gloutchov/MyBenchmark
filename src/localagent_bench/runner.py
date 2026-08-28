"""Benchmark orchestration and artifact capture."""

from __future__ import annotations

import hashlib
import json
import platform
import re
import shutil
import subprocess
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import BenchmarkConfig, CaseSpec
from .grading import grade_workspace
from .ollama import OllamaModel, list_models, unload, version, warmup
from .pi_adapter import run_pi, write_models_config
from .report import write_report


class BenchmarkError(RuntimeError):
    """Raised for failures that prevent a benchmark run from starting."""


def _slug(value: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9._-]+", "-", value).strip("-.")
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:8]
    return f"{safe[:60] or 'model'}-{digest}"


def _command_version(command: list[str]) -> str | None:
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    value = (result.stdout or result.stderr).strip().splitlines()
    return value[0] if value else None


def _git(workspace: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=workspace, capture_output=True, text=True, check=check, timeout=30
    )


def _prepare_workspace(config: BenchmarkConfig, case: CaseSpec, destination: Path) -> str:
    shutil.copytree(case.fixture_path, destination)
    shutil.copy2(config.root / ".gitignore", destination / ".gitignore")
    if config.root not in destination.parents:
        shutil.copy2(config.root / "AGENTS.md", destination / "AGENTS.md")
    try:
        _git(destination, "init", "-q", "-b", "main")
    except subprocess.CalledProcessError:
        _git(destination, "init", "-q")
        _git(destination, "branch", "-M", "main")
    _git(destination, "config", "user.name", "LocalAgent Benchmark")
    _git(destination, "config", "user.email", "benchmark@localhost")
    _git(destination, "add", ".")
    _git(destination, "commit", "-q", "-m", "benchmark baseline")
    return _git(destination, "rev-parse", "HEAD").stdout.strip()


def _capture_git(workspace: Path, baseline_commit: str) -> tuple[str, str, str]:
    status = _git(workspace, "status", "--short", "--branch", check=False).stdout
    _git(workspace, "add", "-N", ".", check=False)
    diff = _git(workspace, "diff", "--no-ext-diff", baseline_commit, "--", check=False).stdout
    branch = _git(workspace, "branch", "--show-current", check=False).stdout.strip()
    return status, diff, branch


def _resolve_models(config: BenchmarkConfig, requested: list[str] | None, installed: list[OllamaModel]) -> list[str]:
    installed_names = {model.name for model in installed}
    if requested:
        selected = requested
    elif config.models == "installed":
        selected = [model.name for model in installed]
    else:
        selected = list(config.models)
    missing = [model for model in selected if model not in installed_names]
    if missing:
        raise BenchmarkError(f"Modelli non installati in Ollama: {', '.join(missing)}")
    if not selected:
        raise BenchmarkError("Nessun modello Ollama selezionato")
    return list(dict.fromkeys(selected))


def _resolve_cases(config: BenchmarkConfig, profile: str, requested: list[str] | None) -> list[CaseSpec]:
    if requested:
        unknown = set(requested) - set(config.cases)
        if unknown:
            raise BenchmarkError(f"Casi sconosciuti: {', '.join(sorted(unknown))}")
        ids = requested
    else:
        try:
            ids = list(config.profiles[profile])
        except KeyError as exc:
            raise BenchmarkError(f"Profilo sconosciuto: {profile}") from exc
    return [config.cases[case_id] for case_id in dict.fromkeys(ids)]


def doctor(config: BenchmarkConfig) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    pi_path = shutil.which(config.pi_command[0])
    checks.append({"name": "pi", "ok": pi_path is not None, "detail": pi_path or "comando non trovato"})
    git_path = shutil.which("git")
    checks.append({"name": "git", "ok": git_path is not None, "detail": git_path or "comando non trovato"})
    try:
        models = list_models(config.ollama_url)
        ollama_version = version(config.ollama_url)
        checks.append(
            {
                "name": "ollama",
                "ok": True,
                "detail": f"{ollama_version or 'versione sconosciuta'}; {len(models)} modelli",
            }
        )
    except Exception as exc:  # a doctor must report all checks
        models = []
        checks.append({"name": "ollama", "ok": False, "detail": str(exc)})
    checks.append({"name": "config", "ok": True, "detail": f"{len(config.cases)} casi validi"})
    return {"ok": all(check["ok"] for check in checks), "checks": checks, "models": [asdict(model) for model in models]}


def run_benchmark(
    config: BenchmarkConfig,
    *,
    profile: str,
    requested_models: list[str] | None,
    requested_cases: list[str] | None,
    repetitions: int | None,
    timeout_seconds: int | None,
    use_warmup: bool | None,
    output_dir: Path | None,
) -> Path:
    installed = list_models(config.ollama_url)
    models = _resolve_models(config, requested_models, installed)
    cases = _resolve_cases(config, profile, requested_cases)
    repeat_count = repetitions or config.defaults.repetitions
    timeout = timeout_seconds or config.defaults.timeout_seconds
    if repeat_count < 1 or timeout < 10:
        raise BenchmarkError("Ripetizioni e timeout devono essere positivi")
    should_warmup = config.defaults.warmup if use_warmup is None else use_warmup

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = (output_dir or config.root / "results" / timestamp).resolve()
    if run_dir.exists() and any(run_dir.iterdir()):
        raise BenchmarkError(f"Directory output non vuota: {run_dir}")
    run_dir.mkdir(parents=True, exist_ok=True)
    agent_dir = run_dir / ".pi-agent"
    write_models_config(
        agent_dir,
        config.ollama_url,
        models,
        config.defaults.context_window,
        config.defaults.max_tokens,
        config.defaults.temperature,
    )
    installed_by_name = {item.name: item for item in installed}
    manifest = {
        "schema_version": 1,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "profile": profile,
        "models": models,
        "cases": [case.id for case in cases],
        "repetitions": repeat_count,
        "timeout_seconds": timeout,
        "thinking": config.defaults.thinking,
        "warmup": should_warmup,
        "warmup_metrics": {},
        "environment": {
            "platform": platform.platform(),
            "python": sys.version.split()[0],
            "pi": _command_version([*config.pi_command, "--version"]),
            "ollama": version(config.ollama_url),
        },
        "model_metadata": {name: asdict(installed_by_name[name]) for name in models},
    }
    (run_dir / "run.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    context_dir = run_dir / "benchmark-context"
    context_dir.mkdir(exist_ok=True)
    shutil.copy2(config.root / "AGENTS.md", context_dir / "AGENTS.snapshot.md")

    total = len(models) * len(cases) * repeat_count
    current = 0
    for model in models:
        if should_warmup:
            print(f"[warmup] {model}", flush=True)
            try:
                warmup_result = warmup(config.ollama_url, model, config.defaults.keep_alive, min(timeout, 300))
                manifest["warmup_metrics"][model] = {
                    key: warmup_result.get(key)
                    for key in ("total_duration", "load_duration", "prompt_eval_count", "eval_count", "eval_duration")
                    if key in warmup_result
                }
            except Exception as exc:
                print(f"[avviso] warmup fallito per {model}: {exc}", file=sys.stderr, flush=True)
            (run_dir / "run.json").write_text(
                json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
            )
        for case in cases:
            for repetition in range(1, repeat_count + 1):
                current += 1
                case_dir = run_dir / "models" / _slug(model) / "cases" / f"{case.id}-r{repetition}"
                workspace = case_dir / "workspace"
                case_dir.mkdir(parents=True, exist_ok=True)
                baseline_commit = _prepare_workspace(config, case, workspace)
                prompt = case.prompt_path.read_text(encoding="utf-8")
                print(f"[{current}/{total}] {model} · {case.id} · ripetizione {repetition}", flush=True)
                pi_run = run_pi(
                    config.pi_command,
                    model,
                    config.defaults.thinking,
                    prompt,
                    workspace,
                    agent_dir,
                    timeout,
                )
                grade = grade_workspace(case, workspace)
                git_status, diff, branch = _capture_git(workspace, baseline_commit)
                (case_dir / "pi-events.jsonl").write_text(pi_run.stdout, encoding="utf-8")
                (case_dir / "stderr.log").write_text(pi_run.stderr, encoding="utf-8")
                (case_dir / "final-response.md").write_text(pi_run.final_response, encoding="utf-8")
                (case_dir / "diff.patch").write_text(diff, encoding="utf-8")
                (case_dir / "git-status.txt").write_text(git_status, encoding="utf-8")
                (case_dir / "grade.json").write_text(json.dumps(grade, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
                result = {
                    "schema_version": 1,
                    "model": model,
                    "case_id": case.id,
                    "case_title": case.title,
                    "case_category": case.category,
                    "case_weight": case.weight,
                    "repetition": repetition,
                    "status": pi_run.status,
                    "exit_code": pi_run.exit_code,
                    "duration_seconds": pi_run.duration_seconds,
                    "metrics": pi_run.metrics,
                    "grade": grade,
                    "git_branch": branch,
                    "baseline_commit": baseline_commit,
                    "command": pi_run.command,
                }
                (case_dir / "result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
                print(
                    f"      stato={pi_run.status} score={grade.get('score', 0)}/100 tempo={pi_run.duration_seconds:.1f}s",
                    flush=True,
                )
                write_report(run_dir)

        try:
            unload(config.ollama_url, model)
        except Exception as exc:
            print(f"[avviso] unload fallito per {model}: {exc}", file=sys.stderr, flush=True)

    manifest["finished_at"] = datetime.now(timezone.utc).isoformat()
    (run_dir / "run.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_report(run_dir)
    return run_dir
