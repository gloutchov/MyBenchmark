"""Optional operating-system sandbox selection and command construction."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse


SANDBOX_MODES = ("audit", "auto", "required")


class SandboxError(RuntimeError):
    """Raised when a requested enforced sandbox cannot be provided safely."""


@dataclass(frozen=True)
class SandboxSelection:
    requested_mode: str
    backend: str
    enforced: bool
    filesystem_isolation: bool
    process_isolation: bool
    network_isolation: bool
    detail: str
    deprecated_backend: bool = False

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class SandboxLaunch:
    command: tuple[str, ...]
    metadata: dict[str, object]


def _probe_command(command: list[str]) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, str(exc)
    if result.returncode == 0:
        return True, "probe riuscito"
    detail = (result.stderr or result.stdout).strip().splitlines()
    return False, detail[0] if detail else f"exit code {result.returncode}"


def _native_candidate(
    *,
    system: str,
    which: Callable[[str], str | None],
    probe: Callable[[list[str]], tuple[bool, str]],
) -> tuple[SandboxSelection | None, str]:
    if system == "Darwin":
        executable = which("sandbox-exec")
        if not executable:
            return None, "sandbox-exec non disponibile"
        ok, detail = probe([executable, "-p", "(version 1) (allow default)", "/usr/bin/true"])
        if not ok:
            return None, f"sandbox-exec non utilizzabile: {detail}"
        return (
            SandboxSelection(
                requested_mode="auto",
                backend="macos-seatbelt",
                enforced=True,
                filesystem_isolation=True,
                process_isolation=True,
                network_isolation=True,
                detail="Seatbelt limita file utente e rete; Ollama resta consentito solo su loopback",
                deprecated_backend=True,
            ),
            detail,
        )
    if system == "Linux":
        executable = which("bwrap")
        if not executable:
            return None, "bubblewrap (bwrap) non disponibile"
        ok, detail = probe(
            [
                executable,
                "--ro-bind",
                "/",
                "/",
                "--unshare-pid",
                "--die-with-parent",
                "/bin/true",
            ]
        )
        if not ok:
            return None, f"bubblewrap non utilizzabile: {detail}"
        return (
            SandboxSelection(
                requested_mode="auto",
                backend="linux-bubblewrap",
                enforced=True,
                filesystem_isolation=True,
                process_isolation=True,
                network_isolation=False,
                detail="bubblewrap nasconde i file utente esterni; la rete resta affidata a policy e audit per raggiungere Ollama",
            ),
            detail,
        )
    if system == "Windows":
        return None, "nessun backend AppContainer integrato in questa versione"
    return None, f"piattaforma non supportata: {system}"


def select_sandbox(
    requested_mode: str,
    *,
    system: str | None = None,
    which: Callable[[str], str | None] = shutil.which,
    probe: Callable[[list[str]], tuple[bool, str]] = _probe_command,
) -> SandboxSelection:
    if requested_mode not in SANDBOX_MODES:
        raise SandboxError(f"Modalità sandbox non valida: {requested_mode}")
    if requested_mode == "audit":
        return SandboxSelection(
            requested_mode="audit",
            backend="audit-only",
            enforced=False,
            filesystem_isolation=False,
            process_isolation=False,
            network_isolation=False,
            detail="policy, snapshot e audit post-run senza isolamento OS",
        )

    candidate, unavailable_detail = _native_candidate(
        system=system or platform.system(),
        which=which,
        probe=probe,
    )
    if candidate is not None:
        return SandboxSelection(**{**candidate.to_dict(), "requested_mode": requested_mode})
    if requested_mode == "required":
        raise SandboxError(f"Sandbox OS richiesta ma non disponibile: {unavailable_detail}")
    return SandboxSelection(
        requested_mode="auto",
        backend="audit-only",
        enforced=False,
        filesystem_isolation=False,
        process_isolation=False,
        network_isolation=False,
        detail=f"fallback esplicito ad audit-only: {unavailable_detail}",
    )


def sandbox_capability(
    *,
    system: str | None = None,
    which: Callable[[str], str | None] = shutil.which,
    probe: Callable[[list[str]], tuple[bool, str]] = _probe_command,
) -> dict[str, object]:
    candidate, detail = _native_candidate(system=system or platform.system(), which=which, probe=probe)
    if candidate is None:
        return {"available": False, "backend": None, "detail": detail}
    return {"available": True, "backend": candidate.backend, "detail": candidate.detail}


def _common_install_root(command_name: str) -> Path | None:
    executable = shutil.which(command_name)
    if not executable:
        return None
    link = Path(executable).resolve(strict=False)
    visible = Path(executable).resolve(strict=False)
    try:
        common = Path(os.path.commonpath((str(Path(executable)), str(link))))
    except ValueError:
        return visible.parent
    if common == Path(executable):
        return common.parent.parent if common.parent.name == "bin" else common.parent
    if common.suffix or common.name in {"bin", "lib"}:
        return common.parent
    return common


def _sbpl(value: str | Path) -> str:
    return json.dumps(str(value), ensure_ascii=False)


def _protected_metadata_ancestors(
    allowed_paths: list[Path],
    protected_roots: tuple[Path, ...],
) -> list[Path]:
    """Return exact protected ancestors needed to resolve allowed paths."""
    resolved_roots = tuple(root.resolve(strict=False) for root in protected_roots)
    ancestors: set[Path] = set()
    for path in allowed_paths:
        current = path.resolve(strict=False).parent
        while current != current.parent:
            if any(current == root or current.is_relative_to(root) for root in resolved_roots):
                ancestors.add(current)
            current = current.parent
    return sorted(ancestors, key=lambda item: (len(item.parts), str(item)))


def _macos_profile(
    workspace: Path,
    agent_dir: Path,
    ollama_url: str,
    pi_command: tuple[str, ...],
) -> str:
    parsed = urlparse(ollama_url)
    if parsed.scheme not in {"http", "https"} or parsed.hostname not in {"127.0.0.1", "::1", "localhost"}:
        raise SandboxError("Il backend macOS richiede ollama.url su loopback")
    if parsed.port is None:
        port = 443 if parsed.scheme == "https" else 80
    else:
        port = parsed.port
    home = Path.home().resolve(strict=False)
    install_root = _common_install_root(pi_command[0])
    readable = [workspace.resolve(), agent_dir.resolve()]
    if install_root is not None and install_root.is_relative_to(home):
        readable.append(install_root)
    protected_roots = (
        home,
        Path("/Volumes"),
        Path("/private/tmp"),
        Path("/private/var/folders"),
    )
    metadata_paths = _protected_metadata_ancestors(readable, protected_roots)
    metadata_rules = "\n".join(
        f"(allow file-read-metadata (literal {_sbpl(path)}))"
        for path in metadata_paths
    )
    allow_paths = "\n".join(
        f"(allow file-read* file-write* (subpath {_sbpl(path)}))" if path in {workspace.resolve(), agent_dir.resolve()}
        else f"(allow file-read* (subpath {_sbpl(path)}))"
        for path in readable
    )
    return (
        "(version 1)\n"
        "(allow default)\n"
        f"(deny file-read* file-write* (subpath {_sbpl(home)}))\n"
        "(deny file-read* file-write* (subpath \"/Volumes\"))\n"
        "(deny file-read* file-write* (subpath \"/private/tmp\"))\n"
        "(deny file-read* file-write* (subpath \"/private/var/folders\"))\n"
        f"{metadata_rules}\n"
        f"{allow_paths}\n"
        "(deny network-outbound)\n"
        f"(allow network-outbound (remote tcp {_sbpl(f'localhost:{port}')}))\n"
    )


def _bwrap_parent_directories(paths: tuple[Path, ...]) -> list[str]:
    directories: set[Path] = set()
    for path in paths:
        current = path.absolute().parent
        while current != current.parent:
            directories.add(current)
            current = current.parent
    return [str(path) for path in sorted(directories, key=lambda item: (len(item.parts), str(item)))]


def _linux_command(
    executable: str,
    command: tuple[str, ...],
    workspace: Path,
    agent_dir: Path,
    pi_command: tuple[str, ...],
) -> tuple[str, ...]:
    workspace = workspace.absolute()
    agent_dir = agent_dir.absolute()
    install_root = _common_install_root(pi_command[0])
    home = Path.home().resolve(strict=False)
    private_install = install_root if install_root is not None and install_root.is_relative_to(home) else None
    visible_paths = (workspace, agent_dir, *((private_install,) if private_install else ()))
    args: list[str] = [
        executable,
        "--unshare-pid",
        "--unshare-ipc",
        "--unshare-uts",
        "--die-with-parent",
        "--new-session",
        "--proc",
        "/proc",
        "--dev",
        "/dev",
        "--tmpfs",
        "/tmp",
    ]
    for system_path in ("/usr", "/bin", "/sbin", "/lib", "/lib64", "/etc", "/opt", "/nix"):
        args.extend(("--ro-bind-try", system_path, system_path))
    for parent in _bwrap_parent_directories(visible_paths):
        args.extend(("--dir", parent))
    if private_install is not None:
        args.extend(("--ro-bind", str(private_install), str(private_install)))
    args.extend(("--bind", str(agent_dir), str(agent_dir)))
    args.extend(("--bind", str(workspace), str(workspace)))
    args.extend(("--setenv", "HOME", str(workspace), "--chdir", str(workspace), "--"))
    args.extend(command)
    return tuple(args)


def prepare_sandbox_launch(
    selection: SandboxSelection,
    command: list[str],
    *,
    workspace: Path,
    agent_dir: Path,
    ollama_url: str,
    pi_command: tuple[str, ...],
) -> SandboxLaunch:
    metadata = selection.to_dict()
    if selection.backend == "audit-only":
        return SandboxLaunch(tuple(command), metadata)
    if selection.backend == "macos-seatbelt":
        executable = shutil.which("sandbox-exec")
        if not executable:
            raise SandboxError("sandbox-exec non è più disponibile")
        profile = _macos_profile(workspace, agent_dir, ollama_url, pi_command)
        profile_path = workspace / ".benchmark-scratch" / "sandbox.sb"
        profile_path.parent.mkdir(parents=True, exist_ok=True)
        profile_path.write_text(profile, encoding="utf-8")
        metadata.update(
            {
                "profile_sha256": hashlib.sha256(profile.encode("utf-8")).hexdigest(),
                "profile_path": str(profile_path.relative_to(workspace)),
            }
        )
        return SandboxLaunch((executable, "-f", str(profile_path), *command), metadata)
    if selection.backend == "linux-bubblewrap":
        executable = shutil.which("bwrap")
        if not executable:
            raise SandboxError("bubblewrap non è più disponibile")
        return SandboxLaunch(
            _linux_command(executable, tuple(command), workspace, agent_dir, pi_command),
            metadata,
        )
    raise SandboxError(f"Backend sandbox sconosciuto: {selection.backend}")
