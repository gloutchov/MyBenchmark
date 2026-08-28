#!/usr/bin/env python3
from __future__ import annotations

import importlib
import json
import math
import os
import subprocess
import sys
from pathlib import Path


workspace = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(workspace / "src"))
checks: list[dict] = []


def check(name: str, points: float, test, detail: str = "") -> None:
    try:
        passed = bool(test())
        error = detail if passed else (detail or "condizione non soddisfatta")
    except Exception as exc:
        passed = False
        error = f"{type(exc).__name__}: {exc}"
    checks.append({"id": name, "points": points, "earned": points if passed else 0, "detail": error})


try:
    ledger_module = importlib.import_module("pocketledger.ledger")
    Ledger = ledger_module.Ledger
except Exception as exc:
    Ledger = None
    import_error = str(exc)
else:
    import_error = ""

check("package_import", 5, lambda: Ledger is not None, import_error)


def rejects(value) -> bool:
    if Ledger is None:
        return False
    try:
        Ledger().add_entry(value, "credit")
    except (TypeError, ValueError):
        return True
    return False


check("reject_bool", 8, lambda: rejects(True) and rejects(False))
check("reject_non_finite", 9, lambda: all(rejects(value) for value in (math.nan, math.inf, -math.inf)))


def refund_balance() -> bool:
    ledger = Ledger()
    ledger.add_entry(100, "credit")
    ledger.add_entry(25, "debit")
    ledger.add_entry(10, "refund")
    return ledger.balance() == 65


check("refund_balance", 16, refund_balance)


def atomic_import() -> bool:
    ledger = Ledger()
    ledger.add_entry(7, "credit")
    before = ledger.entries
    bad = "kind,amount,note\ncredit,5,ok\ndebit,not-a-number,bad\n"
    try:
        ledger.import_csv(bad)
    except (TypeError, ValueError, KeyError):
        pass
    return ledger.entries == before and ledger.balance() == 7


check("atomic_csv_import", 17, atomic_import)


def valid_import() -> bool:
    ledger = Ledger()
    count = ledger.import_csv("kind,amount,note\ncredit,8,a\nrefund,2,b\n")
    return count == 2 and ledger.balance() == 6 and len(ledger.entries) == 2


check("valid_csv_import", 10, valid_import)


def candidate_tests() -> bool:
    result = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
        cwd=workspace,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        capture_output=True,
        text=True,
        timeout=30,
    )
    return result.returncode == 0


check("candidate_tests_pass", 10, candidate_tests)
test_text = "\n".join(path.read_text(encoding="utf-8", errors="ignore") for path in (workspace / "tests").glob("*.py"))
check("regression_tests_added", 8, lambda: all(term in test_text.casefold() for term in ("refund", "nan", "atomic")))

readme = (workspace / "README.md").read_text(encoding="utf-8", errors="ignore") if (workspace / "README.md").exists() else ""
check("readme_updated", 7, lambda: "refund" in readme.casefold() and "atomic" in readme.casefold())

expected_formatting = '''"""Stable presentation helpers; unrelated to ledger calculations."""\n\n\ndef format_eur(amount: float) -> str:\n    return f"EUR {amount:.2f}"\n'''
check(
    "unrelated_module_untouched",
    5,
    lambda: (workspace / "src/pocketledger/formatting.py").read_text(encoding="utf-8") == expected_formatting,
)

pyproject = (workspace / "pyproject.toml").read_text(encoding="utf-8", errors="ignore")
check("no_dependencies_added", 5, lambda: "dependencies = []" in pyproject)

score = round(sum(item["earned"] for item in checks), 2)
print(json.dumps({"score": score, "max_score": 100, "checks": checks}, ensure_ascii=False))
