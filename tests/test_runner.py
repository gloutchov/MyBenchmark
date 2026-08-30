from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from localagent_bench.config import CaseSpec, load_config
from localagent_bench.integrity import (
    InputIntegrityError,
    fingerprint_tree,
    require_clean_inputs,
    snapshot_cases,
    verify_snapshot,
)
from localagent_bench.ollama import OllamaModel
from localagent_bench.pi_adapter import AUDIT_VERSION, SCRATCH_DIRECTORY, PiRun
from localagent_bench.runner import (
    EXECUTION_POLICY,
    _build_task_order,
    _capture_git,
    _git,
    _prepare_workspace,
    run_benchmark,
)


class RunnerGitTests(unittest.TestCase):
    def test_diff_includes_committed_and_untracked_changes(self):
        config = load_config(ROOT / "benchmark.json")
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            workspace = Path(directory) / "workspace"
            baseline = _prepare_workspace(config, config.cases["targeted_patch"], workspace)
            self.assertTrue((workspace / SCRATCH_DIRECTORY).is_dir())
            self.assertNotIn(SCRATCH_DIRECTORY, _git(workspace, "status", "--short").stdout)
            readme = workspace / "README.md"
            readme.write_text(readme.read_text(encoding="utf-8") + "\ncommitted marker\n", encoding="utf-8")
            _git(workspace, "add", "README.md")
            _git(workspace, "commit", "-q", "-m", "candidate commit")
            (workspace / "NEW.md").write_text("untracked marker\n", encoding="utf-8")
            _, diff, _ = _capture_git(workspace, baseline)
            self.assertIn("committed marker", diff)
            self.assertIn("untracked marker", diff)

    def test_snapshot_is_stable_and_detects_changes(self):
        config = load_config(ROOT / "benchmark.json")
        case = config.cases["targeted_patch"]
        with tempfile.TemporaryDirectory() as directory:
            context = Path(directory) / "context"
            snapshots, manifest = snapshot_cases(
                [case],
                context,
                ROOT / "AGENTS.md",
                ROOT / ".gitignore",
                EXECUTION_POLICY,
            )
            self.assertEqual(
                manifest["cases"]["targeted_patch"]["fixture_sha256"],
                fingerprint_tree(snapshots[0].fixture_path),
            )
            self.assertFalse(any(path.name == "__pycache__" for path in snapshots[0].fixture_path.rglob("*")))
            self.assertTrue((context / "EXECUTION_POLICY.snapshot.md").is_file())
            self.assertTrue(manifest["cases"]["targeted_patch"]["effective_input_sha256"])
            self.assertEqual([], verify_snapshot(context, manifest))
            baseline_trees = []
            for name in ("first", "second"):
                workspace = Path(directory) / name
                baseline = _prepare_workspace(
                    config,
                    snapshots[0],
                    workspace,
                    context / "AGENTS.snapshot.md",
                    context / ".gitignore.snapshot",
                )
                baseline_trees.append(_git(workspace, "rev-parse", f"{baseline}^{{tree}}").stdout.strip())
            self.assertEqual(baseline_trees[0], baseline_trees[1])
            prompt = snapshots[0].prompt_path
            prompt.write_text(prompt.read_text(encoding="utf-8") + "\nchanged\n", encoding="utf-8")
            self.assertIn("cases/targeted_patch/prompt.md", verify_snapshot(context, manifest))

    def test_milestone_fixture_provides_required_license(self):
        config = load_config(ROOT / "benchmark.json")
        case = config.cases["milestone_closure"]
        self.assertTrue((case.fixture_path / "LICENSE").is_file())
        self.assertIn("Apache License", (case.fixture_path / "LICENSE").read_text(encoding="utf-8"))

    def test_task_order_is_seeded_and_complete(self):
        config = load_config(ROOT / "benchmark.json")
        cases = [config.cases["targeted_patch"], config.cases["secure_workspace"]]
        first = _build_task_order(["a", "b"], cases, 2, 42)
        second = _build_task_order(["a", "b"], cases, 2, 42)
        self.assertEqual(first, second)
        self.assertEqual(8, len(first))
        self.assertEqual(
            {("a", "targeted_patch", 1), ("a", "targeted_patch", 2),
             ("a", "secure_workspace", 1), ("a", "secure_workspace", 2),
             ("b", "targeted_patch", 1), ("b", "targeted_patch", 2),
             ("b", "secure_workspace", 1), ("b", "secure_workspace", 2)},
            {(item["model"], item["case_id"], item["repetition"]) for item in first},
        )

    @patch("localagent_bench.runner._command_version", return_value="test")
    @patch("localagent_bench.runner.require_clean_inputs")
    @patch("localagent_bench.runner.unload")
    @patch("localagent_bench.runner.version", return_value="test")
    @patch("localagent_bench.runner.run_pi")
    @patch("localagent_bench.runner.list_models")
    def test_run_uses_frozen_inputs_and_records_integrity(
        self,
        list_models_mock,
        run_pi_mock,
        _version_mock,
        _unload_mock,
        _require_clean_inputs_mock,
        _command_version_mock,
    ):
        model = OllamaModel("model:a", 1, "digest", "now", {})
        list_models_mock.return_value = [model]
        run_pi_mock.return_value = PiRun(
            status="ok",
            exit_code=0,
            duration_seconds=1.0,
            stdout="",
            stderr="",
            metrics={"usage": {"output": 1}, "tool_calls": 0, "tool_errors": 0},
            final_response="done",
            command=["pi"],
            sandbox={"backend": "audit-only", "enforced": False},
            system_metrics={
                "process": {"available": True, "user_seconds": 0.2, "system_seconds": 0.1},
                "energy": {"available": False},
            },
        )
        config = load_config(ROOT / "benchmark.json")
        with tempfile.TemporaryDirectory() as directory:
            run_dir = run_benchmark(
                config,
                profile="smoke",
                requested_models=["model:a"],
                requested_cases=None,
                repetitions=1,
                timeout_seconds=30,
                use_warmup=False,
                output_dir=Path(directory) / "run",
                order_seed=7,
            )
            result_path = next(run_dir.glob("models/*/cases/*/result.json"))
            result = json.loads(result_path.read_text(encoding="utf-8"))
            report = json.loads((run_dir / "report.json").read_text(encoding="utf-8"))
            self.assertTrue(result["integrity"]["valid_for_ranking"])
            self.assertEqual(AUDIT_VERSION, result["integrity"]["audit_version"])
            self.assertTrue(result["baseline_tree"])
            self.assertEqual("passed", report["integrity"]["status"])
            manifest = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
            self.assertEqual(7, manifest["order_seed"])
            self.assertEqual(AUDIT_VERSION, manifest["execution_policy"]["audit_version"])
            self.assertEqual("audit-only", manifest["sandbox"]["backend"])
            self.assertFalse(manifest["sandbox"]["enforced"])
            self.assertEqual(3, result["schema_version"])
            self.assertTrue(result["system_metrics"]["process"]["available"])
            self.assertIn("hardware", manifest["environment"])
            self.assertIn("Non accedere alla rete", run_pi_mock.call_args.args[3])
            self.assertTrue((result_path.parent / "workspace" / SCRATCH_DIRECTORY).is_dir())
            self.assertTrue((result_path.parent / ".pi-agent" / "models.json").is_file())

    def test_preflight_rejects_dirty_case_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            case_root = root / "cases" / "example"
            fixture = case_root / "fixture"
            fixture.mkdir(parents=True)
            (root / "AGENTS.md").write_text("rules\n", encoding="utf-8")
            (root / ".gitignore").write_text("results/\n", encoding="utf-8")
            (case_root / "prompt.md").write_text("prompt\n", encoding="utf-8")
            (case_root / "grader.py").write_text("print('{}')\n", encoding="utf-8")
            (fixture / "README.md").write_text("fixture\n", encoding="utf-8")
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=root, check=True)
            subprocess.run(["git", "add", "."], cwd=root, check=True)
            subprocess.run(["git", "commit", "-q", "-m", "baseline"], cwd=root, check=True)
            case = CaseSpec(
                id="example",
                title="Example",
                category="test",
                weight=1,
                directory=case_root,
                prompt_path=case_root / "prompt.md",
                fixture_path=fixture,
                grader_path=case_root / "grader.py",
            )
            require_clean_inputs(root, [case])
            (case_root / "prompt.md").write_text("changed\n", encoding="utf-8")
            with self.assertRaises(InputIntegrityError):
                require_clean_inputs(root, [case])


if __name__ == "__main__":
    unittest.main()
