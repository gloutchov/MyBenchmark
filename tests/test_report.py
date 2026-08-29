from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from localagent_bench.report import write_report


class ReportTests(unittest.TestCase):
    def test_report_ranks_quality_first(self):
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory)
            for model, score, duration, tokens in (("accurate", 90, 20, 200), ("fast", 60, 5, 50)):
                case_dir = run_dir / "models" / model / "cases" / "case-r1"
                case_dir.mkdir(parents=True)
                result = {
                    "model": model,
                    "case_id": "case",
                    "case_weight": 1,
                    "repetition": 1,
                    "status": "ok",
                    "duration_seconds": duration,
                    "metrics": {"usage": {"output": tokens}, "tool_calls": 1, "tool_errors": 0},
                    "grade": {"score": score},
                }
                (case_dir / "result.json").write_text(json.dumps(result), encoding="utf-8")
            report = write_report(run_dir)
            self.assertEqual("accurate", report["leaderboard"][0]["model"])
            self.assertEqual(90, report["leaderboard"][0]["case_scores"]["case"])
            self.assertTrue((run_dir / "REPORT.md").exists())

    def test_integrity_violation_disqualifies_entire_model(self):
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory)
            tasks = [
                {"model": model, "case_id": case, "repetition": 1}
                for model in ("clean", "escaped")
                for case in ("one", "two")
            ]
            (run_dir / "run.json").write_text(
                json.dumps(
                    {
                        "task_order": tasks,
                        "integrity": {"status": "violations_detected", "violations": []},
                    }
                ),
                encoding="utf-8",
            )
            for model in ("clean", "escaped"):
                for case in ("one", "two"):
                    case_dir = run_dir / "models" / model / "cases" / f"{case}-r1"
                    case_dir.mkdir(parents=True)
                    valid = not (model == "escaped" and case == "one")
                    result = {
                        "model": model,
                        "case_id": case,
                        "case_weight": 1,
                        "repetition": 1,
                        "status": "ok",
                        "duration_seconds": 10,
                        "metrics": {"usage": {"output": 10}},
                        "grade": {"score": 90},
                        "baseline_tree": f"tree-{case}",
                        "input_fingerprint": f"input-{case}",
                        "integrity": {"valid_for_ranking": valid},
                    }
                    (case_dir / "result.json").write_text(json.dumps(result), encoding="utf-8")
            report = write_report(run_dir)
            self.assertEqual(["clean"], [row["model"] for row in report["leaderboard"]])
            self.assertEqual(["escaped"], report["integrity"]["disqualified_models"])
            self.assertIn("Modelli esclusi dalla classifica: `escaped`", (run_dir / "REPORT.md").read_text(encoding="utf-8"))

    def test_minority_baseline_is_excluded(self):
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory)
            models = ("first", "second", "contaminated")
            (run_dir / "run.json").write_text(
                json.dumps(
                    {
                        "task_order": [
                            {"model": model, "case_id": "case", "repetition": 1} for model in models
                        ],
                        "integrity": {"status": "passed", "violations": []},
                    }
                ),
                encoding="utf-8",
            )
            for model in models:
                case_dir = run_dir / "models" / model / "cases" / "case-r1"
                case_dir.mkdir(parents=True)
                result = {
                    "model": model,
                    "case_id": "case",
                    "case_weight": 1,
                    "repetition": 1,
                    "status": "ok",
                    "duration_seconds": 10,
                    "metrics": {"usage": {"output": 10}},
                    "grade": {"score": 90},
                    "baseline_tree": "different" if model == "contaminated" else "expected",
                    "integrity": {"valid_for_ranking": True},
                }
                (case_dir / "result.json").write_text(json.dumps(result), encoding="utf-8")
            report = write_report(run_dir)
            self.assertEqual(["contaminated"], report["integrity"]["disqualified_models"])
            self.assertEqual(["case"], report["integrity"]["baseline_mismatches"])
            self.assertEqual({"first", "second"}, {row["model"] for row in report["leaderboard"]})


if __name__ == "__main__":
    unittest.main()
