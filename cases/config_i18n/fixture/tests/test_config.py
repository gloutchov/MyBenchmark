import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from notekeeper import Settings, load_settings, save_settings


class ConfigTests(unittest.TestCase):
    def test_missing_file_uses_defaults(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = load_settings(Path(directory) / "settings.json")
            self.assertEqual(30, settings.autosave_seconds)

    def test_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            save_settings(path, Settings())
            self.assertEqual(Settings(), load_settings(path))


if __name__ == "__main__":
    unittest.main()
