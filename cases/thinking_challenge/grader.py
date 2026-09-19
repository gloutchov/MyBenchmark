#!/usr/bin/env python3
from __future__ import annotations

import copy
import importlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


workspace = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(workspace / "src"))
checks: list[dict[str, Any]] = []


def check(name: str, points: int, test, detail: str = "") -> None:
    try:
        passed = bool(test())
        result_detail = detail if passed else (detail or "condizione non soddisfatta")
    except Exception as exc:
        passed = False
        result_detail = f"{type(exc).__name__}: {exc}"
    checks.append({"id": name, "points": points, "earned": points if passed else 0, "detail": result_detail})


try:
    package = importlib.import_module("releaseplanner")
    PlanningError = package.PlanningError
    plan_release = package.plan_release
except Exception as exc:
    PlanningError = None
    plan_release = None
    import_error = str(exc)
else:
    import_error = ""


check(
    "api_import",
    5,
    lambda: isinstance(PlanningError, type)
    and issubclass(PlanningError, ValueError)
    and callable(plan_release),
    import_error,
)


PUBLIC_SPEC = {
    "budget": 12,
    "risk_limit": 6,
    "team_capacities": {"backend": 4, "mobile": 3, "data": 2},
    "required_categories": ["security", "experience"],
    "mandatory": ["foundation"],
    "initiatives": [
        {"id": "foundation", "value": 3, "cost": 1, "risk": 0, "category": "platform", "team_effort": {"backend": 1}, "requires": [], "conflicts": []},
        {"id": "auth", "value": 9, "cost": 3, "risk": 2, "category": "security", "team_effort": {"backend": 2}, "requires": ["foundation"], "conflicts": []},
        {"id": "passkeys", "value": 10, "cost": 4, "risk": 1, "category": "security", "team_effort": {"mobile": 2}, "requires": ["auth"], "conflicts": []},
        {"id": "offline", "value": 8, "cost": 3, "risk": 2, "category": "experience", "team_effort": {"mobile": 2}, "requires": [], "conflicts": ["sync"]},
        {"id": "sync", "value": 11, "cost": 5, "risk": 3, "category": "experience", "team_effort": {"backend": 2, "data": 1}, "requires": ["foundation"], "conflicts": []},
        {"id": "insights", "value": 7, "cost": 3, "risk": 2, "category": "analytics", "team_effort": {"data": 2}, "requires": [], "conflicts": []},
        {"id": "polish", "value": 6, "cost": 2, "risk": 1, "category": "experience", "team_effort": {"mobile": 1}, "requires": [], "conflicts": []},
    ],
}

HIDDEN_SPEC_A = {
    "budget": 10,
    "risk_limit": 5,
    "team_capacities": {"api": 4, "ops": 3},
    "required_categories": ["reliability"],
    "mandatory": ["bootstrap"],
    "initiatives": [
        {"id": "bootstrap", "value": 2, "cost": 1, "risk": 0, "category": "base", "team_effort": {"api": 1}, "requires": [], "conflicts": []},
        {"id": "cache", "value": 8, "cost": 3, "risk": 1, "category": "performance", "team_effort": {"api": 2}, "requires": ["bootstrap"], "conflicts": []},
        {"id": "replica", "value": 10, "cost": 4, "risk": 2, "category": "reliability", "team_effort": {"ops": 2}, "requires": ["bootstrap"], "conflicts": ["backup"]},
        {"id": "backup", "value": 7, "cost": 2, "risk": 1, "category": "reliability", "team_effort": {"ops": 2}, "requires": [], "conflicts": []},
        {"id": "observe", "value": 6, "cost": 2, "risk": 1, "category": "operations", "team_effort": {"ops": 1}, "requires": [], "conflicts": []},
        {"id": "compress", "value": 5, "cost": 2, "risk": 2, "category": "performance", "team_effort": {"api": 1}, "requires": [], "conflicts": ["cache"]},
        {"id": "migration", "value": 12, "cost": 6, "risk": 4, "category": "reliability", "team_effort": {"api": 2, "ops": 2}, "requires": ["bootstrap"], "conflicts": ["backup"]},
    ],
}

