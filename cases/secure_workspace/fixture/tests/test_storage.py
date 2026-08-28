import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from safenotes import atomic_write_text, resolve_workspace_path


class StorageTests(unittest.TestCase):
    def test_nested_write(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = atomic_write_text(root, "notes/hello.md", "hello")
            self.assertEqual("hello", path.read_text(encoding="utf-8"))

    def test_resolve_simple_relative_path(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(root / "note.md", resolve_workspace_path(root, "note.md"))


if __name__ == "__main__":
    unittest.main()
