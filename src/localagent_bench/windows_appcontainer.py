"""Windows AppContainer launcher with a fixed-destination Ollama named-pipe broker."""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import uuid
from ctypes import wintypes
from pathlib import Path
from urllib.parse import urlparse


ERROR_ALREADY_EXISTS_HRESULT = 0x800700B7
ERROR_INSUFFICIENT_BUFFER = 122
ERROR_PIPE_CONNECTED = 535
EXTENDED_STARTUPINFO_PRESENT = 0x00080000
CREATE_SUSPENDED = 0x00000004
STARTF_USESTDHANDLES = 0x00000100
PROC_THREAD_ATTRIBUTE_SECURITY_CAPABILITIES = 0x00020009
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
JOB_OBJECT_EXTENDED_LIMIT_INFORMATION = 9
WAIT_FAILED = 0xFFFFFFFF
INFINITE = 0xFFFFFFFF
SE_GROUP_ENABLED = 0x00000004
_LIBRARY_CACHE = None


class AppContainerError(RuntimeError):
    """Raised when Windows cannot apply the requested AppContainer boundary."""


class STARTUPINFOW(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("lpReserved", wintypes.LPWSTR),
        ("lpDesktop", wintypes.LPWSTR),
        ("lpTitle", wintypes.LPWSTR),
        ("dwX", wintypes.DWORD),
        ("dwY", wintypes.DWORD),
        ("dwXSize", wintypes.DWORD),
        ("dwYSize", wintypes.DWORD),
        ("dwXCountChars", wintypes.DWORD),
        ("dwYCountChars", wintypes.DWORD),
        ("dwFillAttribute", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("wShowWindow", wintypes.WORD),
        ("cbReserved2", wintypes.WORD),
        ("lpReserved2", ctypes.POINTER(ctypes.c_ubyte)),
        ("hStdInput", wintypes.HANDLE),
        ("hStdOutput", wintypes.HANDLE),
        ("hStdError", wintypes.HANDLE),
    ]


class STARTUPINFOEXW(ctypes.Structure):
    _fields_ = [("StartupInfo", STARTUPINFOW), ("lpAttributeList", ctypes.c_void_p)]


class PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("hProcess", wintypes.HANDLE),
        ("hThread", wintypes.HANDLE),
        ("dwProcessId", wintypes.DWORD),
        ("dwThreadId", wintypes.DWORD),
    ]


class SECURITY_CAPABILITIES(ctypes.Structure):
    _fields_ = [
        ("AppContainerSid", ctypes.c_void_p),
        ("Capabilities", ctypes.c_void_p),
        ("CapabilityCount", wintypes.DWORD),
        ("Reserved", wintypes.DWORD),
    ]


class SECURITY_ATTRIBUTES(ctypes.Structure):
    _fields_ = [
        ("nLength", wintypes.DWORD),
        ("lpSecurityDescriptor", ctypes.c_void_p),
        ("bInheritHandle", wintypes.BOOL),
    ]


class IO_COUNTERS(ctypes.Structure):
    _fields_ = [(name, ctypes.c_ulonglong) for name in (
        "ReadOperationCount",
        "WriteOperationCount",
        "OtherOperationCount",
        "ReadTransferCount",
        "WriteTransferCount",
        "OtherTransferCount",
    )]


class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_longlong),
        ("PerJobUserTimeLimit", ctypes.c_longlong),
        ("LimitFlags", wintypes.DWORD),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", wintypes.DWORD),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", wintypes.DWORD),
        ("SchedulingClass", wintypes.DWORD),
    ]


class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
        ("IoInfo", IO_COUNTERS),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


def _last_error(message: str) -> AppContainerError:
    return AppContainerError(f"{message}: Windows error {ctypes.get_last_error()}")


def _libraries():
    global _LIBRARY_CACHE
    if os.name != "nt":
        raise AppContainerError("AppContainer is available only on Windows")
    if _LIBRARY_CACHE is None:
        _LIBRARY_CACHE = (
        ctypes.WinDLL("kernel32", use_last_error=True),
        ctypes.WinDLL("userenv", use_last_error=True),
        ctypes.WinDLL("advapi32", use_last_error=True),
        )
        _configure(*_LIBRARY_CACHE)
    return _LIBRARY_CACHE


