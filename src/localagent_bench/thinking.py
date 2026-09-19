"""Canonical, provider-facing thinking policy for benchmark runs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


THINKING_CONTROL_VERSION = 1
THINKING_LEVELS = ("off", "minimal", "low", "medium", "high", "xhigh", "max")
OLLAMA_REASONING_EFFORT = {
    "off": "none",
    "minimal": "low",
    "low": "low",
    "medium": "medium",
    "high": "high",
    "xhigh": "max",
    "max": "max",
}
PI_THINKING_LEVEL_MAP = dict(OLLAMA_REASONING_EFFORT)


class ThinkingPolicyError(ValueError):
    """Raised when a requested thinking level cannot be canonicalized."""


@dataclass(frozen=True)
class ThinkingPolicy:
    """Requested Pi level and the exact value sent to Ollama."""

    requested: str
    reasoning_effort: str

    @property
    def active(self) -> bool:
        return self.reasoning_effort != "none"

    @property
    def native_think(self) -> bool | str:
        return self.reasoning_effort if self.active else False

    def to_manifest(self) -> dict[str, Any]:
        return {
            "version": THINKING_CONTROL_VERSION,
            "requested": self.requested,
            "reasoning_effort": self.reasoning_effort,
            "source": "explicit_sampling_parameter",
        }


def resolve_thinking_policy(requested: str) -> ThinkingPolicy:
    """Return the explicit Ollama control for a supported Pi level."""
    if requested not in OLLAMA_REASONING_EFFORT:
        raise ThinkingPolicyError(
            f"Livello thinking non valido: {requested!r}; attesi {', '.join(THINKING_LEVELS)}"
        )
    return ThinkingPolicy(requested=requested, reasoning_effort=OLLAMA_REASONING_EFFORT[requested])


def metrics_show_thinking(metrics: dict[str, Any]) -> bool:
    """Detect observable reasoning without reading or retaining its content."""
    streamed = metrics.get("streamed_thinking_chars", 0)
    usage = metrics.get("usage") if isinstance(metrics.get("usage"), dict) else {}
    reasoning_tokens = usage.get("reasoning", 0)
    return (
        isinstance(streamed, (int, float))
        and not isinstance(streamed, bool)
        and streamed > 0
    ) or (
        isinstance(reasoning_tokens, (int, float))
        and not isinstance(reasoning_tokens, bool)
        and reasoning_tokens > 0
    )
