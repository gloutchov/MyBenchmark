from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from localagent_bench.pi_adapter import AUDIT_VERSION, audit_workspace_accesses, parse_json_events, write_models_config


class PiAdapterTests(unittest.TestCase):
    def test_current_audit_version(self):
        self.assertEqual(3, AUDIT_VERSION)

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

    def test_audits_structured_and_shell_access_outside_workspace(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workspace = root / "results" / "workspace"
            workspace.mkdir(parents=True)
            protected = root / "cases"
            protected.mkdir()
            event = {
                "type": "message_start",
                "message": {
                    "content": [
                        {"type": "toolCall", "id": "safe", "name": "read", "arguments": {"path": "src/app.py"}},
                        {"type": "toolCall", "id": "safe-absolute", "name": "read", "arguments": {"path": str(workspace / "README.md")}},
                        {"type": "toolCall", "id": "escape", "name": "edit", "arguments": {"path": str(protected / "fixture.py")}},
                        {"type": "toolCall", "id": "shell", "name": "bash", "arguments": {"command": f"python3 {protected}/grader.py"}},
                    ]
                },
            }
            findings = audit_workspace_accesses(json.dumps(event), workspace, [protected])
            self.assertEqual({"escape", "shell"}, {item["tool_call_id"] for item in findings})
            self.assertTrue(any(item["reason"] == "structured_path_outside_workspace" for item in findings))
            self.assertTrue(
                any(item["reason"] == "shell_protected_path_outside_workspace" for item in findings)
            )
            self.assertTrue(all(item["access"] == "attempted" for item in findings))

    def test_allows_nested_scratch_traversal_test_that_stays_in_workspace(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory) / "workspace"
            workspace.mkdir()
            event = {
                "type": "tool_execution_start",
                "toolCallId": "scratch-test",
                "toolName": "bash",
                "args": {
                    "command": (
                        "mkdir -p .benchmark-scratch/app && cd .benchmark-scratch/app && "
                        "python3 -m tinyjournal export note.txt ../rejected.md"
                    )
                },
            }
            findings = audit_workspace_accesses(json.dumps(event), workspace, [workspace.parent])
            self.assertEqual([], findings)

    def test_reports_system_temp_repository_and_network_attempts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workspace = root / "results" / "workspace"
            workspace.mkdir(parents=True)
            event = {
                "type": "tool_execution_start",
                "toolCallId": "outside",
                "toolName": "bash",
                "args": {
                    "command": (
                        f'cd /tmp && cp "{root}/LICENSE" LICENSE && '
                        "curl -fsSL https://example.invalid/LICENSE -o LICENSE"
                    )
                },
            }
            findings = audit_workspace_accesses(json.dumps(event), workspace, [root])
            reasons = {item["reason"] for item in findings}
            self.assertIn("shell_path_outside_workspace", reasons)
            self.assertIn("shell_protected_path_outside_workspace", reasons)
            self.assertIn("shell_network_attempt", reasons)

    def test_url_text_alone_is_not_a_network_attempt(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            event = {
                "type": "tool_execution_start",
                "toolCallId": "docs",
                "toolName": "bash",
                "args": {"command": "printf 'https://example.invalid/docs' > README.md"},
            }
            self.assertEqual([], audit_workspace_accesses(json.dumps(event), workspace, []))

    def test_awk_program_starting_with_slash_is_not_a_path(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            event = {
                "type": "tool_execution_start",
                "toolCallId": "awk",
                "toolName": "bash",
                "args": {
                    "command": r"awk '/- \[x\] Export command implemented/ {print NR}' PLAN.md"
                },
            }
            self.assertEqual([], audit_workspace_accesses(json.dumps(event), workspace, []))

    def test_printed_and_grep_patterns_are_not_treated_as_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            event = {
                "type": "tool_execution_start",
                "toolCallId": "text",
                "toolName": "bash",
                "args": {
                    "command": "echo /tmp && grep '/tmp' README.md && printf '/outside' > NOTES.md"
                },
            }
            self.assertEqual([], audit_workspace_accesses(json.dumps(event), workspace, []))

    def test_grep_input_and_redirection_outside_workspace_are_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            event = {
                "type": "tool_execution_start",
                "toolCallId": "paths",
                "toolName": "bash",
                "args": {"command": "grep needle /tmp/input.txt > /tmp/output.txt"},
            }
            findings = audit_workspace_accesses(json.dumps(event), workspace, [])
            self.assertEqual(
                {"/tmp/input.txt", "/tmp/output.txt"},
                {item["target"] for item in findings},
            )

    def test_foreign_absolute_path_style_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            foreign_path = "C:/outside/input.txt" if sys.platform != "win32" else "/tmp/input.txt"
            event = {
                "type": "tool_execution_start",
                "toolCallId": "foreign-path",
                "toolName": "bash",
                "args": {"command": f"python read_file.py {foreign_path}"},
            }
            findings = audit_workspace_accesses(json.dumps(event), workspace, [])
            self.assertEqual({foreign_path}, {item["target"] for item in findings})

    def test_literal_heredoc_body_is_not_parsed_as_shell_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            event = {
                "type": "tool_execution_start",
                "toolCallId": "heredoc",
                "toolName": "bash",
                "args": {
                    "command": (
                        "cat > tests.py << 'EOF'\n"
                        "from pathlib import Path\n"
                        "ROOT = Path(__file__).resolve().parents[1] / \"src\"\n"
                        "EOF"
                    )
                },
            }
            self.assertEqual([], audit_workspace_accesses(json.dumps(event), workspace, []))

    def test_executable_heredoc_network_code_is_still_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            events = [
                {
                    "type": "tool_execution_start",
                    "toolCallId": "python-heredoc",
                    "toolName": "bash",
                    "args": {
                        "command": "python3 <<'PY'\nimport requests\nrequests.get('https://example.invalid')\nPY"
                    },
                },
                {
                    "type": "tool_execution_start",
                    "toolCallId": "shell-heredoc",
                    "toolName": "bash",
                    "args": {"command": "bash <<'SH'\ncurl https://example.invalid\nSH"},
                },
            ]
            findings = audit_workspace_accesses("\n".join(json.dumps(event) for event in events), workspace, [])
            self.assertEqual(
                {"python-heredoc", "shell-heredoc"},
                {item["tool_call_id"] for item in findings},
            )
            self.assertTrue(all(item["reason"] == "shell_network_attempt" for item in findings))


if __name__ == "__main__":
    unittest.main()
