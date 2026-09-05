from __future__ import annotations

import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NODE = shutil.which("node")


class DashboardJavaScriptTests(unittest.TestCase):
    @unittest.skipUnless(NODE, "Node.js non disponibile")
    def test_official_dashboard_node_suite(self):
        result = subprocess.run(
            [NODE, "--test", "dashboard/tests/dashboard.test.js"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(0, result.returncode, msg=result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