HIDDEN_SPEC_B = {
    "budget": 9,
    "risk_limit": 5,
    "team_capacities": {"red": 3, "blue": 3, "green": 2},
    "required_categories": ["customer", "security"],
    "mandatory": [],
    "initiatives": [
        {"id": "gate", "value": 0, "cost": 0, "risk": 0, "category": "platform", "team_effort": {"green": 1}, "requires": [], "conflicts": []},
        {"id": "shield", "value": 9, "cost": 4, "risk": 2, "category": "security", "team_effort": {"red": 2}, "requires": ["gate"], "conflicts": []},
        {"id": "audit", "value": 6, "cost": 2, "risk": 1, "category": "security", "team_effort": {"green": 1}, "requires": [], "conflicts": []},
        {"id": "portal", "value": 10, "cost": 4, "risk": 2, "category": "customer", "team_effort": {"blue": 2}, "requires": [], "conflicts": ["mobile"]},
        {"id": "mobile", "value": 11, "cost": 5, "risk": 2, "category": "customer", "team_effort": {"blue": 3}, "requires": [], "conflicts": []},
        {"id": "search", "value": 7, "cost": 3, "risk": 2, "category": "customer", "team_effort": {"red": 1, "blue": 1}, "requires": [], "conflicts": []},
        {"id": "cleanup", "value": 4, "cost": 1, "risk": 0, "category": "hygiene", "team_effort": {"red": 1}, "requires": [], "conflicts": []},
        {"id": "export", "value": 8, "cost": 3, "risk": 2, "category": "data", "team_effort": {"green": 2}, "requires": ["audit"], "conflicts": []},
    ],
}


def reference_plan(spec: dict[str, Any]) -> dict[str, Any] | None:
    initiatives = spec["initiatives"]
    capacities = spec["team_capacities"]
    mandatory = set(spec["mandatory"])
    required_categories = set(spec["required_categories"])
    best_key: tuple[Any, ...] | None = None
    best_result: dict[str, Any] | None = None
    for mask in range(1 << len(initiatives)):
        chosen = [item for index, item in enumerate(initiatives) if mask & (1 << index)]
        selected = {item["id"] for item in chosen}
        if not mandatory <= selected:
            continue
        if not required_categories <= {item["category"] for item in chosen}:
            continue
        if any(not set(item["requires"]) <= selected for item in chosen):
            continue
        if any(set(item["conflicts"]) & selected for item in chosen):
            continue
        total_cost = sum(item["cost"] for item in chosen)
        total_risk = sum(item["risk"] for item in chosen)
        if total_cost > spec["budget"] or total_risk > spec["risk_limit"]:
            continue
        usage = {
            team: sum(item["team_effort"].get(team, 0) for item in chosen)
            for team in capacities
        }
        if any(usage[team] > capacity for team, capacity in capacities.items()):
            continue
        selected_ids = sorted(selected)
        total_value = sum(item["value"] for item in chosen)
        key = (-total_value, total_cost, total_risk, tuple(selected_ids))
        if best_key is None or key < best_key:
            best_key = key
            best_result = {
                "selected": selected_ids,
                "total_value": total_value,
                "total_cost": total_cost,
                "total_risk": total_risk,
                "team_usage": usage,
            }
    return best_result


def candidate_matches(spec: dict[str, Any]) -> bool:
    if plan_release is None:
        return False
    payload = copy.deepcopy(spec)
    before = copy.deepcopy(payload)
    result = plan_release(payload)
    return payload == before and result == reference_plan(spec)


def rejects_invalid_specs() -> bool:
    if plan_release is None or PlanningError is None:
        return False
    invalid_specs: list[dict[str, Any]] = []

    invalid_specs.append({**copy.deepcopy(PUBLIC_SPEC), "budget": True})
    invalid_specs.append({**copy.deepcopy(PUBLIC_SPEC), "unknown": 1})

    duplicate = copy.deepcopy(PUBLIC_SPEC)
    duplicate["initiatives"][1]["id"] = "foundation"
    invalid_specs.append(duplicate)

    unknown_dependency = copy.deepcopy(PUBLIC_SPEC)
    unknown_dependency["initiatives"][1]["requires"] = ["missing"]
    invalid_specs.append(unknown_dependency)

    unknown_team = copy.deepcopy(PUBLIC_SPEC)
    unknown_team["initiatives"][0]["team_effort"] = {"ghost": 1}
    invalid_specs.append(unknown_team)

    overlapping_relation = copy.deepcopy(PUBLIC_SPEC)
    overlapping_relation["initiatives"][1]["conflicts"] = ["foundation"]
    invalid_specs.append(overlapping_relation)

    unknown_category = copy.deepcopy(PUBLIC_SPEC)
    unknown_category["required_categories"] = ["missing"]
    invalid_specs.append(unknown_category)

    for invalid in invalid_specs:
        try:
            plan_release(invalid)
        except PlanningError:
            continue
        except Exception:
            return False
        return False
    return True


