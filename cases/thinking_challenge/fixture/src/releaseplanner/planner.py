"""Exact release planning domain logic."""

from __future__ import annotations

from typing import Any


class PlanningError(ValueError):
    """Raised when a release specification or its feasible set is invalid."""


def plan_release(spec: dict[str, Any]) -> dict[str, Any]:
    """Return the optimal feasible plan for *spec* without mutating it."""
    raise NotImplementedError("release planning is not implemented")
