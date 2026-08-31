"""Trusted host-side Unix-socket broker for the Linux network namespace."""

from __future__ import annotations

import argparse
import os
import socket
import subprocess
import threading
from pathlib import Path
from urllib.parse import urlparse


class TransportError(RuntimeError):
    """Raised when the restricted Ollama transport cannot be created."""


def loopback_target(url: str) -> tuple[str, int]:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or parsed.hostname not in {
        "127.0.0.1",
        "::1",
        "localhost",
    }:
        raise TransportError("the transport target must be an HTTP(S) loopback URL")
    return parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80)


def _copy(source: socket.socket, destination: socket.socket) -> None:
    try:
        while True:
            chunk = source.recv(65536)
            if not chunk:
                break
            destination.sendall(chunk)
    except OSError:
        pass
    finally:
        try:
            destination.shutdown(socket.SHUT_WR)
        except OSError:
            pass


def _handle(client: socket.socket, target: tuple[str, int]) -> None:
    try:
        upstream = socket.create_connection(target, timeout=10)
    except OSError:
        client.close()
        return
    with client, upstream:
        first = threading.Thread(target=_copy, args=(client, upstream), daemon=True)
        second = threading.Thread(target=_copy, args=(upstream, client), daemon=True)
        first.start()
        second.start()
        first.join()
        second.join()


def _serve(listener: socket.socket, target: tuple[str, int], stop: threading.Event) -> None:
    listener.settimeout(0.2)
    while not stop.is_set():
        try:
            client, _ = listener.accept()
        except TimeoutError:
            continue
        except OSError:
            break
        threading.Thread(target=_handle, args=(client, target), daemon=True).start()


def run(socket_path: Path, url: str, command: list[str]) -> int:
    if os.name != "posix" or not hasattr(socket, "AF_UNIX"):
        raise TransportError("Unix sockets are unavailable on this platform")
    target = loopback_target(url)
    socket_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        socket_path.unlink(missing_ok=True)
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
            listener.bind(str(socket_path))
            socket_path.chmod(0o600)
            listener.listen(16)
            stop = threading.Event()
            server = threading.Thread(target=_serve, args=(listener, target, stop), daemon=True)
            server.start()
            try:
                child = subprocess.Popen(command)
                return child.wait()
            finally:
                stop.set()
                listener.close()
                server.join(timeout=1)
    finally:
        socket_path.unlink(missing_ok=True)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--socket", type=Path, required=True)
    parser.add_argument("--url", required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    command = list(args.command)
    if command[:1] == ["--"]:
        command = command[1:]
    if not command:
        raise SystemExit("missing child command")
    try:
        return run(args.socket, args.url, command)
    except (OSError, TransportError) as exc:
        raise SystemExit(f"sandbox transport error: {exc}") from exc


if __name__ == "__main__":
    raise SystemExit(main())
