from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from localagent_bench.config import load_config
from localagent_bench.runner import _capture_git, _git, _prepare_workspace


class RunnerGitTests(unittest.TestCase):
    def test_diff_includes_committed_and_untracked_changes(self):
        config = load_config(ROOT / "benchmark.json")
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            workspace = Path(directory) / "workspace"
            baseline = _prepare_workspace(config, config.cases["targeted_patch"], workspace)
            readme = workspace / "README.md"
            readme.write_text(readme.read_text(encoding="utf-8") + "\ncommitted marker\n", encoding="utf-8")
            _git(workspace, "add", "README.md")
            _git(workspace, "commit", "-q", "-m", "candidate commit")
            (workspace / "NEW.md").write_text("untracked marker\n", encoding="utf-8")
            _, diff, _ = _capture_git(workspace, baseline)
            self.assertIn("committed marker", diff)
            self.assertIn("untracked marker", diff)


if __name__ == "__main__":
    unittest.main()
