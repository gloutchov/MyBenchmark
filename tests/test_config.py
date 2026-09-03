from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from localagent_bench.config import ConfigError, load_config


class ConfigTests(unittest.TestCase):
    def test_repository_config_discovers_case_manifests(self):
        config = load_config(ROOT / "benchmark.json")
        self.assertEqual("installed", config.models)
        self.assertEqual(5, len(config.cases))
        self.assertEqual(("targeted_patch",), config.profiles["smoke"])
        self.assertEqual("audit", config.defaults.sandbox)
        self.assertEqual((ROOT / "cases").resolve(), config.cases_directory)
        self.assertEqual(
            "Targeted patch with regressions and documentation",
            config.cases["targeted_patch"].title_en,
        )
        self.assertEqual(
            ROOT / "cases" / "targeted_patch" / "case.json",
            config.cases["targeted_patch"].manifest_path,
        )
        self.assertEqual(20, config.cases["milestone_closure"].manual_rubric_max_score)
        self.assertEqual(("results_dashboard",), config.profiles["showcase"])
        self.assertEqual(20, config.cases["results_dashboard"].manual_rubric_max_score)

    def test_unknown_profile_case_is_rejected(self):
        raw = json.loads((ROOT / "benchmark.json").read_text(encoding="utf-8"))
        raw["cases"] = [
            {
                "id": "targeted_patch",
                "title": "Legacy case",
                "category": "test",
                "weight": 1,
            }
        ]
        raw["profiles"] = {"standard": ["targeted_patch", "missing"]}
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            path = Path(directory) / "benchmark.json"
            fixture = path.parent / "cases" / "targeted_patch" / "fixture"
            fixture.mkdir(parents=True)
            (fixture.parent / "prompt.md").write_text("prompt\n", encoding="utf-8")
            (fixture.parent / "grader.py").write_text("print('{}')\n", encoding="utf-8")
            path.write_text(json.dumps(raw), encoding="utf-8")
            with self.assertRaisesRegex(ConfigError, "Casi sconosciuti"):
                load_config(path)

    def test_legacy_inline_case_configuration_remains_readable(self):
        raw = json.loads((ROOT / "benchmark.json").read_text(encoding="utf-8"))
        raw["cases"] = [
            {"id": "legacy", "title": "Caso legacy", "category": "compatibility", "weight": 2}
        ]
        raw["profiles"] = {"standard": ["legacy"]}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = root / "cases" / "legacy" / "fixture"
            fixture.mkdir(parents=True)
            (fixture.parent / "prompt.md").write_text("prompt\n", encoding="utf-8")
            (fixture.parent / "grader.py").write_text("print('{}')\n", encoding="utf-8")
            path = root / "benchmark.json"
            path.write_text(json.dumps(raw), encoding="utf-8")
            config = load_config(path)
            self.assertEqual(2, config.cases["legacy"].weight)
            self.assertIsNone(config.cases["legacy"].manifest_path)

    def test_cases_directory_cannot_escape_repository(self):
        raw = json.loads((ROOT / "benchmark.json").read_text(encoding="utf-8"))
        raw["cases"] = {"directory": "../cases"}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "benchmark.json"
            path.write_text(json.dumps(raw), encoding="utf-8")
            with self.assertRaisesRegex(ConfigError, "dentro il repository"):
                load_config(path)


if __name__ == "__main__":
    unittest.main()
