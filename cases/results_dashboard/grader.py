#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import shutil
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


def read(name: str) -> str:
    path = workspace / name
    return path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""


index = read("index.html")
javascript = read("app.js")
styles = read("styles.css")
readme = read("README.md")
node = shutil.which("node")


check(
    "required_files",
    5,
    lambda: all((workspace / name).is_file() for name in ("index.html", "styles.css", "app.js", "dashboard-data.json", "README.md")),
)
check(
    "semantic_dashboard_shell",
    7,
    lambda: all(
        token in index.casefold()
        for token in ("<main", "<section", "<h1", "<label", 'type="file"', "multiple", "aria-live", "skip-link")
    ),
)


def syntax_and_offline() -> bool:
    if not node:
        return False
    syntax = subprocess.run([node, "--check", "app.js"], cwd=workspace, capture_output=True, text=True, timeout=20)
    combined = "\n".join((index, javascript, styles)).casefold()
    remote = re.search(r"(?:https?:)?//[^\s'\"<]+|websocket|sendbeacon|xmlhttprequest", combined)
    external_assets = re.search(r"<(?:script|link)[^>]+(?:src|href)=[\"'](?!app\.js|styles\.css|#)", index, re.I)
    return syntax.returncode == 0 and remote is None and external_assets is None


check("valid_javascript_and_offline_assets", 8, syntax_and_offline)


hidden_dataset = {
    "schema_version": 1,
    "profile_order": ["standard", "full"],
    "runs": [
        {
            "id": "hidden-standard-77",
            "profile": "standard",
            "benchmark_version": "9.9.9-test",
            "started_at": None,
            "finished_at": None,
            "provenance": {"run_schema_version": 3, "report_schema_version": 3, "run_sha256": "a" * 64, "report_sha256": "b" * 64, "repository_commit": None},
            "sandbox": {"backend": "test", "enforced": True, "filesystem_isolation": True, "process_isolation": True, "network_isolation": True},
            "integrity": {"status": "passed", "disqualified_models": []},
            "participants": ["orion-hidden", "zenith-hidden"],
            "leaderboard": [
                {"rank": 1, "model": "zenith-hidden", "overall_score": 88, "quality_score": 90, "completion_rate": 100, "speed_score": 70, "token_efficiency_score": 75, "median_duration_seconds": 42, "median_output_tokens": 900, "median_cpu_seconds": None, "median_energy_joules": None, "score_stddev": 0, "successful_tasks": 1, "total_tasks": 1, "case_scores": {"unseen_case": 90}},
                {"rank": 2, "model": "orion-hidden", "overall_score": 73, "quality_score": 76, "completion_rate": 100, "speed_score": 55, "token_efficiency_score": 60, "median_duration_seconds": 75, "median_output_tokens": 1300, "median_cpu_seconds": 12, "median_energy_joules": None, "score_stddev": 0, "successful_tasks": 1, "total_tasks": 1, "case_scores": {"unseen_case": 76}},
            ],
            "tasks": [
                {"model": "orion-hidden", "case_id": "unseen_case", "case_title": "Caso nascosto", "case_title_en": "Hidden case", "category": "alternate", "repetition": 1, "status": "ok", "state": "passed", "score": 76, "max_score": 100, "duration_seconds": 75, "output_tokens": 1300, "tool_calls": 4, "tool_errors": 0, "cpu_seconds": 12, "energy_joules": None, "integrity_valid": True}
            ],
        },
        {
            "id": "hidden-full-77",
            "profile": "full",
            "benchmark_version": "9.9.9-test",
            "started_at": None,
            "finished_at": None,
            "provenance": {"run_schema_version": 3, "report_schema_version": 3, "run_sha256": "c" * 64, "report_sha256": "d" * 64, "repository_commit": None},
            "sandbox": {"backend": "test", "enforced": True, "filesystem_isolation": True, "process_isolation": True, "network_isolation": True},
            "integrity": {"status": "passed", "disqualified_models": []},
            "participants": ["zenith-hidden"],
            "leaderboard": [
                {"rank": 1, "model": "zenith-hidden", "overall_score": 91, "quality_score": 92, "completion_rate": 100, "speed_score": 80, "token_efficiency_score": 82, "median_duration_seconds": 50, "median_output_tokens": 1000, "median_cpu_seconds": None, "median_energy_joules": None, "score_stddev": 0, "successful_tasks": 1, "total_tasks": 1, "case_scores": {"another_case": 92}}
            ],
            "tasks": [],
        },
    ],
    "funnel": [
        {"profile": "standard", "run_ids": ["hidden-standard-77"], "participants": ["orion-hidden", "zenith-hidden"], "new_participants": ["orion-hidden", "zenith-hidden"], "next_profile": "full", "continued_to_next": ["zenith-hidden"], "not_run_in_next": ["orion-hidden"]},
        {"profile": "full", "run_ids": ["hidden-full-77"], "participants": ["zenith-hidden"], "new_participants": [], "next_profile": None, "continued_to_next": [], "not_run_in_next": []},
    ],
}


