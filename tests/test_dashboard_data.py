from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from localagent_bench.cli import main
from localagent_bench.dashboard_data import (
    DashboardDataError,
    build_dashboard_data,
    validate_dashboard_data,
    write_dashboard_data,
)


def leaderboard_row(model: str, score: float) -> dict:
    return {
        "model": model,
        "overall_score": score,
        "quality_score": score + 1,
        "completion_rate": 100,
        "speed_score": 75,
        "token_efficiency_score": 80,
        "median_duration_seconds": 12.5,
        "median_output_tokens": 500,
        "median_cpu_seconds": None,
        "median_energy_joules": None,
        "score_stddev": 0,
        "successful_tasks": 1,
        "total_tasks": 1,
        "case_scores": {"synthetic_case": score + 1},
        "raw_path": "/Users/private/ignored",
    }


def result_row(model: str, *, state: str = "ok", valid: bool = True) -> dict:
    return {
        "model": model,
        "case_id": "synthetic_case",
        "case_title": "Caso sintetico",
        "case_title_en": "Synthetic case",
        "case_category": "test",
        "repetition": 1,
        "status": state,
        "duration_seconds": 9.5,
        "metrics": {"usage": {"output": 321, "input": 999}, "tool_calls": 3, "tool_errors": 0},
        "system_metrics": {
            "process": {"available": True, "user_seconds": 1.2, "system_seconds": 0.3},
            "energy": {"available": False, "provider": "secret-provider"},
        },
        "grade": {"score": 87, "max_score": 100, "error": "PRIVATE-GRADE-DETAIL"},
        "integrity": {"valid_for_ranking": valid, "external_accesses": ["/Users/private/file"]},
        "command": ["pi", "--secret"],
        "final_response": "PRIVATE-RESPONSE",
    }


def write_run(root: Path, name: str, profile: str, models: list[str]) -> Path:
    run = root / name
    run.mkdir(parents=True)
    manifest = {
        "schema_version": 3,
        "benchmark_version": "0.5.0-test",
        "profile": profile,
        "models": models,
        "started_at": "2026-09-01T10:00:00+00:00",
        "finished_at": "2026-09-01T10:01:00+00:00",
        "repository": {"commit": "a" * 40, "dirty_paths": ["/Users/private/source"]},
        "sandbox": {
            "backend": "test-sandbox",
            "enforced": True,
            "filesystem_isolation": True,
            "process_isolation": True,
            "network_isolation": True,
        },
        "prompt": "PRIVATE-PROMPT",
    }
    results = [result_row(model, valid=model != "excluded-model") for model in models]
    ranked = [model for model in models if model != "excluded-model"]
    report = {
        "schema_version": 3,
        "run": {"profile": profile, "sandbox": manifest["sandbox"]},
        "integrity": {
            "status": "violations_detected" if "excluded-model" in models else "passed",
            "disqualified_models": ["excluded-model"] if "excluded-model" in models else [],
            "violations": [{"target": "/Users/private/file", "evidence": "PRIVATE-EVIDENCE"}],
        },
        "leaderboard": [leaderboard_row(model, 90 - index) for index, model in enumerate(ranked)],
        "results": results,
        "raw_log": "PRIVATE-LOG",
    }
    (run / "run.json").write_text(json.dumps(manifest), encoding="utf-8")
    (run / "report.json").write_text(json.dumps(report), encoding="utf-8")
    return run


