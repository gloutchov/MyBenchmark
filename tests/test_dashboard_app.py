from __future__ import annotations

import contextlib
import io
import json
import socket
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from localagent_bench.dashboard_app import (
    DashboardAppError,
    create_dashboard_server,
    discover_run_directories,
    load_dashboard_dataset,
    main,
    render_dataset_script,
    resolve_run_directories,
    write_snapshot_script,
)
from localagent_bench.dashboard_data import validate_dashboard_data


SNAPSHOT_SOURCE = ROOT / "cases" / "results_dashboard" / "fixture" / "dashboard-data.json"


def _write_minimal_run(root: Path, name: str = "run-ok") -> Path:
    run = root / name
    run.mkdir(parents=True)
    manifest = {
        "schema_version": 3,
        "benchmark_version": "0.6.0-test",
        "profile": "smoke",
        "models": ["model-a"],
        "started_at": None,
        "finished_at": None,
        "repository": {"commit": "a" * 40},
        "sandbox": {"backend": "test", "enforced": True},
    }
    report = {
        "schema_version": 3,
        "run": {"profile": "smoke", "sandbox": manifest["sandbox"]},
        "integrity": {"status": "passed", "disqualified_models": []},
        "leaderboard": [],
        "results": [],
    }
    (run / "run.json").write_text(json.dumps(manifest), encoding="utf-8")
    (run / "report.json").write_text(json.dumps(report), encoding="utf-8")
    return run