check("strict_validation", 12, rejects_invalid_specs)
check("public_optimum", 18, lambda: candidate_matches(PUBLIC_SPEC))
check("hidden_dependencies_conflicts", 20, lambda: candidate_matches(HIDDEN_SPEC_A))
check("hidden_capacities_categories", 15, lambda: candidate_matches(HIDDEN_SPEC_B))


TIE_SPEC = {
    "budget": 2,
    "risk_limit": 1,
    "team_capacities": {"solo": 1},
    "required_categories": ["feature"],
    "mandatory": [],
    "initiatives": [
        {"id": "beta", "value": 5, "cost": 2, "risk": 1, "category": "feature", "team_effort": {"solo": 1}, "requires": [], "conflicts": []},
        {"id": "alpha", "value": 5, "cost": 2, "risk": 1, "category": "feature", "team_effort": {"solo": 1}, "requires": [], "conflicts": []},
    ],
}
check("lexicographic_tie_break", 10, lambda: candidate_matches(TIE_SPEC))


def rejects_infeasible() -> bool:
    if plan_release is None or PlanningError is None:
        return False
    impossible = copy.deepcopy(TIE_SPEC)
    impossible["budget"] = 1
    try:
        plan_release(impossible)
    except PlanningError:
        return True
    return False


check("infeasible_plan", 5, rejects_infeasible)


def cli_contract() -> bool:
    with tempfile.TemporaryDirectory() as directory:
        spec_path = Path(directory) / "spec.json"
        spec_path.write_text(json.dumps(PUBLIC_SPEC), encoding="utf-8")
        completed = subprocess.run(
            [sys.executable, "-m", "releaseplanner", str(spec_path)],
            cwd=workspace,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONPATH": str(workspace / "src")},
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if completed.returncode != 0 or completed.stderr.strip():
            return False
        return json.loads(completed.stdout) == reference_plan(PUBLIC_SPEC)


check("cli_json_contract", 5, cli_contract)


def candidate_tests() -> bool:
    completed = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
        cwd=workspace,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    contents = "\n".join(
        path.read_text(encoding="utf-8", errors="ignore")
        for path in (workspace / "tests").glob("*.py")
    ).casefold()
    return completed.returncode == 0 and all(term in contents for term in ("tie", "conflict")) and (
        "depend" in contents or "requires" in contents
    ) and ("invalid" in contents or "reject" in contents)


check("candidate_regression_tests", 5, candidate_tests)


EXPECTED_FORMATTING = '''"""Stable presentation helper unrelated to planning decisions."""\n\n\ndef format_summary(selected: list[str], value: int) -> str:\n    return f"{', '.join(selected)} | value={value}"\n'''


def documentation_and_scope() -> bool:
    readme_path = workspace / "README.md"
    pyproject_path = workspace / "pyproject.toml"
    formatting_path = workspace / "src/releaseplanner/formatting.py"
    if not readme_path.is_file() or not pyproject_path.is_file() or not formatting_path.is_file():
        return False
    readme = readme_path.read_text(encoding="utf-8", errors="ignore").casefold()
    pyproject = pyproject_path.read_text(encoding="utf-8", errors="ignore")
    formatting = formatting_path.read_text(encoding="utf-8")
    required = ("## italiano", "## english", "budget", "tie-break", "python -m releaseplanner")
    relation_documented = ("depend" in readme or "dipenden" in readme) and (
        "conflict" in readme or "conflitt" in readme
    )
    return all(term in readme for term in required) and relation_documented and "dependencies = []" in pyproject and formatting == EXPECTED_FORMATTING


check("documentation_no_dependencies_scope", 5, documentation_and_scope)

score = sum(item["earned"] for item in checks)
print(json.dumps({"score": score, "max_score": 100, "checks": checks}, ensure_ascii=False))
