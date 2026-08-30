from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from localagent_bench.system_metrics import SystemMetricCollector, hardware_snapshot


class SystemMetricTests(unittest.TestCase):
    def test_hardware_snapshot_is_structured_and_dependency_free(self):
        snapshot = hardware_snapshot()
        self.assertIn("logical_cpu_count", snapshot)
        self.assertIn("memory_total_bytes", snapshot)
        self.assertIn("energy", snapshot)
        self.assertIsInstance(snapshot["energy"]["available"], bool)

    def test_task_collector_reports_availability_explicitly(self):
        collector = SystemMetricCollector.start()
        sum(index * index for index in range(1000))
        metrics = collector.finish()
        self.assertEqual(1, metrics["schema_version"])
        self.assertIn("available", metrics["process"])
        self.assertIn("available", metrics["energy"])
        self.assertIn("before", metrics["system_load_average"])


if __name__ == "__main__":
    unittest.main()
