from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from localagent_bench.case_sdk import (
    CaseValidationError,
    create_case_template,
    discover_case_manifests,
    load_case_manifest,
    validate_case_runtime,
)
from localagent_bench.cli import main


VALID_GRADER = '''from __future__ import annotations
import json
checks = [{"id": "baseline", "points": 100, "earned": 0, "detail": "incomplete"}]
print(json.dumps({"score": 0, "max_score": 100, "checks": checks}))
'''


def write_case(cases_root: Path, case_id: str = "example") -> Path:
    case = cases_root / case_id
    fixture = case / "fixture"
    fixture.mkdir(parents=True)
    (case / "prompt.md").write_text("Complete the synthetic task.\n", encoding="utf-8")
    (case / "grader.py").write_text(VALID_GRADER, encoding="utf-8")
    (fixture / "README.md").write_text("Incomplete baseline.\n", encoding="utf-8")
    manifest = {
        "$schema": "../../schemas/case.schema.json",
        "schema_version": 1,
        "id": case_id,
        "title": {"it": "Caso di esempio", "en": "Example case"},
        "category": "test",
        "weight": 1.5,
        "paths": {"prompt": "prompt.md", "fixture": "fixture", "grader": "grader.py"},
    }
    (case / "case.json").write_text(json.dumps(manifest), encoding="utf-8")
    return case


def write_config(root: Path) -> Path:
    payload = {
        "version": 1,
        "ollama": {"url": "http://127.0.0.1:11434"},
        "pi": {"command": ["pi"]},
        "models": "installed",
        "defaults": {"sandbox": "audit"},
        "profiles": {"standard": ["example"]},
        "cases": {"directory": "cases"},
    }
    path = root / "benchmark.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


class CaseSdkTests(unittest.TestCase):
    def test_repository_manifests_match_public_schema_shape(self):
        schema = json.loads((ROOT / "schemas" / "case.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(1, schema["properties"]["schema_version"]["const"])
        cases = discover_case_manifests(ROOT / "cases")
        self.assertEqual(
            {"targeted_patch", "secure_workspace", "config_i18n", "milestone_closure", "results_dashboard"},
            set(cases),
        )

    def test_manifest_rejects_id_mismatch_unknown_field_and_unsafe_path(self):
        mutations = (
            ("id mismatch", lambda payload: payload.update({"id": "different"}), "non coincide"),
            ("unknown field", lambda payload: payload.update({"weigth": 1}), "Campi sconosciuti"),
            (
                "unsafe path",
                lambda payload: payload["paths"].update({"prompt": "../outside.md"}),
                "restare dentro",
            ),
            (
                "foreign absolute path",
                lambda payload: payload["paths"].update({"prompt": r"C:\\outside\\prompt.md"}),
                "separatori POSIX",
            ),
            ("boolean weight", lambda payload: payload.update({"weight": True}), "numero finito"),
            (
                "control character",
                lambda payload: payload["title"].update({"it": "Titolo\nnon valido"}),
                "caratteri di controllo",
            ),
        )
        for label, mutate, message in mutations:
            with self.subTest(label=label), tempfile.TemporaryDirectory() as directory:
                case = write_case(Path(directory) / "cases")
                manifest_path = case / "case.json"
                payload = json.loads(manifest_path.read_text(encoding="utf-8"))
                mutate(payload)
                manifest_path.write_text(json.dumps(payload), encoding="utf-8")
                with self.assertRaisesRegex(CaseValidationError, message):
                    load_case_manifest(case)

    def test_manifest_size_is_bounded(self):
        with tempfile.TemporaryDirectory() as directory:
            case = write_case(Path(directory) / "cases")
            (case / "case.json").write_text(" " * (64 * 1024 + 1), encoding="utf-8")
            with self.assertRaisesRegex(CaseValidationError, "troppo grande"):
                load_case_manifest(case)

    def test_discovery_rejects_incomplete_case_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            cases_root = Path(directory) / "cases"
            write_case(cases_root)
            (cases_root / "incomplete").mkdir()
            with self.assertRaisesRegex(CaseValidationError, "Manifesto mancante"):
                discover_case_manifests(cases_root)

    def test_fixture_symlink_cannot_escape_case(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            case = write_case(root / "cases")
            outside = root / "outside.txt"
            outside.write_text("private\n", encoding="utf-8")
            try:
                (case / "fixture" / "outside-link").symlink_to(outside)
            except OSError as exc:
                self.skipTest(f"symlink non disponibile: {exc}")
            with self.assertRaisesRegex(CaseValidationError, "Symlink della fixture fuori scope"):
                load_case_manifest(case)

    def test_runtime_validation_rejects_bad_protocol_and_completed_baseline(self):
        graders = (
            (
                "bad maximum",
                'import json; print(json.dumps({"score": 0, "max_score": 90, "checks": [{"id": "bad", "points": 100, "earned": 0}]}))\n',
                "max_score",
            ),
            (
                "completed baseline",
                'import json; print(json.dumps({"score": 100, "max_score": 100, "checks": [{"id": "done", "points": 100, "earned": 100}]}))\n',
                "atteso < 60",
            ),
        )
        for label, grader, message in graders:
            with self.subTest(label=label), tempfile.TemporaryDirectory() as directory:
                case_dir = write_case(Path(directory) / "cases")
                (case_dir / "grader.py").write_text(grader, encoding="utf-8")
                case = load_case_manifest(case_dir)
                with self.assertRaisesRegex(CaseValidationError, message):
                    validate_case_runtime(case)

    def test_template_is_atomic_valid_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            cases_root = Path(directory) / "cases"
            cases_root.mkdir()
            case = create_case_template(
                cases_root,
                "personal_case",
                title_it="Caso personale",
                title_en="Personal case",
                category="custom",
                weight=1.25,
                include_manual_rubric=True,
            )
            report = validate_case_runtime(case)
            self.assertEqual(0, report["baseline_score"])
            self.assertTrue(report["manual_rubric"])
            self.assertTrue((case.directory / "fixture" / "README.md").is_file())
            self.assertFalse(any(path.name.startswith(".personal_case-") for path in cases_root.iterdir()))
            with self.assertRaisesRegex(CaseValidationError, "esiste già"):
                create_case_template(
                    cases_root,
                    "personal_case",
                    title_it="Caso personale",
                    title_en="Personal case",
                    category="custom",
                    weight=1,
                )

    def test_cli_creates_then_validates_a_discovered_case(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_case(root / "cases")
            config_path = write_config(root)
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                exit_code = main(
                    [
                        "--config",
                        str(config_path),
                        "case",
                        "create",
                        "second_case",
                        "--title-it",
                        "Secondo caso",
                        "--title-en",
                        "Second case",
                        "--manual-rubric",
                    ]
                )
            self.assertEqual(0, exit_code)
            self.assertIn("Caso creato e validato", output.getvalue())
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(
                    0,
                    main(["--config", str(config_path), "case", "validate", "second_case"]),
                )


if __name__ == "__main__":
    unittest.main()
