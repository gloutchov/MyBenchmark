"""Small Ollama HTTP client using only the Python standard library."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


class OllamaError(RuntimeError):
    """Raised when the local Ollama service cannot satisfy a request."""


@dataclass(frozen=True)
class OllamaModel:
    name: str
    size: int | None
    digest: str | None
    modified_at: str | None
    details: dict[str, Any]


def _request(url: str, path: str, payload: dict[str, Any] | None = None, timeout: int = 30) -> Any:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        f"{url.rstrip('/')}{path}",
        data=data,
        headers={"Content-Type": "application/json"} if data else {},
        method="POST" if data else "GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise OllamaError(f"Ollama non raggiungibile su {url}: {exc}") from exc


def list_models(url: str) -> list[OllamaModel]:
    raw = _request(url, "/api/tags")
    models = raw.get("models", []) if isinstance(raw, dict) else []
    result: list[OllamaModel] = []
    for item in models:
        if not isinstance(item, dict) or not isinstance(item.get("name"), str):
            continue
        result.append(
            OllamaModel(
                name=item["name"],
                size=item.get("size") if isinstance(item.get("size"), int) else None,
                digest=item.get("digest") if isinstance(item.get("digest"), str) else None,
                modified_at=item.get("modified_at") if isinstance(item.get("modified_at"), str) else None,
                details=item.get("details") if isinstance(item.get("details"), dict) else {},
            )
        )
    return sorted(result, key=lambda model: model.name.casefold())


def version(url: str) -> str | None:
    raw = _request(url, "/api/version")
    return raw.get("version") if isinstance(raw, dict) and isinstance(raw.get("version"), str) else None


def warmup(url: str, model: str, keep_alive: str, timeout: int) -> dict[str, Any]:
    raw = _request(
        url,
        "/api/generate",
        {
            "model": model,
            "prompt": "Reply with exactly: OK",
            "stream": False,
            "keep_alive": keep_alive,
            "options": {"temperature": 0, "num_predict": 8},
        },
        timeout=timeout,
    )
    return raw if isinstance(raw, dict) else {}


def unload(url: str, model: str) -> None:
    _request(
        url,
        "/api/generate",
        {"model": model, "keep_alive": 0},
        timeout=30,
    )