def _configure(kernel32, userenv, advapi32) -> None:
    userenv.CreateAppContainerProfile.argtypes = [
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(ctypes.c_void_p),
    ]
    userenv.CreateAppContainerProfile.restype = ctypes.c_long
    userenv.DeriveAppContainerSidFromAppContainerName.argtypes = [
        wintypes.LPCWSTR,
        ctypes.POINTER(ctypes.c_void_p),
    ]
    userenv.DeriveAppContainerSidFromAppContainerName.restype = ctypes.c_long
    userenv.DeleteAppContainerProfile.argtypes = [wintypes.LPCWSTR]
    userenv.DeleteAppContainerProfile.restype = ctypes.c_long
    advapi32.ConvertSidToStringSidW.argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.LPWSTR)]
    advapi32.ConvertSidToStringSidW.restype = wintypes.BOOL
    advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.POINTER(wintypes.DWORD),
    ]
    advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW.restype = wintypes.BOOL
    kernel32.InitializeProcThreadAttributeList.argtypes = [
        ctypes.c_void_p,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.POINTER(ctypes.c_size_t),
    ]
    kernel32.InitializeProcThreadAttributeList.restype = wintypes.BOOL
    kernel32.UpdateProcThreadAttribute.argtypes = [
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.c_size_t,
        ctypes.c_void_p,
        ctypes.c_size_t,
        ctypes.c_void_p,
        ctypes.c_void_p,
    ]
    kernel32.UpdateProcThreadAttribute.restype = wintypes.BOOL
    kernel32.DeleteProcThreadAttributeList.argtypes = [ctypes.c_void_p]
    kernel32.CreateProcessW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.LPWSTR,
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.BOOL,
        wintypes.DWORD,
        ctypes.c_void_p,
        wintypes.LPCWSTR,
        ctypes.POINTER(STARTUPINFOW),
        ctypes.POINTER(PROCESS_INFORMATION),
    ]
    kernel32.CreateProcessW.restype = wintypes.BOOL
    kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    kernel32.SetInformationJobObject.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        ctypes.c_void_p,
        wintypes.DWORD,
    ]
    kernel32.SetInformationJobObject.restype = wintypes.BOOL
    kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
    kernel32.ResumeThread.argtypes = [wintypes.HANDLE]
    kernel32.ResumeThread.restype = wintypes.DWORD
    kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel32.WaitForSingleObject.restype = wintypes.DWORD
    kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel32.GetExitCodeProcess.restype = wintypes.BOOL
    kernel32.GetStdHandle.argtypes = [wintypes.DWORD]
    kernel32.GetStdHandle.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    kernel32.CreateNamedPipeW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.POINTER(SECURITY_ATTRIBUTES),
    ]
    kernel32.CreateNamedPipeW.restype = wintypes.HANDLE
    kernel32.ConnectNamedPipe.argtypes = [wintypes.HANDLE, ctypes.c_void_p]
    kernel32.ConnectNamedPipe.restype = wintypes.BOOL
    kernel32.DisconnectNamedPipe.argtypes = [wintypes.HANDLE]
    kernel32.DisconnectNamedPipe.restype = wintypes.BOOL
    kernel32.ReadFile.argtypes = [
        wintypes.HANDLE,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
        ctypes.c_void_p,
    ]
    kernel32.ReadFile.restype = wintypes.BOOL
    kernel32.WriteFile.argtypes = [
        wintypes.HANDLE,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
        ctypes.c_void_p,
    ]
    kernel32.WriteFile.restype = wintypes.BOOL
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p
    advapi32.FreeSid.argtypes = [ctypes.c_void_p]
    advapi32.FreeSid.restype = ctypes.c_void_p


def _create_profile(name: str) -> tuple[ctypes.c_void_p, bool, str]:
    kernel32, userenv, advapi32 = _libraries()
    sid = ctypes.c_void_p()
    result = int(userenv.CreateAppContainerProfile(name, name, name, None, 0, ctypes.byref(sid)))
    created = result == 0
    if not created:
        if result & 0xFFFFFFFF != ERROR_ALREADY_EXISTS_HRESULT:
            raise AppContainerError(f"CreateAppContainerProfile failed: HRESULT 0x{result & 0xFFFFFFFF:08x}")
        result = int(userenv.DeriveAppContainerSidFromAppContainerName(name, ctypes.byref(sid)))
        if result != 0:
            raise AppContainerError(
                f"DeriveAppContainerSidFromAppContainerName failed: HRESULT 0x{result & 0xFFFFFFFF:08x}"
            )
    sid_text = wintypes.LPWSTR()
    if not advapi32.ConvertSidToStringSidW(sid, ctypes.byref(sid_text)):
        advapi32.FreeSid(sid)
        raise _last_error("ConvertSidToStringSidW failed")
    try:
        value = sid_text.value
    finally:
        kernel32.LocalFree(sid_text)
    return sid, created, value


