from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from localagent_bench.pi_adapter import parse_json_events, write_models_config


class PiAdapterTests(unittest.TestCase):
    def test_extracts_usage_tools_and_final_response(self):
        lines = [
            {"type": "session", "version": 3},
            {"type": "tool_execution_start", "toolName": "read"},
            {"type": "tool_execution_end", "toolName": "read", "isError": False},
            {
                "type": "message_end",
                "message": {
                    "role": "assistant",
                    "content": [{"type": "text", "text": "done"}],
                    "stopReason": "stop",
                    "usage": {"input": 10, "output": 4, "cacheRead": 1, "cacheWrite": 0, "totalTokens": 15},
                },
            },
        ]
        metrics, response = parse_json_events("\n".join(json.dumps(line) for line in lines))
        self.assertEqual("done", response)
        self.assertEqual(1, metrics["tool_calls"])
        self.assertEqual(4, metrics["usage"]["output"])
        self.assertEqual(0, metrics["streamed_thinking_chars"])
        self.assertEqual(["stop"], metrics["stop_reasons"])

    def test_writes_isolated_ollama_configuration(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            write_models_config(target, "http://127.0.0.1:11434", ["model:a"], 8192, 1024, 0)
            payload = json.loads((target / "models.json").read_text(encoding="utf-8"))
            provider = payload["providers"]["ollama"]
            self.assertEqual("http://127.0.0.1:11434/v1", provider["baseUrl"])
            self.assertEqual("model:a", provider["models"][0]["id"])
            self.assertFalse(provider["compat"]["supportsDeveloperRole"])


if __name__ == "__main__":
    unittest.main()
