"""Pi process configuration, execution, and JSONL metric extraction."""

from __future__ import annotations

import json
import os
import re
import shlex
import signal
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


AUDIT_VERSION = 2
SCRATCH_DIRECTORY = ".benchmark-scratch"

_SHELL_OPERATORS = {";", "&&", "||", "|", "&"}
_SHELL_REDIRECTS = {"<", "<<", "<<<", ">", ">>"}
_NETWORK_COMMANDS = {
    "curl",
    "ftp",
    "nc",
    "ncat",
    "scp",
    "sftp",
    "ssh",
    "telnet",
    "wget",
}
_NETWORK_CODE = re.compile(
    r"(?:urllib\.request\.(?:urlopen|urlretrieve)|requests\.(?:get|post|put|patch|delete)|"
    r"http\.client\.|socket\.(?:create_connection|connect))",
    re.IGNORECASE,
)
_SHELL_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=(.*)$", re.DOTALL)
_SHELL_VARIABLE = re.compile(r"\$(?:\{([A-Za-z_][A-Za-z0-9_]*)\}|([A-Za-z_][A-Za-z0-9_]*))")
_WINDOWS_ABSOLUTE = re.compile(r"^(?:[A-Za-z]:[\\/]|\\\\)")


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
    scratch = workspace / SCRATCH_DIRECTORY
    scratch.mkdir(parents=True, exist_ok=True)
    env.update(
        {
            "PI_CODING_AGENT_DIR": str(agent_dir),
            "PI_OFFLINE": "1",
            "PI_TELEMETRY": "0",
            "TMPDIR": str(scratch),
            "TMP": str(scratch),
            "TEMP": str(scratch),
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


def _shell_tokens(command: str) -> list[str]:
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|<>")
        lexer.whitespace_split = True
        lexer.commenters = ""
        return list(lexer)
    except ValueError:
        return command.split()


def _expand_shell_variables(value: str, variables: dict[str, str]) -> str:
    def replace(match: re.Match[str]) -> str:
        name = match.group(1) or match.group(2) or ""
        return variables.get(name, match.group(0))

    expanded = value
    for _ in range(3):
        updated = _SHELL_VARIABLE.sub(replace, expanded)
        if updated == expanded:
            break
        expanded = updated
    return expanded


def _path_value(token: str, variables: dict[str, str]) -> str:
    assignment = _SHELL_ASSIGNMENT.match(token)
    value = assignment.group(1) if assignment else token
    if value.startswith("-") and "=" in value:
        value = value.split("=", 1)[1]
    return _expand_shell_variables(value, variables)


def _is_allowed_device(path: Path) -> bool:
    text = path.as_posix()
    return text in {"/dev/null", "/dev/stdin", "/dev/stdout", "/dev/stderr"} or text.startswith("/dev/fd/")


def _protected(path: Path, protected_roots: Iterable[Path]) -> bool:
    return any(_inside(path, root) for root in protected_roots)


def _audit_shell_command(
    command: str,
    workspace: Path,
    protected_roots: tuple[Path, ...],
) -> list[tuple[str, str, str]]:
    """Return reason, target, and evidence for explicit shell boundary attempts."""
    findings: list[tuple[str, str, str]] = []
    tokens = _shell_tokens(command)
    variables: dict[str, str] = {}
    cwd = workspace.resolve(strict=False)
    expect_cd_path = False
    expect_redirection_path = False
    command_name = ""
    grep_pattern_seen = False
    grep_expect_pattern = False
    grep_expect_file = False

    network_target = ""
    lowered_words = [Path(token).name.casefold() for token in tokens if token not in _SHELL_OPERATORS]
    for index, word in enumerate(lowered_words):
        if word in _NETWORK_COMMANDS:
            network_target = word
            break
        if word == "git" and any(
            candidate in {"clone", "fetch", "pull", "push", "ls-remote"}
            for candidate in lowered_words[index + 1:index + 4]
        ):
            network_target = "git remote operation"
            break
    if not network_target:
        match = _NETWORK_CODE.search(command)
        if match:
            network_target = match.group(0)
    if network_target:
        findings.append(("shell_network_attempt", network_target, "command_argument"))

    for token in tokens:
        if token in _SHELL_OPERATORS:
            expect_cd_path = False
            expect_redirection_path = False
            command_name = ""
            grep_pattern_seen = False
            grep_expect_pattern = False
            grep_expect_file = False
            continue
        if token in _SHELL_REDIRECTS:
            expect_redirection_path = token not in {"<<", "<<<"}
            continue
        assignment = _SHELL_ASSIGNMENT.match(token)
        if assignment:
            name = token.split("=", 1)[0]
            variables[name] = _expand_shell_variables(assignment.group(1), variables)
            continue
        if not command_name:
            command_name = Path(token).name.casefold()
            if command_name in {"command", "env"}:
                command_name = ""
            elif command_name == "cd":
                expect_cd_path = True
            continue
        if command_name == "cd" and not expect_cd_path:
            expect_cd_path = True

        value = _path_value(token, variables).strip()
        if not value or value.startswith(("http://", "https://")) or "$" in value:
            continue
        is_redirection_path = expect_redirection_path
        expect_redirection_path = False
        if command_name in {"echo", "printf"} and not is_redirection_path:
            continue
        if command_name in {"grep", "egrep", "fgrep", "rg"} and not is_redirection_path:
            if grep_expect_file:
                grep_expect_file = False
            elif grep_expect_pattern:
                grep_expect_pattern = False
                grep_pattern_seen = True
                continue
            elif token in {"-e", "--regexp"}:
                grep_expect_pattern = True
                continue
            elif token in {"-f", "--file"}:
                grep_expect_file = True
                continue
            elif token.startswith(("--regexp=", "-e")):
                grep_pattern_seen = True
                continue
            elif token.startswith("-") and not token.startswith("--file="):
                continue
            elif not grep_pattern_seen:
                grep_pattern_seen = True
                continue
        if command_name == "awk" and (
            "{" in value or value.startswith(("/", "BEGIN", "END"))
        ):
            continue
        if command_name == "sed" and value.startswith(("s/", "/")) and value.count("/") >= 2:
            continue
        has_parent = ".." in Path(value).parts
        is_windows_absolute = bool(_WINDOWS_ABSOLUTE.match(value))
        candidate: Path | None = None
        if value.startswith("~"):
            candidate = Path(value).expanduser()
        elif Path(value).is_absolute():
            candidate = Path(value)
        elif is_windows_absolute:
            findings.append(("shell_path_outside_workspace", value, "command_argument"))
        elif has_parent or expect_cd_path:
            candidate = cwd / value

        if candidate is not None:
            resolved = candidate.resolve(strict=False)
            if not _is_allowed_device(resolved) and not _inside(resolved, workspace):
                reason = (
                    "shell_protected_path_outside_workspace"
                    if _protected(resolved, protected_roots)
                    else "shell_path_outside_workspace"
                )
                findings.append((reason, value, "command_argument"))
            if expect_cd_path:
                cwd = resolved
        expect_cd_path = False
    return findings


def _tool_calls(stdout: str) -> Iterable[tuple[str, str, dict[str, Any]]]:
    seen: set[str] = set()
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        if event.get("type") == "tool_execution_start":
            call_id = str(event.get("toolCallId", "unknown"))
            arguments = event.get("args", {})
            if call_id not in seen and isinstance(arguments, dict):
                seen.add(call_id)
                yield call_id, str(event.get("toolName", "unknown")), arguments
        message = event.get("message")
        content = message.get("content") if isinstance(message, dict) else event.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict) or block.get("type") != "toolCall":
                continue
            call_id = str(block.get("id", "unknown"))
            arguments = block.get("arguments", {})
            if call_id in seen or not isinstance(arguments, dict):
                continue
            seen.add(call_id)
            yield call_id, str(block.get("name", "unknown")), arguments


def audit_workspace_accesses(stdout: str, workspace: Path, protected_paths: Iterable[Path]) -> list[dict[str, str]]:
    """Find tool calls that explicitly attempt paths or network outside the workspace.

    This is a post-run audit, not an OS sandbox. Structured path arguments are
    resolved precisely. Shell paths are resolved against deterministic ``cd``
    changes, so a traversal test inside the internal scratch directory remains
    valid while paths that resolve outside the task root are disqualifying.
    """
    findings: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    protected_roots = tuple(path.resolve(strict=False) for path in protected_paths)
    for call_id, tool, arguments in _tool_calls(stdout):
        reasons: list[tuple[str, str, str]] = []
        raw_path = arguments.get("path")
        if isinstance(raw_path, str) and raw_path:
            candidate = Path(raw_path)
            resolved = candidate if candidate.is_absolute() else workspace / candidate
            if not _inside(resolved, workspace):
                reasons.append(("structured_path_outside_workspace", raw_path, "structured_tool_argument"))
        if tool == "bash" and isinstance(arguments.get("command"), str):
            reasons.extend(_audit_shell_command(arguments["command"], workspace, protected_roots))
        for reason, target, evidence in reasons:
            key = (call_id, reason, target)
            if key in seen:
                continue
            seen.add(key)
            findings.append(
                {
                    "tool_call_id": call_id,
                    "tool": tool,
                    "reason": reason,
                    "target": target,
                    "access": "attempted",
                    "evidence": evidence,
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