def _delete_profile(name: str) -> bool:
    _kernel32, userenv, _advapi32 = _libraries()
    result = int(userenv.DeleteAppContainerProfile(name))
    return result == 0


def _free_sid(sid: ctypes.c_void_p) -> None:
    _kernel32, _userenv, advapi32 = _libraries()
    advapi32.FreeSid(sid)


def _pi_install_root(command_name: str) -> Path:
    executable = shutil.which(command_name)
    if not executable:
        raise AppContainerError(f"Pi command not found: {command_name}")
    path = Path(executable).resolve(strict=False)
    return path.parent.parent if path.parent.name.lower() == "bin" else path.parent


def _icacls(path: Path, action: str, sid: str, permission: str | None = None) -> None:
    if action == "grant":
        assert permission is not None
        args = ["icacls", str(path), "/grant", f"*{sid}:(OI)(CI){permission}", "/T", "/C", "/Q"]
    else:
        args = ["icacls", str(path), "/remove", f"*{sid}", "/T", "/C", "/Q"]
    result = subprocess.run(args, capture_output=True, text=True, check=False, timeout=120)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip().splitlines()
        raise AppContainerError(f"icacls {action} failed: {detail[0] if detail else result.returncode}")


def _grant_paths(sid: str, workspace: Path, agent_dir: Path, install_root: Path) -> list[Path]:
    permissions = [(workspace, "M"), (agent_dir, "M"), (install_root, "RX")]
    granted: list[Path] = []
    try:
        for path, permission in permissions:
            _icacls(path, "grant", sid, permission)
            granted.append(path)
    except Exception:
        for path in reversed(granted):
            try:
                _icacls(path, "remove", sid)
            except AppContainerError:
                pass
        raise
    return granted


def _remove_paths(sid: str, paths: list[Path]) -> bool:
    clean = True
    for path in reversed(paths):
        try:
            _icacls(path, "remove", sid)
        except AppContainerError:
            clean = False
    return clean


def _resolved_command(command: list[str]) -> list[str]:
    executable = shutil.which(command[0])
    if not executable:
        raise AppContainerError(f"command not found: {command[0]}")
    resolved = [executable, *command[1:]]
    if Path(executable).suffix.lower() in {".bat", ".cmd"}:
        shell = os.environ.get("COMSPEC") or shutil.which("cmd.exe")
        if not shell:
            raise AppContainerError("cmd.exe is unavailable")
        return [shell, "/d", "/s", "/c", subprocess.list2cmdline(resolved)]
    return resolved


def _create_job(kernel32):
    job = kernel32.CreateJobObjectW(None, None)
    if not job:
        raise _last_error("CreateJobObjectW failed")
    limits = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
    limits.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    if not kernel32.SetInformationJobObject(
        job,
        JOB_OBJECT_EXTENDED_LIMIT_INFORMATION,
        ctypes.byref(limits),
        ctypes.sizeof(limits),
    ):
        kernel32.CloseHandle(job)
        raise _last_error("SetInformationJobObject failed")
    return job


