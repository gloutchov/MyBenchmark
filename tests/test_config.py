from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from localagent_bench.config import ConfigError, load_config


class ConfigTests(unittest.TestCase):
    def test_repository_config_is_valid(self):
        config = load_config(ROOT / "benchmark.json")
        self.assertEqual("installed", config.models)
        self.assertEqual(4, len(config.cases))
        self.assertEqual(("targeted_patch",), config.profiles["smoke"])
        self.assertEqual("audit", config.defaults.sandbox)

    def test_missing_case_is_rejected(self):
        source = (ROOT / "benchmark.json").read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            path = Path(directory) / "benchmark.json"
            path.write_text(source, encoding="utf-8")
            with self.assertRaises(ConfigError):
                load_config(path)


if __name__ == "__main__":
    unittest.main()
