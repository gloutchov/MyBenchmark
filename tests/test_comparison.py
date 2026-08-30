from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from localagent_bench.comparison import ComparisonError, write_comparison


class ComparisonTests(unittest.TestCase):
    def _write_run(
        self,
        root: Path,
        name: str,
        *,
        overall: float,
        fingerprint: str = "same-input",
        sandbox_backend: str = "audit-only",
        digest: str = "digest-a",
        max_tokens: int = 8192,
    ) -> Path:
        run_dir = root / name
        run_dir.mkdir()
        manifest = {
            "profile": "full",
            "cases": ["case"],
            "inputs": {"cases": {"case": {"effective_input_sha256": fingerprint}}},
            "sandbox": {"backend": sandbox_backend, "enforced": sandbox_backend != "audit-only"},
            "configuration": {
                "timeout_seconds": 30,
                "repetitions": 1,
                "thinking": "off",
                "warmup": False,
                "context_window": 32768,
                "max_tokens": max_tokens,
                "temperature": 0,
            },
            "model_metadata": {"model:a": {"digest": digest}},
            "environment": {
                "platform": "test-os",
                "hardware": {"machine": "test-cpu", "logical_cpu_count": 8},
            },
        }
        report = {
            "schema_version": 3,
            "integrity": {"audit_version": 3, "disqualified_models": []},
            "leaderboard": [
                {
                    "model": "model:a",
                    "overall_score": overall,
                    "quality_score": overall,
                    "completion_rate": 100,
                    "speed_score": 100,
                    "token_efficiency_score": 100,
                    "median_duration_seconds": 10,
                    "median_output_tokens": 100,
                    "median_cpu_seconds": 2,
                    "median_energy_joules": None,
                }
            ],
            "results": [],
        }
        (run_dir / "run.json").write_text(json.dumps(manifest), encoding="utf-8")
        (run_dir / "report.json").write_text(json.dumps(report), encoding="utf-8")
        return run_dir

    def test_aggregates_compatible_runs_with_dispersion(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = self._write_run(root, "first", overall=80)
            second = self._write_run(root, "second", overall=90)
            output = root / "comparison"
            comparison = write_comparison([first, second], output)
            overall = comparison["models"][0]["metrics"]["overall_score"]
            self.assertEqual(2, overall["count"])
            self.assertEqual(85, overall["mean"])
            self.assertGreater(overall["stddev"], 0)
            self.assertTrue((output / "COMPARISON.md").is_file())
            self.assertEqual("digest-a", comparison["models"][0]["model_digest"])

    def test_rejects_duplicate_runs_and_changed_model_digest(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = self._write_run(root, "first", overall=80)
            with self.assertRaisesRegex(ComparisonError, "una sola volta"):
                write_comparison([first, first], root / "duplicate")
            changed = self._write_run(root, "changed", overall=80, digest="digest-b")
            with self.assertRaisesRegex(ComparisonError, "Digest Ollama divergente"):
                write_comparison([first, changed], root / "changed-digest")

    def test_rejects_different_inputs_or_sandbox_backends(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = self._write_run(root, "first", overall=80)
            changed = self._write_run(root, "changed", overall=80, fingerprint="changed")
            with self.assertRaisesRegex(ComparisonError, "inputs"):
                write_comparison([first, changed], root / "bad-input")

            backend = self._write_run(root, "backend", overall=80, sandbox_backend="macos-seatbelt")
            with self.assertRaisesRegex(ComparisonError, "sandbox_backend"):
                write_comparison([first, backend], root / "bad-backend")

            configuration = self._write_run(root, "configuration", overall=80, max_tokens=4096)
            with self.assertRaisesRegex(ComparisonError, "max_tokens"):
                write_comparison([first, configuration], root / "bad-configuration")


if __name__ == "__main__":
    unittest.main()
