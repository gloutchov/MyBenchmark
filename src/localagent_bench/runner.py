"""Benchmark orchestration and artifact capture."""

from __future__ import annotations

import hashlib
import json
import platform
import random
import re
import secrets
import shutil
import subprocess
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import BenchmarkConfig, CaseSpec
from .grading import grade_workspace
from .integrity import (
    InputIntegrityError,
    changed_paths,
    repository_fingerprints,
    repository_metadata,
    require_clean_inputs,
    snapshot_cases,
    verify_snapshot,
)
from .ollama import OllamaModel, list_models, unload, version, warmup
from .pi_adapter import AUDIT_VERSION, SCRATCH_DIRECTORY, audit_workspace_accesses, run_pi, write_models_config
from .report import write_report


class BenchmarkError(RuntimeError):
    """Raised for failures that prevent a benchmark run from starting."""


EXECUTION_POLICY = f"""# Confine di esecuzione del benchmark / Benchmark execution boundary

- Opera soltanto nella directory di lavoro corrente e nei suoi discendenti. Non leggere, elencare, copiare o modificare altri path, inclusi repository reali e directory sorelle.
- Work only in the current working directory and its descendants. Do not read, list, copy, or modify any other path, including real repositories and sibling directories.
- Non usare directory temporanee di sistema come `/tmp`. Per smoke test e file temporanei usa `{SCRATCH_DIRECTORY}/`, che il runner prepara e ignora in Git.
- Do not use system temporary directories such as `/tmp`. Use `{SCRATCH_DIRECTORY}/` for smoke tests and temporary files; the runner prepares it and excludes it from Git.
- Non accedere alla rete con shell, interpreti, package manager o Git. Tutti gli input necessari sono già nella workspace; segnala come limite un eventuale materiale mancante senza cercarlo altrove.
- Do not access the network through shell commands, interpreters, package managers, or Git. All required inputs are already in the workspace; report missing material as a limitation instead of searching elsewhere.
- Per testare un rifiuto di traversal, crea una sottodirectory dentro `{SCRATCH_DIRECTORY}/` e usa quella come workspace dell'applicazione, così anche il path di prova resta nel confine del benchmark.
- To test traversal rejection, create a nested directory under `{SCRATCH_DIRECTORY}/` and use it as the application workspace, so the attempted test path remains inside the benchmark boundary.

Un riferimento esplicito fuori da questo confine o un tentativo di rete invalida il risultato anche quando il comando fallisce.
An explicit reference outside this boundary or a network attempt invalidates the result even if the command fails.
"""


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


def _prepare_workspace(
    config: BenchmarkConfig,
    case: CaseSpec,
    destination: Path,
    agents_path: Path | None = None,
    gitignore_path: Path | None = None,
) -> str:
    shutil.copytree(case.fixture_path, destination, symlinks=True)
    shutil.copy2(gitignore_path or config.root / ".gitignore", destination / ".gitignore")
    shutil.copy2(agents_path or config.root / "AGENTS.md", destination / "AGENTS.md")
    try:
        _git(destination, "init", "-q", "-b", "main")
    except subprocess.CalledProcessError:
        _git(destination, "init", "-q")
        _git(destination, "branch", "-M", "main")
    _git(destination, "config", "user.name", "LocalAgent Benchmark")
    _git(destination, "config", "user.email", "benchmark@localhost")
    _git(destination, "add", ".")
    _git(destination, "commit", "-q", "-m", "benchmark baseline")
    baseline_commit = _git(destination, "rev-parse", "HEAD").stdout.strip()
    scratch = destination / SCRATCH_DIRECTORY
    scratch.mkdir(parents=True, exist_ok=True)
    exclude_path = destination / ".git" / "info" / "exclude"
    exclude_entry = f"/{SCRATCH_DIRECTORY}/"
    exclude_lines = exclude_path.read_text(encoding="utf-8").splitlines() if exclude_path.exists() else []
    if exclude_entry not in exclude_lines:
        exclude_path.parent.mkdir(parents=True, exist_ok=True)
        exclude_path.write_text("\n".join([*exclude_lines, exclude_entry, ""]), encoding="utf-8")
    return baseline_commit


def _write_manifest(run_dir: Path, manifest: dict[str, Any]) -> None:
    (run_dir / "run.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _record_integrity_violation(
    manifest: dict[str, Any],
    *,
    model: str,
    case_id: str,
    repetition: int,
    kind: str,
    details: list[Any],
) -> None:
    integrity = manifest["integrity"]
    integrity["status"] = "violations_detected"
    integrity["violations"].append(
        {
            "model": model,
            "case_id": case_id,
            "repetition": repetition,
            "kind": kind,
            "details": details,
        }
    )


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


