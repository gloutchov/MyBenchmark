"""Pi process configuration, execution, and JSONL metric extraction."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


@dataclass(frozen=True)
class PiRun:
    status: str
    exit_code: int | None
    duration_seconds: float
    stdout: str
    stderr: str
    metrics: dict[str, Any]
    final_response: str
    command: list[str]


def write_models_config(
    agent_dir: Path,
    ollama_url: str,
    models: Iterable[str],
    context_window: int,
    max_tokens: int,
    temperature: float,
) -> None:
    agent_dir.mkdir(parents=True, exist_ok=True)
    model_items = [
        {
            "id": name,
            "name": f"{name} (Ollama locale)",
            "reasoning": False,
            "input": ["text"],
            "contextWindow": context_window,
            "maxTokens": max_tokens,
            "samplingParams": {"temperature": temperature},
            "cost": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0},
        }
        for name in models
    ]
    payload = {
        "providers": {
            "ollama": {
                "baseUrl": f"{ollama_url.rstrip('/')}/v1",
                "api": "openai-completions",
                "apiKey": "ollama",
                "compat": {
                    "supportsDeveloperRole": False,
                    "supportsReasoningEffort": False,
                },
                "models": model_items,
            }
        }
    }
    (agent_dir / "models.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    (agent_dir / "settings.json").write_text(
        json.dumps({"defaultProjectTrust": "always", "telemetry": False}, indent=2) + "\n",
        encoding="utf-8",
    )


def _terminate(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    try:
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGTERM)
        else:
            process.terminate()
        process.wait(timeout=5)
    except (ProcessLookupError, subprocess.TimeoutExpired):
        if process.poll() is None:
            if os.name == "posix":
                os.killpg(process.pid, signal.SIGKILL)
            else:
                process.kill()


def run_pi(
    pi_command: tuple[str, ...],
    model: str,
    thinking: str,
    prompt: str,
    workspace: Path,
    agent_dir: Path,
    timeout_seconds: int,
) -> PiRun:
    command = [
        *pi_command,
        "--mode",
        "json",
        "--provider",
        "ollama",
        "--model",
        model,
        "--api-key",
        "ollama",
        "--thinking",
        thinking,
        "--tools",
        "read,bash,edit,write,grep,find,ls",
        "--no-session",
        "--no-extensions",
        "--no-skills",
        "--no-prompt-templates",
        "--no-themes",
        "--approve",
        "--offline",
        "--",
        prompt,
    ]
    env = os.environ.copy()
    env.update(
        {
            "PI_CODING_AGENT_DIR": str(agent_dir),
            "PI_OFFLINE": "1",
            "PI_TELEMETRY": "0",
        }
    )
    started = time.monotonic()
    process = subprocess.Popen(
        command,
        cwd=workspace,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=(os.name == "posix"),
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout_seconds)
        status = "ok" if process.returncode == 0 else "pi_error"
    except subprocess.TimeoutExpired:
        _terminate(process)
        stdout, stderr = process.communicate()
        status = "timeout"
    duration = time.monotonic() - started
    metrics, final_response = parse_json_events(stdout)
    return PiRun(
        status=status,
        exit_code=process.returncode,
        duration_seconds=round(duration, 3),
        stdout=stdout,
        stderr=stderr,
        metrics=metrics,
        final_response=final_response,
        command=command,
    )


def _content_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    return "\n".join(
        block.get("text", "")
        for block in content
        if isinstance(block, dict) and block.get("type") == "text" and isinstance(block.get("text"), str)
    )


def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=False))
    except ValueError:
        return False
    return True


def audit_workspace_accesses(stdout: str, workspace: Path, protected_paths: Iterable[Path]) -> list[dict[str, str]]:
    """Find tool calls that explicitly address paths outside the task workspace.

    This is a post-run audit, not an OS sandbox. Structured path arguments are
    resolved precisely; shell commands are checked conservatively for parent
    traversal and literal protected paths.
    """
    findings: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    protected: set[str] = set()
    for path in protected_paths:
        protected.add(str(path.absolute()))
        protected.add(str(path.resolve(strict=False)))
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        message = event.get("message")
        content = message.get("content") if isinstance(message, dict) else event.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict) or block.get("type") != "toolCall":
                continue
            tool = str(block.get("name", "unknown"))
            call_id = str(block.get("id", "unknown"))
            arguments = block.get("arguments", {})
            if not isinstance(arguments, dict):
                continue
            reasons: list[tuple[str, str]] = []
            raw_path = arguments.get("path")
            if isinstance(raw_path, str) and raw_path:
                candidate = Path(raw_path)
                resolved = candidate if candidate.is_absolute() else workspace / candidate
                if not _inside(resolved, workspace):
                    reasons.append(("structured_path_outside_workspace", raw_path))
            if tool == "bash" and isinstance(arguments.get("command"), str):
                command = arguments["command"].replace("\\ ", " ")
                if "../" in command or "..\\" in command:
                    reasons.append(("shell_parent_traversal", ".."))
                for protected_text in protected:
                    if protected_text in command:
                        reasons.append(("shell_protected_path", protected_text))
            for reason, target in reasons:
                key = (call_id, reason + "\0" + target)
                if key in seen:
                    continue
                seen.add(key)
                findings.append(
                    {
                        "tool_call_id": call_id,
                        "tool": tool,
                        "reason": reason,
                        "target": target,
                    }
                )
    return findings


def parse_json_events(stdout: str) -> tuple[dict[str, Any], str]:
    usage = {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0, "reasoning": 0, "totalTokens": 0}
    tool_calls = 0
    tool_errors = 0
    assistant_turns = 0
    parse_errors = 0
    streamed_text_chars = 0
    streamed_thinking_chars = 0
    final_response = ""
    stop_reasons: list[str] = []
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            if line.strip():
                parse_errors += 1
            continue
        if not isinstance(event, dict):
            continue
        event_type = event.get("type")
        if event_type == "message_update":
            update = event.get("assistantMessageEvent", {})
            if isinstance(update, dict) and isinstance(update.get("delta"), str):
                if update.get("type") == "text_delta":
                    streamed_text_chars += len(update["delta"])
                elif update.get("type") == "thinking_delta":
                    streamed_thinking_chars += len(update["delta"])
        if event_type == "tool_execution_start":
            tool_calls += 1
        elif event_type == "tool_execution_end" and event.get("isError") is True:
            tool_errors += 1
        elif event_type == "message_end":
            message = event.get("message")
            if not isinstance(message, dict) or message.get("role") != "assistant":
                continue
            assistant_turns += 1
            message_usage = message.get("usage", {})
            if isinstance(message_usage, dict):
                for key in usage:
                    value = message_usage.get(key, 0)
                    if isinstance(value, (int, float)):
                        usage[key] += int(value)
            if isinstance(message.get("stopReason"), str):
                stop_reasons.append(message["stopReason"])
            text = _content_text(message.get("content"))
            if text:
                final_response = text
    metrics = {
        "usage": usage,
        "tool_calls": tool_calls,
        "tool_errors": tool_errors,
        "assistant_turns": assistant_turns,
        "json_parse_errors": parse_errors,
        "streamed_text_chars": streamed_text_chars,
        "streamed_thinking_chars": streamed_thinking_chars,
        "stop_reasons": stop_reasons,
    }
    return metrics, final_response
