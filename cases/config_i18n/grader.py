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
    package = importlib.import_module("notekeeper")
    config_module = importlib.import_module("notekeeper.config")
    i18n_module = importlib.import_module("notekeeper.i18n")
    Settings = package.Settings
    ConfigError = package.ConfigError
    load_settings = package.load_settings
    save_settings = package.save_settings
    resolve_language = package.resolve_language
    resolve_theme = package.resolve_theme
    translate = package.translate
except Exception as exc:
    Settings = ConfigError = load_settings = save_settings = None
    resolve_language = resolve_theme = translate = None
    config_module = i18n_module = None
    import_error = str(exc)
else:
    import_error = ""

check("package_import", 5, lambda: Settings is not None, import_error)
check(
    "defaults",
    5,
    lambda: Settings().language == "auto" and Settings().theme == "auto" and Settings().autosave_seconds == 30,
)


def valid_load() -> bool:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "settings.json"
        path.write_text('{"language":"it","theme":"dark","autosave_seconds":90}', encoding="utf-8")
        return load_settings(path) == Settings(language="it", theme="dark", autosave_seconds=90)


check("valid_load", 10, valid_load)


def missing_defaults() -> bool:
    with tempfile.TemporaryDirectory() as directory:
        return load_settings(Path(directory) / "missing.json") == Settings()


check("missing_file_fallback", 5, missing_defaults)


def config_rejects(payload: str) -> bool:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "settings.json"
        path.write_text(payload, encoding="utf-8")
        try:
            load_settings(path)
        except ConfigError:
            return True
        except Exception:
            return False
        return False


check(
    "invalid_language_theme",
    10,
    lambda: config_rejects('{"language":"fr"}') and config_rejects('{"theme":"blue"}') and config_rejects("{broken"),
)
check(
    "invalid_autosave",
    10,
    lambda: all(
        config_rejects(json.dumps({"autosave_seconds": value}))
        for value in (True, 4, 3601, 3.5, "30")
    ),
)


def unknown_ignored() -> bool:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "settings.json"
        path.write_text('{"language":"en","future_option":42}', encoding="utf-8")
        settings = load_settings(path)
        return settings.language == "en" and not hasattr(settings, "future_option")


check("unknown_keys_ignored", 5, unknown_ignored)
check(
    "language_resolution",
    10,
    lambda: all(
        (
            resolve_language("auto", "it_IT") == "it",
            resolve_language("auto", "IT-ch") == "it",
            resolve_language("auto", "en_US") == "en",
            resolve_language("auto", None) == "en",
            resolve_language("it", "en_US") == "it",
        )
    ),
)
check(
    "theme_resolution",
    8,
    lambda: resolve_theme("auto", True) == "dark"
    and resolve_theme("auto", False) == "light"
    and resolve_theme("dark", False) == "dark",
)


def dictionaries_synced() -> bool:
    strings = getattr(i18n_module, "STRINGS", {})
    return set(strings) >= {"it", "en"} and set(strings["it"]) == set(strings["en"]) and set(strings["it"]) >= {"title", "saved", "error"}


check("i18n_dictionaries_synced", 12, dictionaries_synced)
def translations() -> bool:
    if translate("saved", "it") == translate("saved", "en"):
        return False
    try:
        translate("missing", "en")
    except KeyError:
        return True
    return False


check("translations_and_missing_key", 6, translations)


def atomic_round_trip() -> bool:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "nested" / "settings.json"
        settings = Settings(language="it", theme="dark", autosave_seconds=60)
        save_settings(path, settings)
        leftovers = [item for item in path.parent.iterdir() if item != path]
        source = inspect.getsource(save_settings).casefold()
        uses_atomic_replace = "os.replace" in source or ".replace(" in source
        return load_settings(path) == settings and not leftovers and uses_atomic_replace


check("atomic_save_round_trip", 5, atomic_round_trip)


def candidate_tests() -> bool:
    result = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
        cwd=workspace,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        capture_output=True,
        text=True,
        timeout=30,
    )
    contents = "\n".join(path.read_text(encoding="utf-8", errors="ignore") for path in (workspace / "tests").glob("*.py"))
    return result.returncode == 0 and "resolve_language" in contents and "invalid" in contents.casefold()


check("candidate_tests", 4, candidate_tests)
docs = "\n".join(
    (workspace / name).read_text(encoding="utf-8", errors="ignore") if (workspace / name).exists() else ""
    for name in ("README.md", "ISTRUZIONI.md", "INSTRUCTIONS.md", "MAP.md")
).casefold()
check("documentation_updated", 5, lambda: all(term in docs for term in ("autosave", "automatic", "config")))

score = round(sum(item["earned"] for item in checks), 2)
print(json.dumps({"score": score, "max_score": 100, "checks": checks}, ensure_ascii=False))