def _build_task_order(
    models: list[str],
    cases: list[CaseSpec],
    repetitions: int,
    seed: int,
) -> list[dict[str, str | int]]:
    tasks: list[dict[str, str | int]] = [
        {"model": model, "case_id": case.id, "repetition": repetition}
        for model in models
        for case in cases
        for repetition in range(1, repetitions + 1)
    ]
    random.Random(seed).shuffle(tasks)
    return tasks


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
    try:
        require_clean_inputs(config.root, config.cases.values())
    except InputIntegrityError as exc:
        checks.append({"name": "inputs", "ok": False, "detail": str(exc).splitlines()[0]})
    else:
        checks.append({"name": "inputs", "ok": True, "detail": "AGENTS, .gitignore, prompt, fixture e grader puliti"})
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
    order_seed: int | None = None,
) -> Path:
    cases = _resolve_cases(config, profile, requested_cases)
    try:
        require_clean_inputs(config.root, cases)
    except InputIntegrityError as exc:
        raise BenchmarkError(str(exc)) from exc
    installed = list_models(config.ollama_url)
    models = _resolve_models(config, requested_models, installed)
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
    context_dir = run_dir / "benchmark-context"
    try:
        frozen_cases, input_manifest = snapshot_cases(
            cases,
            context_dir,
            config.root / "AGENTS.md",
            config.root / ".gitignore",
            EXECUTION_POLICY,
        )
    except InputIntegrityError as exc:
        raise BenchmarkError(str(exc)) from exc
    frozen_by_id = {case.id: case for case in frozen_cases}
    repository_state = repository_fingerprints(config.root, (run_dir,))
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
    seed = order_seed if order_seed is not None else secrets.randbits(64)
    tasks = _build_task_order(models, cases, repeat_count, seed)
    manifest = {
        "schema_version": 2,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "profile": profile,
        "models": models,
        "cases": [case.id for case in cases],
        "repetitions": repeat_count,
        "timeout_seconds": timeout,
        "thinking": config.defaults.thinking,
        "warmup": should_warmup,
        "warmup_events": [],
        "order_seed": seed,
        "task_order": tasks,
        "repository": repository_metadata(config.root),
        "inputs": input_manifest,
        "execution_policy": {
            "audit_version": AUDIT_VERSION,
            "sha256": input_manifest.get("execution_policy_sha256"),
            "scratch_directory": SCRATCH_DIRECTORY,
            "network_access": "forbidden",
            "filesystem_scope": "task_workspace",
        },
        "integrity": {"status": "passed", "aborted": False, "violations": []},
        "environment": {
            "platform": platform.platform(),
            "python": sys.version.split()[0],
            "pi": _command_version([*config.pi_command, "--version"]),
            "ollama": version(config.ollama_url),
        },
        "model_metadata": {name: asdict(installed_by_name[name]) for name in models},
    }
    _write_manifest(run_dir, manifest)

    active_model: str | None = None
    protected_paths = (config.root,)
    for current, task in enumerate(tasks, 1):
        model = str(task["model"])
        case_id = str(task["case_id"])
        repetition = int(task["repetition"])
        case = frozen_by_id[case_id]
        snapshot_before = verify_snapshot(context_dir, input_manifest)
        if snapshot_before:
            manifest["integrity"]["status"] = "snapshot_compromised"
            manifest["integrity"]["aborted"] = True
            manifest["integrity"]["violations"].append(
                {"kind": "snapshot_changed_before_task", "details": snapshot_before}
            )
            break
        if active_model != model:
            if active_model is not None:
                try:
                    unload(config.ollama_url, active_model)
                except Exception as exc:
                    print(f"[avviso] unload fallito per {active_model}: {exc}", file=sys.stderr, flush=True)
            if should_warmup:
                print(f"[warmup] {model}", flush=True)
                event: dict[str, Any] = {"sequence": current, "model": model}
                try:
                    warmup_result = warmup(config.ollama_url, model, config.defaults.keep_alive, min(timeout, 300))
                    event["metrics"] = {
                        key: warmup_result.get(key)
                        for key in ("total_duration", "load_duration", "prompt_eval_count", "eval_count", "eval_duration")
                        if key in warmup_result
                    }
                except Exception as exc:
                    event["error"] = str(exc)
                    print(f"[avviso] warmup fallito per {model}: {exc}", file=sys.stderr, flush=True)
                manifest["warmup_events"].append(event)
                _write_manifest(run_dir, manifest)
            active_model = model

        case_dir = run_dir / "models" / _slug(model) / "cases" / f"{case.id}-r{repetition}"
        workspace = case_dir / "workspace"
        case_dir.mkdir(parents=True, exist_ok=True)
        baseline_commit = _prepare_workspace(
            config,
            case,
            workspace,
            context_dir / "AGENTS.snapshot.md",
            context_dir / ".gitignore.snapshot",
        )
        baseline_tree = _git(workspace, "rev-parse", f"{baseline_commit}^{{tree}}").stdout.strip()
        prompt = "\n\n".join(
            (
                (context_dir / "EXECUTION_POLICY.snapshot.md").read_text(encoding="utf-8").rstrip(),
                case.prompt_path.read_text(encoding="utf-8").lstrip(),
            )
        )
        print(f"[{current}/{len(tasks)}] {model} · {case.id} · ripetizione {repetition}", flush=True)
        before_task_repository = repository_state
        pi_run = run_pi(
            config.pi_command,
            model,
            config.defaults.thinking,
            prompt,
            workspace,
            agent_dir,
            timeout,
        )
        after_task_repository = repository_fingerprints(config.root, (run_dir,))
        source_mutations = changed_paths(before_task_repository, after_task_repository)
        repository_state = after_task_repository
        snapshot_mutations = verify_snapshot(context_dir, input_manifest)
        external_accesses = audit_workspace_accesses(pi_run.stdout, workspace, protected_paths)
        valid_for_ranking = not source_mutations and not snapshot_mutations and not external_accesses
        if source_mutations:
            _record_integrity_violation(
                manifest,
                model=model,
                case_id=case.id,
                repetition=repetition,
                kind="repository_mutation",
                details=source_mutations,
            )
        if external_accesses:
            _record_integrity_violation(
                manifest,
                model=model,
                case_id=case.id,
                repetition=repetition,
                kind="external_workspace_access",
                details=external_accesses,
            )
        if snapshot_mutations:
            manifest["integrity"]["status"] = "snapshot_compromised"
            manifest["integrity"]["aborted"] = True
            manifest["integrity"]["violations"].append(
                {
                    "model": model,
                    "case_id": case.id,
                    "repetition": repetition,
                    "kind": "snapshot_mutation",
                    "details": snapshot_mutations,
                }
            )
            grade = {
                "score": 0,
                "max_score": 100,
                "checks": [],
                "error": "Grader non eseguito: snapshot degli input modificato durante la task",
            }
        else:
            grade = grade_workspace(case, workspace)
        git_status, diff, branch = _capture_git(workspace, baseline_commit)
        (case_dir / "pi-events.jsonl").write_text(pi_run.stdout, encoding="utf-8")
        (case_dir / "stderr.log").write_text(pi_run.stderr, encoding="utf-8")
        (case_dir / "final-response.md").write_text(pi_run.final_response, encoding="utf-8")
        (case_dir / "diff.patch").write_text(diff, encoding="utf-8")
        (case_dir / "git-status.txt").write_text(git_status, encoding="utf-8")
        (case_dir / "grade.json").write_text(json.dumps(grade, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        result = {
            "schema_version": 2,
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
            "baseline_tree": baseline_tree,
            "input_fingerprint": input_manifest["cases"][case.id]["effective_input_sha256"],
            "integrity": {
                "audit_version": AUDIT_VERSION,
                "valid_for_ranking": valid_for_ranking,
                "source_mutations": source_mutations,
                "snapshot_mutations": snapshot_mutations,
                "external_accesses": external_accesses,
            },
            "command": pi_run.command,
        }
        (case_dir / "result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        _write_manifest(run_dir, manifest)
        print(
            f"      stato={pi_run.status} score={grade.get('score', 0)}/100 "
            f"integrità={'ok' if valid_for_ranking else 'violata'} tempo={pi_run.duration_seconds:.1f}s",
            flush=True,
        )
        write_report(run_dir)
        if snapshot_mutations:
            break

    if active_model is not None:
        try:
            unload(config.ollama_url, active_model)
        except Exception as exc:
            print(f"[avviso] unload fallito per {active_model}: {exc}", file=sys.stderr, flush=True)

    manifest["finished_at"] = datetime.now(timezone.utc).isoformat()
    _write_manifest(run_dir, manifest)
    write_report(run_dir)
    return run_dir
