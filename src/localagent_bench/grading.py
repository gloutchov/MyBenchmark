"""Run case graders outside the candidate workspace."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from .config import CaseSpec


def grade_workspace(case: CaseSpec, workspace: Path, timeout_seconds: int = 120) -> dict[str, Any]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        result = subprocess.run(
            [sys.executable, str(case.grader_path), str(workspace)],
            cwd=case.directory,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "score": 0,
            "max_score": 100,
            "checks": [],
            "error": f"Grader timeout dopo {timeout_seconds}s",
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or "",
        }
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {
            "score": 0,
            "max_score": 100,
            "checks": [],
            "error": f"Output grader non valido (exit {result.returncode})",
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
    if not isinstance(payload, dict):
        return {"score": 0, "max_score": 100, "checks": [], "error": "Il grader non ha restituito un oggetto"}
    payload["grader_exit_code"] = result.returncode
    if result.stderr:
        payload["grader_stderr"] = result.stderr
    return payload