def _launch(sid: ctypes.c_void_p, command: list[str], cwd: Path) -> int:
    kernel32, _userenv, _advapi32 = _libraries()
    size = ctypes.c_size_t()
    kernel32.InitializeProcThreadAttributeList(None, 1, 0, ctypes.byref(size))
    if ctypes.get_last_error() != ERROR_INSUFFICIENT_BUFFER:
        raise _last_error("InitializeProcThreadAttributeList sizing failed")
    attributes_buffer = ctypes.create_string_buffer(size.value)
    attributes = ctypes.cast(attributes_buffer, ctypes.c_void_p)
    if not kernel32.InitializeProcThreadAttributeList(attributes, 1, 0, ctypes.byref(size)):
        raise _last_error("InitializeProcThreadAttributeList failed")
    capabilities = SECURITY_CAPABILITIES(sid, None, 0, 0)
    startup = STARTUPINFOEXW()
    startup.StartupInfo.cb = ctypes.sizeof(startup)
    startup.StartupInfo.dwFlags = STARTF_USESTDHANDLES
    startup.StartupInfo.hStdInput = kernel32.GetStdHandle(0xFFFFFFF6)
    startup.StartupInfo.hStdOutput = kernel32.GetStdHandle(0xFFFFFFF5)
    startup.StartupInfo.hStdError = kernel32.GetStdHandle(0xFFFFFFF4)
    startup.lpAttributeList = attributes
    process = PROCESS_INFORMATION()
    job = _create_job(kernel32)
    try:
        if not kernel32.UpdateProcThreadAttribute(
            attributes,
            0,
            PROC_THREAD_ATTRIBUTE_SECURITY_CAPABILITIES,
            ctypes.byref(capabilities),
            ctypes.sizeof(capabilities),
            None,
            None,
        ):
            raise _last_error("UpdateProcThreadAttribute failed")
        command_line = ctypes.create_unicode_buffer(subprocess.list2cmdline(_resolved_command(command)))
        if not kernel32.CreateProcessW(
            None,
            command_line,
            None,
            None,
            True,
            EXTENDED_STARTUPINFO_PRESENT | CREATE_SUSPENDED,
            None,
            str(cwd),
            ctypes.byref(startup.StartupInfo),
            ctypes.byref(process),
        ):
            raise _last_error("CreateProcessW failed")
        try:
            if not kernel32.AssignProcessToJobObject(job, process.hProcess):
                raise _last_error("AssignProcessToJobObject failed")
            if kernel32.ResumeThread(process.hThread) == 0xFFFFFFFF:
                raise _last_error("ResumeThread failed")
            kernel32.CloseHandle(process.hThread)
            process.hThread = None
            if kernel32.WaitForSingleObject(process.hProcess, INFINITE) == WAIT_FAILED:
                raise _last_error("WaitForSingleObject failed")
            exit_code = wintypes.DWORD()
            if not kernel32.GetExitCodeProcess(process.hProcess, ctypes.byref(exit_code)):
                raise _last_error("GetExitCodeProcess failed")
            return int(exit_code.value)
        finally:
            if process.hThread:
                kernel32.CloseHandle(process.hThread)
            if process.hProcess:
                kernel32.CloseHandle(process.hProcess)
    finally:
        kernel32.CloseHandle(job)
        kernel32.DeleteProcThreadAttributeList(attributes)


def _target(url: str) -> tuple[str, int]:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or parsed.hostname not in {
        "127.0.0.1",
        "::1",
        "localhost",
    }:
        raise AppContainerError("Ollama must use an HTTP(S) loopback URL")
    return parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80)


class NamedPipeBroker:
    def __init__(self, pipe_path: str, sid: str, target: tuple[str, int]):
        self.pipe_path = pipe_path
        self.sid = sid
        self.target = target
        self.stop = threading.Event()
        self.ready = threading.Event()
        self.error: AppContainerError | None = None
        self.thread = threading.Thread(target=self._serve, daemon=True)

    def start(self) -> None:
        self.thread.start()
        if not self.ready.wait(timeout=5):
            raise AppContainerError("named-pipe broker did not become ready")
        if self.error is not None:
            raise self.error

    def close(self) -> None:
        self.stop.set()
        self.thread.join(timeout=1)

    def _security(self):
        kernel32, _userenv, advapi32 = _libraries()
        descriptor = ctypes.c_void_p()
        sddl = f"D:P(A;;GA;;;{self.sid})"
        if not advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW(
            sddl, 1, ctypes.byref(descriptor), None
        ):
            raise _last_error("named-pipe security descriptor failed")
        return kernel32, descriptor, SECURITY_ATTRIBUTES(
            ctypes.sizeof(SECURITY_ATTRIBUTES), descriptor, False
        )

    def _serve(self) -> None:
        try:
            kernel32, descriptor, security = self._security()
        except AppContainerError as exc:
            self.error = exc
            self.ready.set()
            return
        try:
            first_instance = True
            while not self.stop.is_set():
                handle = kernel32.CreateNamedPipeW(
                    self.pipe_path,
                    0x00000003,
                    0x00000000,
                    255,
                    65536,
                    65536,
                    0,
                    ctypes.byref(security),
                )
                if handle == ctypes.c_void_p(-1).value:
                    if first_instance:
                        self.error = _last_error("CreateNamedPipeW failed")
                        self.ready.set()
                    return
                if first_instance:
                    first_instance = False
                    self.ready.set()
                connected = kernel32.ConnectNamedPipe(handle, None)
                if not connected and ctypes.get_last_error() != ERROR_PIPE_CONNECTED:
                    kernel32.CloseHandle(handle)
                    continue
                if self.stop.is_set():
                    kernel32.CloseHandle(handle)
                    break
                threading.Thread(target=self._handle, args=(handle,), daemon=True).start()
        finally:
            kernel32.LocalFree(descriptor)

    def _handle(self, handle) -> None:
        kernel32, _userenv, _advapi32 = _libraries()
        try:
            upstream = socket.create_connection(self.target, timeout=10)
        except OSError:
            kernel32.CloseHandle(handle)
            return

        def pipe_to_socket() -> None:
            buffer = ctypes.create_string_buffer(65536)
            count = wintypes.DWORD()
            while kernel32.ReadFile(handle, buffer, len(buffer), ctypes.byref(count), None):
                if not count.value:
                    break
                try:
                    upstream.sendall(buffer.raw[: count.value])
                except OSError:
                    break
            try:
                upstream.shutdown(socket.SHUT_WR)
            except OSError:
                pass

        def socket_to_pipe() -> None:
            written = wintypes.DWORD()
            try:
                while True:
                    data = upstream.recv(65536)
                    if not data:
                        break
                    buffer = ctypes.create_string_buffer(data)
                    if not kernel32.WriteFile(handle, buffer, len(data), ctypes.byref(written), None):
                        break
            except OSError:
                pass

        first = threading.Thread(target=pipe_to_socket, daemon=True)
        second = threading.Thread(target=socket_to_pipe, daemon=True)
        first.start()
        second.start()
        first.join()
        second.join()
        upstream.close()
        kernel32.DisconnectNamedPipe(handle)
        kernel32.CloseHandle(handle)


