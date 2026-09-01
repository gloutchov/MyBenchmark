from __future__ import annotations

import json
import os
import subprocess
import sys
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


if __name__ == "__main__":
    unittest.main()
