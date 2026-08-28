import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tinyjournal.exporter import export_markdown


class ExportTests(unittest.TestCase):
    def test_exports_markdown_inside_workspace(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "daily-note.txt").write_text("A useful thought.\n", encoding="utf-8")
            output = export_markdown(root, Path("daily-note.txt"), Path("exports/note.md"))
            self.assertEqual("# Daily Note\n\nA useful thought.\n", output.read_text(encoding="utf-8"))

    def test_rejects_output_traversal(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "note.txt").write_text("text", encoding="utf-8")
            with self.assertRaises(ValueError):
                export_markdown(root, Path("note.txt"), Path("../outside.md"))


if __name__ == "__main__":
    unittest.main()