class DashboardAppTests(unittest.TestCase):
    def setUp(self):
        self.dataset = load_dashboard_dataset(SNAPSHOT_SOURCE, root=ROOT)

    def test_snapshot_script_is_valid_and_contains_only_public_data(self):
        script = render_dataset_script(self.dataset, source="snapshot")
        decoded = script.decode("utf-8")
        self.assertTrue(decoded.startswith("window.LOCALAGENT_DASHBOARD_DATA="))
        self.assertIn('"source":"snapshot"', decoded)
        for forbidden in ("final_response", '"command"', "pi-events", "/Users/", "PRIVATE-"):
            self.assertNotIn(forbidden, decoded)

    def test_snapshot_writer_is_atomic_confined_and_requires_force(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as directory, tempfile.TemporaryDirectory() as outside:
            temp_root = Path(directory)
            output = temp_root / "data" / "snapshot.js"
            write_snapshot_script(self.dataset, output, root=temp_root)
            original = output.read_bytes()
            self.assertFalse(list(output.parent.glob(".*.tmp")))
            with self.assertRaisesRegex(DashboardAppError, "--force"):
                write_snapshot_script(self.dataset, output, root=temp_root)
            write_snapshot_script(self.dataset, output, root=temp_root, overwrite=True)
            self.assertEqual(original, output.read_bytes())
            with self.assertRaisesRegex(DashboardAppError, "root del progetto"):
                write_snapshot_script(self.dataset, Path(outside) / "snapshot.js", root=temp_root)

    def test_discovery_accepts_valid_runs_and_skips_invalid_ones(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            temp_root = Path(directory)
            results = temp_root / "results"
            results.mkdir()
            valid = _write_minimal_run(results)
            invalid = _write_minimal_run(results, "run-invalid")
            (invalid / "report.json").write_text("{}", encoding="utf-8")
            (results / "not-a-run").mkdir()

            discovered, skipped = discover_run_directories(results, root=temp_root)

            self.assertEqual([valid.resolve()], discovered)
            self.assertEqual(["run-invalid"], skipped)

    def test_explicit_runs_must_be_unique_and_inside_root(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as directory, tempfile.TemporaryDirectory() as outside:
            temp_root = Path(directory)
            run = _write_minimal_run(temp_root)
            self.assertEqual([run.resolve()], resolve_run_directories([run], root=temp_root))
            with self.assertRaisesRegex(DashboardAppError, "distinte"):
                resolve_run_directories([run, run], root=temp_root)
            outside_run = _write_minimal_run(Path(outside))
            with self.assertRaisesRegex(DashboardAppError, "root del progetto"):
                resolve_run_directories([outside_run], root=temp_root)

    def test_server_exposes_only_whitelisted_assets_and_security_headers(self):
        try:
            server = create_dashboard_server(
                dataset=self.dataset,
                assets_directory=ROOT / "dashboard",
                host="127.0.0.1",
                port=0,
                source="snapshot",
            )
        except DashboardAppError as exc:
            if "Operation not permitted" in str(exc):
                self.skipTest("bind loopback vietato dal sandbox del test")
            raise
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_address[1]}"
        try:
            with urllib.request.urlopen(base + "/", timeout=5) as response:
                self.assertEqual(200, response.status)
                self.assertIn(b"LocalAgent Benchmark", response.read())
                self.assertEqual("no-store", response.headers["Cache-Control"])
                self.assertIn("connect-src 'none'", response.headers["Content-Security-Policy"])
                self.assertEqual("nosniff", response.headers["X-Content-Type-Options"])
            with urllib.request.urlopen(base + "/data/snapshot.js", timeout=5) as response:
                payload = response.read()
                self.assertIn(b'"source":"snapshot"', payload)
                self.assertNotIn(b"final_response", payload)
            for path in ("/../benchmark.json", "/benchmark.json", "/data/snapshot.json"):
                with self.assertRaises(urllib.error.HTTPError) as error:
                    urllib.request.urlopen(base + path, timeout=5)
                self.assertEqual(404, error.exception.code)
                self.assertEqual("no-store", error.exception.headers["Cache-Control"])
                self.assertIn("connect-src 'none'", error.exception.headers["Content-Security-Policy"])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_server_rejects_non_loopback_and_occupied_port(self):
        with self.assertRaisesRegex(DashboardAppError, "127.0.0.1"):
            create_dashboard_server(
                dataset=self.dataset,
                assets_directory=ROOT / "dashboard",
                host="0.0.0.0",
                port=0,
                source="snapshot",
            )
        with socket.socket() as listener:
            try:
                listener.bind(("127.0.0.1", 0))
            except PermissionError:
                self.skipTest("bind loopback vietato dal sandbox del test")
            listener.listen(1)
            port = listener.getsockname()[1]
            with self.assertRaisesRegex(DashboardAppError, "porta dashboard"):
                create_dashboard_server(
                    dataset=self.dataset,
                    assets_directory=ROOT / "dashboard",
                    host="127.0.0.1",
                    port=port,
                    source="snapshot",
                )

    def test_committed_snapshot_source_is_valid(self):
        validate_dashboard_data(self.dataset)
        self.assertEqual(["smoke", "standard", "full"], self.dataset["profile_order"])

    def test_no_open_mode_does_not_launch_browser_or_write_sources(self):
        fake_server = mock.Mock()
        fake_server.server_address = ("127.0.0.1", 43210)
        source_before = SNAPSHOT_SOURCE.read_bytes()
        stdout = io.StringIO()
        with (
            mock.patch("localagent_bench.dashboard_app.create_dashboard_server", return_value=fake_server),
            mock.patch("localagent_bench.dashboard_app.webbrowser.open") as browser_open,
            contextlib.redirect_stdout(stdout),
        ):
            exit_code = main(
                [
                    "--config",
                    str(ROOT / "benchmark.json"),
                    "--dataset",
                    str(SNAPSHOT_SOURCE),
                    "--no-open",
                ]
            )
        self.assertEqual(0, exit_code)
        browser_open.assert_not_called()
        fake_server.serve_forever.assert_called_once_with(poll_interval=0.2)
        fake_server.server_close.assert_called_once_with()
        self.assertEqual(source_before, SNAPSHOT_SOURCE.read_bytes())
        self.assertIn("http://127.0.0.1:43210/", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