class DashboardDataTests(unittest.TestCase):
    def test_export_whitelists_fields_and_builds_neutral_funnel(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            smoke = write_run(root, "smoke-run", "smoke", ["alpha", "beta", "excluded-model"])
            standard = write_run(root, "standard-run", "standard", ["alpha"])
            full = write_run(root, "full-run", "full", ["alpha", "new-finalist"])

            dataset = build_dashboard_data([full, smoke, standard])

            self.assertEqual(["smoke", "standard", "full"], dataset["profile_order"])
            self.assertEqual(["smoke-run", "standard-run", "full-run"], [run["id"] for run in dataset["runs"]])
            smoke_stage = dataset["funnel"][0]
            self.assertEqual(["alpha"], smoke_stage["continued_to_next"])
            self.assertEqual(["beta", "excluded-model"], smoke_stage["not_run_in_next"])
            self.assertEqual(["new-finalist"], dataset["funnel"][2]["new_participants"])
            self.assertEqual("integrity_excluded", dataset["runs"][0]["tasks"][2]["state"])
            serialized = json.dumps(dataset)
            for forbidden in (
                "PRIVATE-PROMPT",
                "PRIVATE-RESPONSE",
                "PRIVATE-GRADE-DETAIL",
                "PRIVATE-EVIDENCE",
                "PRIVATE-LOG",
                "/Users/private",
                '"command"',
            ):
                self.assertNotIn(forbidden, serialized)
            validate_dashboard_data(dataset)

    def test_rejects_duplicate_sources_schema_mismatch_and_profile_mismatch(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run = write_run(root, "run", "smoke", ["alpha"])
            with self.assertRaisesRegex(DashboardDataError, "distinte"):
                build_dashboard_data([run, run])
            report_path = run / "report.json"
            report = json.loads(report_path.read_text(encoding="utf-8"))
            report["schema_version"] = 99
            report_path.write_text(json.dumps(report), encoding="utf-8")
            with self.assertRaisesRegex(DashboardDataError, "Schema report"):
                build_dashboard_data([run])
            report["schema_version"] = 3
            report["run"]["profile"] = "full"
            report_path.write_text(json.dumps(report), encoding="utf-8")
            with self.assertRaisesRegex(DashboardDataError, "Profilo incoerente"):
                build_dashboard_data([run])

    def test_rejects_symlinked_source_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run = write_run(root, "run", "smoke", ["alpha"])
            actual = root / "outside-report.json"
            report_path = run / "report.json"
            report_path.replace(actual)
            try:
                report_path.symlink_to(actual)
            except OSError as exc:
                self.skipTest(f"symlink non disponibile: {exc}")
            with self.assertRaisesRegex(DashboardDataError, "symlink"):
                build_dashboard_data([run])

    def test_atomic_writer_confines_paths_refuses_overwrite_and_preserves_sources(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as outside:
            root = Path(directory)
            run = write_run(root, "run", "smoke", ["alpha"])
            original_run = (run / "run.json").read_bytes()
            original_report = (run / "report.json").read_bytes()
            output = root / "exports" / "dashboard-data.json"

            payload = write_dashboard_data([run], output, workspace_root=root)

            self.assertEqual(payload, json.loads(output.read_text(encoding="utf-8")))
            self.assertEqual(original_run, (run / "run.json").read_bytes())
            self.assertEqual(original_report, (run / "report.json").read_bytes())
            self.assertFalse(list(output.parent.glob(".*.tmp")))
            with self.assertRaisesRegex(DashboardDataError, "--force"):
                write_dashboard_data([run], output, workspace_root=root)
            write_dashboard_data([run], output, workspace_root=root, overwrite=True)
            with self.assertRaisesRegex(DashboardDataError, "directory sorgente"):
                write_dashboard_data([run], run / "dashboard-data.json", workspace_root=root)
            with self.assertRaisesRegex(DashboardDataError, "root del progetto"):
                write_dashboard_data([run], Path(outside) / "dashboard-data.json", workspace_root=root)

    def test_cli_generates_dataset_from_synthetic_runs(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            temp_root = Path(directory)
            smoke = write_run(temp_root, "smoke-cli", "smoke", ["alpha"])
            output = temp_root / "dashboard-data.json"
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                exit_code = main(
                    [
                        "--config",
                        str(ROOT / "benchmark.json"),
                        "dashboard-data",
                        str(smoke),
                        "--output",
                        str(output),
                    ]
                )
            self.assertEqual(0, exit_code)
            self.assertTrue(output.is_file())
            self.assertIn("Run esportati: 1", stdout.getvalue())

    def test_public_schema_and_synthetic_fixture_match_version(self):
        schema = json.loads((ROOT / "schemas" / "dashboard-data.schema.json").read_text(encoding="utf-8"))
        fixture = json.loads(
            (ROOT / "cases" / "results_dashboard" / "fixture" / "dashboard-data.json").read_text(encoding="utf-8")
        )
        self.assertEqual(1, schema["properties"]["schema_version"]["const"])
        validate_dashboard_data(fixture)
        self.assertEqual(["smoke", "standard", "full"], fixture["profile_order"])

    def test_public_validator_rejects_nested_non_whitelisted_fields(self):
        fixture = json.loads(
            (ROOT / "cases" / "results_dashboard" / "fixture" / "dashboard-data.json").read_text(encoding="utf-8")
        )
        fixture["runs"][0]["tasks"][0]["final_response"] = "PRIVATE-RESPONSE"
        with self.assertRaisesRegex(DashboardDataError, "Campi non validi"):
            validate_dashboard_data(fixture)
        fixture = json.loads(
            (ROOT / "cases" / "results_dashboard" / "fixture" / "dashboard-data.json").read_text(encoding="utf-8")
        )
        fixture["runs"][0]["tasks"][0]["state"] = "mystery"
        with self.assertRaisesRegex(DashboardDataError, "Task non valida"):
            validate_dashboard_data(fixture)


if __name__ == "__main__":
    unittest.main()
