from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from localagent_bench.ollama import (
    OllamaError,
    OllamaModel,
    inspect_model,
    list_models,
    preflight_thinking,
    warmup,
)
from localagent_bench.thinking import ThinkingPolicyError, resolve_thinking_policy


class ThinkingPolicyTests(unittest.TestCase):
    def test_canonicalizes_supported_levels_without_fallback(self):
        expected = {
            "off": "none",
            "minimal": "low",
            "low": "low",
            "medium": "medium",
            "high": "high",
            "xhigh": "max",
            "max": "max",
        }
        self.assertEqual(
            expected,
            {level: resolve_thinking_policy(level).reasoning_effort for level in expected},
        )
        with self.assertRaises(ThinkingPolicyError):
            resolve_thinking_policy("automatic")

    def test_native_warmup_control_matches_effective_level(self):
        self.assertIs(resolve_thinking_policy("off").native_think, False)
        self.assertEqual("medium", resolve_thinking_policy("medium").native_think)


class OllamaThinkingTests(unittest.TestCase):
    def setUp(self):
        self.model = OllamaModel("model:a", 1, "digest", "now", {})

    @patch("localagent_bench.ollama._request")
    def test_list_models_keeps_only_whitelisted_details(self, request_mock):
        request_mock.return_value = {
            "models": [
                {
                    "name": "model:a",
                    "size": 1,
                    "digest": "digest",
                    "details": {
                        "family": "qwen",
                        "parameter_size": "9B",
                        "private_template": "DO-NOT-STORE",
                    },
                }
            ]
        }
        models = list_models("http://127.0.0.1:11434")
        self.assertEqual({"family": "qwen", "parameter_size": "9B"}, models[0].details)
        self.assertNotIn("DO-NOT-STORE", repr(models[0]))

    @patch("localagent_bench.ollama._request")
    def test_inspect_model_whitelists_capabilities(self, request_mock):
        request_mock.return_value = {
            "capabilities": ["completion", "thinking", "thinking", "x" * 65, 42],
            "private_template": "DO-NOT-STORE",
        }
        inspected = inspect_model("http://127.0.0.1:11434", self.model)
        self.assertEqual(("completion", "thinking"), inspected.capabilities)
        self.assertTrue(inspected.capabilities_known)
        self.assertTrue(inspected.thinking_capable)
        self.assertNotIn("DO-NOT-STORE", repr(inspected))

    @patch("localagent_bench.ollama._request", return_value={"template": "unknown"})
    def test_inspect_model_marks_missing_capabilities_unknown(self, _request_mock):
        inspected = inspect_model("http://127.0.0.1:11434", self.model)
        self.assertFalse(inspected.capabilities_known)
        self.assertIsNone(inspected.thinking_capable)

    @patch("localagent_bench.ollama._request", return_value=[])
    def test_inspect_model_rejects_malformed_response(self, _request_mock):
        with self.assertRaises(OllamaError):
            inspect_model("http://127.0.0.1:11434", self.model)

    @patch("localagent_bench.ollama._request", return_value={"capabilities": ["completion"]})
    def test_inspect_model_distinguishes_non_thinking_model(self, _request_mock):
        inspected = inspect_model("http://127.0.0.1:11434", self.model)
        self.assertTrue(inspected.capabilities_known)
        self.assertFalse(inspected.thinking_capable)

    @patch("localagent_bench.ollama._request")
    def test_preflight_off_requires_none_and_rejects_observed_reasoning(self, request_mock):
        request_mock.return_value = {
            "choices": [{"message": {"content": "391", "reasoning": "private trace"}}],
            "usage": {"completion_tokens_details": {"reasoning_tokens": 4}},
        }
        result = preflight_thinking(
            "http://127.0.0.1:11434",
            self.model,
            resolve_thinking_policy("off"),
            timeout=30,
        )
        self.assertEqual("unexpected_thinking", result.status)
        self.assertTrue(result.thinking_observed)
        payload = request_mock.call_args.args[2]
        self.assertEqual("none", payload["reasoning_effort"])
        self.assertNotIn("private trace", repr(result))

    @patch("localagent_bench.ollama._request")
    def test_active_preflight_requires_capability_and_observable_reasoning(self, request_mock):
        capable = OllamaModel(
            "model:a",
            1,
            "digest",
            "now",
            {},
            ("thinking",),
            True,
            True,
        )
        request_mock.return_value = {
            "choices": [{"message": {"content": "391"}}],
            "usage": {"completion_tokens_details": {"reasoning_tokens": 0}},
        }
        missing = preflight_thinking(
            "http://127.0.0.1:11434",
            capable,
            resolve_thinking_policy("medium"),
            timeout=30,
        )
        self.assertEqual("thinking_not_observed", missing.status)
        request_mock.return_value["usage"]["completion_tokens_details"]["reasoning_tokens"] = 7
        passed = preflight_thinking(
            "http://127.0.0.1:11434",
            capable,
            resolve_thinking_policy("medium"),
            timeout=30,
        )
        self.assertTrue(passed.passed)
        self.assertEqual("medium", request_mock.call_args.args[2]["reasoning_effort"])

        unsupported = preflight_thinking(
            "http://127.0.0.1:11434",
            self.model,
            resolve_thinking_policy("medium"),
            timeout=30,
        )
        self.assertEqual("unknown_capability", unsupported.status)

    @patch("localagent_bench.ollama._request", return_value={"done": True})
    def test_warmup_uses_native_thinking_control(self, request_mock):
        warmup(
            "http://127.0.0.1:11434",
            "model:a",
            "15m",
            30,
            resolve_thinking_policy("off"),
        )
        self.assertIs(request_mock.call_args.args[2]["think"], False)
        warmup(
            "http://127.0.0.1:11434",
            "model:a",
            "15m",
            30,
            resolve_thinking_policy("medium"),
        )
        self.assertEqual("medium", request_mock.call_args.args[2]["think"])


if __name__ == "__main__":
    unittest.main()
