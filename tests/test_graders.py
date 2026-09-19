from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from localagent_bench.config import load_config


class GraderTests(unittest.TestCase):
    def test_baselines_score_below_completion_threshold(self):
        config = load_config(ROOT / "benchmark.json")
        for case in config.cases.values():
            with self.subTest(case=case.id):
                result = subprocess.run(
                    [sys.executable, str(case.grader_path), str(case.fixture_path)],
                    env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
                    capture_output=True,
                    text=True,
                    timeout=30,
                    check=True,
                )
                payload = json.loads(result.stdout)
                self.assertEqual(100, sum(item["points"] for item in payload["checks"]))
                self.assertLess(payload["score"], 60)

    def test_thinking_challenge_rejects_a_public_fixture_hardcode(self):
        case = load_config(ROOT / "benchmark.json").cases["thinking_challenge"]
        with tempfile.TemporaryDirectory() as directory:
            candidate = Path(directory) / "candidate"
            shutil.copytree(case.fixture_path, candidate)
            (candidate / "src/releaseplanner/planner.py").write_text(
                '''class PlanningError(ValueError):\n    pass\n\ndef plan_release(spec):\n    return {\n        "selected": ["auth", "foundation", "passkeys", "polish"],\n        "total_value": 28,\n        "total_cost": 10,\n        "total_risk": 4,\n        "team_usage": {"backend": 3, "mobile": 3, "data": 0},\n    }\n''',
                encoding="utf-8",
            )
            completed = subprocess.run(
                [sys.executable, str(case.grader_path), str(candidate)],
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
                capture_output=True,
                text=True,
                timeout=30,
                check=True,
            )
            payload = json.loads(completed.stdout)
            earned = {item["id"]: item["earned"] for item in payload["checks"]}
            self.assertEqual(18, earned["public_optimum"])
            self.assertEqual(0, earned["hidden_dependencies_conflicts"])
            self.assertEqual(0, earned["hidden_capacities_categories"])
            self.assertLess(payload["score"], 60)


if __name__ == "__main__":
    unittest.main()
