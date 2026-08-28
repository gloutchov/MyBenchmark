from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class GraderTests(unittest.TestCase):
    def test_baselines_score_below_completion_threshold(self):
        for case in ("targeted_patch", "secure_workspace", "config_i18n", "milestone_closure"):
            with self.subTest(case=case):
                result = subprocess.run(
                    [sys.executable, str(ROOT / "cases" / case / "grader.py"), str(ROOT / "cases" / case / "fixture")],
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