def node_probe() -> dict:
    if not node:
        return {}
    harness = r'''
const fs = require("node:fs");
const app = require(process.argv[1]);
const data = JSON.parse(fs.readFileSync(0, "utf8"));
let invalidRejected = false;
try { app.validateDashboardData({schema_version: 999, profile_order: [], runs: [], funnel: []}); }
catch (_) { invalidRejected = true; }
const valid = app.validateDashboardData(data) === true;
const view = app.createDashboardView(data, {profile: "standard", sortBy: "overall_score", sortDirection: "desc"});
const filtered = app.createDashboardView(data, {profile: "standard", model: "orion-hidden", sortBy: "median_duration_seconds", sortDirection: "asc"});
const first = {schema_version: 1, profile_order: ["standard"], runs: [data.runs[0]], funnel: [data.funnel[0]]};
const second = {schema_version: 1, profile_order: ["full"], runs: [data.runs[1]], funnel: [data.funnel[1]]};
const merged = app.mergeDashboardData([first, second]);
console.log(JSON.stringify({valid, invalidRejected, view, filtered, merged}));
'''
    result = subprocess.run(
        [node, "-e", harness, str(workspace / "app.js")],
        input=json.dumps(hidden_dataset),
        cwd=workspace,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        return {}
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


probe = node_probe()
check("public_api_and_validation", 12, lambda: probe.get("valid") is True and probe.get("invalidRejected") is True)


def generalized_view() -> bool:
    view = probe.get("view", {})
    if not isinstance(view, dict):
        return False
    models = set(view.get("availableModels", []))
    leaderboard = view.get("leaderboard", [])
    tasks = view.get("tasks", [])
    return (
        set(view.get("profiles", [])) >= {"standard", "full"}
        and models >= {"orion-hidden", "zenith-hidden"}
        and [row.get("model") for row in leaderboard[:2]] == ["zenith-hidden", "orion-hidden"]
        and any(task.get("case_id") == "unseen_case" for task in tasks)
    )


check("alternate_dataset_generality", 18, generalized_view)


def merged_dataset() -> bool:
    merged = probe.get("merged", {})
    return (
        isinstance(merged, dict)
        and [run.get("id") for run in merged.get("runs", [])] == ["hidden-standard-77", "hidden-full-77"]
        and merged.get("profile_order") == ["standard", "full"]
        and [stage.get("profile") for stage in merged.get("funnel", [])] == ["standard", "full"]
        and merged.get("funnel", [{}])[0].get("not_run_in_next") == ["orion-hidden"]
    )


check("multi_dataset_merge_and_funnel_rebuild", 10, merged_dataset)


def funnel_semantics() -> bool:
    view = probe.get("view", {})
    stages = view.get("funnel", []) if isinstance(view, dict) else []
    standard = next((stage for stage in stages if stage.get("profile") == "standard"), {})
    source = "\n".join((index, javascript)).casefold()
    neutral_copy = any(term in source for term in ("not run", "not_run_in_next", "non eseguit"))
    return standard.get("continued_to_next") == ["zenith-hidden"] and standard.get("not_run_in_next") == ["orion-hidden"] and neutral_copy


check("funnel_progression_without_failure_inference", 10, funnel_semantics)


def filtering_sorting_and_details() -> bool:
    filtered = probe.get("filtered", {})
    if not isinstance(filtered, dict):
        return False
    return (
        [row.get("model") for row in filtered.get("leaderboard", [])] == ["orion-hidden"]
        and all(task.get("model") == "orion-hidden" for task in filtered.get("tasks", []))
        and all(token in javascript for token in ("sortBy", "sortDirection", "addEventListener"))
        and any(token in index.casefold() + javascript.casefold() for token in ("dialog", "details", "task-detail"))
    )


check("filters_sorting_and_task_details", 10, filtering_sorting_and_details)


def preferences_and_i18n() -> bool:
    source = "\n".join((index, javascript, styles)).casefold()
    return all(
        token in source
        for token in ("localstorage", "matchmedia", "prefers-color-scheme", "navigator.language", "auto", "italiano", "english")
    ) and ("strings" in javascript.casefold() or "translations" in javascript.casefold())


check("persistent_language_and_theme", 8, preferences_and_i18n)


def responsive_and_accessible() -> bool:
    combined = index.casefold() + "\n" + styles.casefold()
    return all(token in combined for token in ("@media", ":focus-visible", "overflow-x", "aria-live", "skip-link", "<label"))


check("responsive_and_accessible_states", 6, responsive_and_accessible)


def candidate_tests() -> bool:
    if not node or not (workspace / "tests" / "dashboard.test.js").is_file():
        return False
    result = subprocess.run(
        [node, "--test", "tests/dashboard.test.js"],
        cwd=workspace,
        env={**os.environ, "NO_COLOR": "1"},
        capture_output=True,
        text=True,
        timeout=30,
    )
    tests = read("tests/dashboard.test.js").casefold()
    return result.returncode == 0 and all(term in tests for term in ("merge", "invalid", "filter"))


check("candidate_tests", 3, candidate_tests)
check(
    "usage_privacy_and_test_documentation",
    3,
    lambda: all(term in readme.casefold() for term in ("python3 -m http.server", "import", "offline", "privacy", "test")),
)

score = round(sum(item["earned"] for item in checks), 2)
print(json.dumps({"score": score, "max_score": 100, "checks": checks}, ensure_ascii=False))
