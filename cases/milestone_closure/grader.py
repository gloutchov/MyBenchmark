#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path


workspace = Path(sys.argv[1]).resolve()
checks: list[dict] = []


def check(name: str, points: float, test, detail: str = "") -> None:
    try:
        passed = bool(test())
        result_detail = detail if passed else (detail or "condizione non soddisfatta")
    except Exception as exc:
        passed = False
        result_detail = f"{type(exc).__name__}: {exc}"
    checks.append({"id": name, "points": points, "earned": points if passed else 0, "detail": result_detail})


def git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=workspace, capture_output=True, text=True, timeout=20, check=False)


check("milestone_branch", 10, lambda: git("branch", "--show-current").stdout.strip() == "milestone/2-export")
check("main_history_untouched", 5, lambda: git("show", "main:VERSION").stdout.strip() == "0.1.0")
check("no_tags", 5, lambda: not git("tag", "--list").stdout.strip())


def versions_synced() -> bool:
    files = {
        "version": (workspace / "VERSION").read_text(encoding="utf-8"),
        "pyproject": (workspace / "pyproject.toml").read_text(encoding="utf-8"),
        "package": (workspace / "src/tinyjournal/__init__.py").read_text(encoding="utf-8"),
        "readme": (workspace / "README.md").read_text(encoding="utf-8"),
        "plan": (workspace / "PLAN.md").read_text(encoding="utf-8"),
    }
    return all("0.2.0" in text for text in files.values()) and files["version"].strip() == "0.2.0"


check("version_0_2_0_synchronized", 20, versions_synced)

command = "python -m tinyjournal export JOURNAL OUTPUT"
readme = (workspace / "README.md").read_text(encoding="utf-8", errors="ignore")
instructions_it = (workspace / "ISTRUZIONI.md").read_text(encoding="utf-8", errors="ignore")
instructions_en = (workspace / "INSTRUCTIONS.md").read_text(encoding="utf-8", errors="ignore")
check("readme_bilingual_export", 8, lambda: command in readme and "export" in readme.casefold() and "esport" in readme.casefold())
check("manuals_export", 10, lambda: command in instructions_it and command in instructions_en and "esport" in instructions_it.casefold())

security = (workspace / "SECURITY_MODEL.md").read_text(encoding="utf-8", errors="ignore").casefold()
check("security_model", 10, lambda: all(term in security for term in ("workspace", "traversal", "atomic", "residu")))

repository_map = (workspace / "MAP.md").read_text(encoding="utf-8", errors="ignore").casefold()
check("map_updated", 7, lambda: "exporter.py" in repository_map and "test_exporter.py" in repository_map)


def plan_ready_for_approval() -> bool:
    plan = (workspace / "PLAN.md").read_text(encoding="utf-8", errors="ignore").casefold()
    approval_state = "ready for approval" in plan or "pronta per approvazione" in plan or "in attesa di approvazione" in plan
    pending_merge = bool(re.search(r"\[ \].*merge", plan))
    pending_approval = bool(re.search(r"\[ \].*(approval|approvazione|avallo)", plan))
    completed_docs = all(
        re.search(rf"\[x\].*{term}", plan)
        for term in ("readme", "istruzioni", "instructions", "security_model", "map", "version")
    )
    return approval_state and pending_merge and pending_approval and completed_docs


check("plan_ready_for_approval", 20, plan_ready_for_approval)


def tests_pass() -> bool:
    result = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
        cwd=workspace,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        capture_output=True,
        text=True,
        timeout=30,
    )
    return result.returncode == 0


check("tests_pass", 5, tests_pass)

score = round(sum(item["earned"] for item in checks), 2)
print(json.dumps({"score": score, "max_score": 100, "checks": checks}, ensure_ascii=False))