def _write_metadata(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def run_container(args, command: list[str]) -> int:
    workspace = args.workspace.resolve()
    agent_dir = args.agent_dir.resolve()
    install_root = _pi_install_root(args.pi_command)
    sid, created, sid_text = _create_profile(args.profile)
    granted: list[Path] = []
    broker: NamedPipeBroker | None = None
    metadata: dict[str, object] = {
        "appcontainer_sid": sid_text,
        "profile_created": created,
        "network_capabilities": [],
        "job_kill_on_close": True,
        "acl_roots": [str(workspace), str(agent_dir), str(install_root)],
    }
    _write_metadata(args.metadata, metadata)
    try:
        granted = _grant_paths(sid_text, workspace, agent_dir, install_root)
        broker = NamedPipeBroker(args.pipe, sid_text, _target(args.url))
        broker.start()
        return _launch(sid, command, workspace)
    finally:
        if broker is not None:
            broker.close()
        metadata["acl_removed"] = _remove_paths(sid_text, granted)
        _free_sid(sid)
        metadata["profile_deleted"] = _delete_profile(args.profile)
        _write_metadata(args.metadata, metadata)


def probe() -> int:
    if os.name != "nt":
        raise AppContainerError("AppContainer probe requires Windows")
    name = f"LocalAgentBenchmark.Probe.{uuid.uuid4().hex}"
    sid, _created, _sid_text = _create_profile(name)
    try:
        with tempfile.TemporaryDirectory() as directory:
            private = Path(directory) / "private.txt"
            private.write_text(hashlib.sha256(name.encode()).hexdigest(), encoding="utf-8")
            script = f'type "{private}" >nul 2>&1 && exit /b 9 || exit /b 0'
            windows = Path(os.environ.get("WINDIR", r"C:\Windows"))
            return _launch(sid, ["cmd.exe", "/d", "/s", "/c", script], windows)
    finally:
        _free_sid(sid)
        _delete_profile(name)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="action", required=True)
    subparsers.add_parser("probe")
    run = subparsers.add_parser("run")
    run.add_argument("--profile", required=True)
    run.add_argument("--workspace", type=Path, required=True)
    run.add_argument("--agent-dir", type=Path, required=True)
    run.add_argument("--pi-command", required=True)
    run.add_argument("--pipe", required=True)
    run.add_argument("--url", required=True)
    run.add_argument("--metadata", type=Path, required=True)
    run.add_argument("command", nargs=argparse.REMAINDER)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.action == "probe":
            return probe()
        command = list(args.command)
        if command[:1] == ["--"]:
            command = command[1:]
        if not command:
            raise AppContainerError("missing AppContainer child command")
        return run_container(args, command)
    except (AppContainerError, OSError, subprocess.SubprocessError) as exc:
        print(f"AppContainer error: {exc}", file=sys.stderr)
        return 125


if __name__ == "__main__":
    raise SystemExit(main())
