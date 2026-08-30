"""Configuration loading and validation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .sandbox import SANDBOX_MODES


class ConfigError(ValueError):
    """Raised when benchmark configuration is invalid."""


@dataclass(frozen=True)
class Defaults:
    timeout_seconds: int
    repetitions: int
    thinking: str
    warmup: bool
    keep_alive: str
    context_window: int
    max_tokens: int
    temperature: float
    sandbox: str


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


@dataclass(frozen=True)
class BenchmarkConfig:
    root: Path
    ollama_url: str
    pi_command: tuple[str, ...]
    models: str | tuple[str, ...]
    defaults: Defaults
    profiles: dict[str, tuple[str, ...]]
    cases: dict[str, CaseSpec]


def _require(mapping: dict[str, Any], key: str, expected: type) -> Any:
    value = mapping.get(key)
    if not isinstance(value, expected):
        raise ConfigError(f"'{key}' deve essere di tipo {expected.__name__}")
    return value


def _safe_case_id(value: str) -> bool:
    return bool(value) and all(ch.isalnum() or ch in "-_" for ch in value)


def load_config(path: Path) -> BenchmarkConfig:
    path = path.resolve()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigError(f"Impossibile leggere {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ConfigError("La radice di benchmark.json deve essere un oggetto")
    if raw.get("version") != 1:
        raise ConfigError("Versione configurazione non supportata (attesa: 1)")

    root = path.parent
    ollama = _require(raw, "ollama", dict)
    ollama_url = _require(ollama, "url", str).rstrip("/")
    parsed_url = urlparse(ollama_url)
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
        raise ConfigError("ollama.url deve essere un URL HTTP(S) valido")

    pi = _require(raw, "pi", dict)
    pi_command_raw = _require(pi, "command", list)
    if not pi_command_raw or not all(isinstance(item, str) and item for item in pi_command_raw):
        raise ConfigError("pi.command deve contenere almeno una stringa non vuota")

    defaults_raw = _require(raw, "defaults", dict)
    defaults = Defaults(
        timeout_seconds=int(defaults_raw.get("timeout_seconds", 1200)),
        repetitions=int(defaults_raw.get("repetitions", 1)),
        thinking=str(defaults_raw.get("thinking", "off")),
        warmup=bool(defaults_raw.get("warmup", True)),
        keep_alive=str(defaults_raw.get("keep_alive", "15m")),
        context_window=int(defaults_raw.get("context_window", 32768)),
        max_tokens=int(defaults_raw.get("max_tokens", 8192)),
        temperature=float(defaults_raw.get("temperature", 0)),
        sandbox=str(defaults_raw.get("sandbox", "audit")),
    )
    if defaults.timeout_seconds < 10 or defaults.repetitions < 1:
        raise ConfigError("timeout_seconds deve essere >= 10 e repetitions >= 1")
    if defaults.thinking not in {"off", "minimal", "low", "medium", "high", "xhigh", "max"}:
        raise ConfigError("Livello thinking non valido")
    if defaults.context_window < 4096 or defaults.max_tokens < 256:
        raise ConfigError("context_window o max_tokens troppo piccoli")
    if defaults.sandbox not in SANDBOX_MODES:
        raise ConfigError(f"defaults.sandbox deve essere uno tra: {', '.join(SANDBOX_MODES)}")

    models_raw = raw.get("models", "installed")
    if models_raw == "installed":
        models: str | tuple[str, ...] = "installed"
    elif isinstance(models_raw, list) and models_raw and all(isinstance(m, str) and m for m in models_raw):
        models = tuple(models_raw)
    else:
        raise ConfigError("models deve essere 'installed' o una lista non vuota")

    cases_raw = _require(raw, "cases", list)
    cases: dict[str, CaseSpec] = {}
    for item in cases_raw:
        if not isinstance(item, dict):
            raise ConfigError("Ogni caso deve essere un oggetto")
        case_id = _require(item, "id", str)
        if not _safe_case_id(case_id) or case_id in cases:
            raise ConfigError(f"ID caso non valido o duplicato: {case_id!r}")
        directory = (root / "cases" / case_id).resolve()
        if directory.parent != (root / "cases").resolve():
            raise ConfigError(f"Il caso esce da cases/: {case_id}")
        spec = CaseSpec(
            id=case_id,
            title=_require(item, "title", str),
            category=_require(item, "category", str),
            weight=float(item.get("weight", 1)),
            directory=directory,
            prompt_path=directory / "prompt.md",
            fixture_path=directory / "fixture",
            grader_path=directory / "grader.py",
        )
        if spec.weight <= 0:
            raise ConfigError(f"Peso non valido per {case_id}")
        for required_path in (spec.prompt_path, spec.fixture_path, spec.grader_path):
            if not required_path.exists():
                raise ConfigError(f"File del caso mancante: {required_path}")
        cases[case_id] = spec

    profiles_raw = _require(raw, "profiles", dict)
    profiles: dict[str, tuple[str, ...]] = {}
    for name, ids in profiles_raw.items():
        if not isinstance(ids, list) or not ids or not all(isinstance(i, str) for i in ids):
            raise ConfigError(f"Profilo non valido: {name}")
        unknown = set(ids) - set(cases)
        if unknown:
            raise ConfigError(f"Casi sconosciuti nel profilo {name}: {', '.join(sorted(unknown))}")
        profiles[name] = tuple(ids)
    if "standard" not in profiles:
        raise ConfigError("È richiesto il profilo 'standard'")

    return BenchmarkConfig(
        root=root,
        ollama_url=ollama_url,
        pi_command=tuple(pi_command_raw),
        models=models,
        defaults=defaults,
        profiles=profiles,
        cases=cases,
    )
