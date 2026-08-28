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


if __name__ == "__main__":
    unittest.main()
