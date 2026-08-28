"""Persistent application preferences."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class Settings:
    language: str = "en"
    theme: str = "light"
    autosave_seconds: int = 30


def load_settings(path: str | Path) -> Settings:
    config_path = Path(path)
    if not config_path.exists():
        return Settings()
    data = json.loads(config_path.read_text(encoding="utf-8"))
    return Settings(**data)


def save_settings(path: str | Path, settings: Settings) -> None:
    config_path = Path(path)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(asdict(settings), indent=2) + "\n", encoding="utf-8")
