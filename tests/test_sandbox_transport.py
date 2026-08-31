from __future__ import annotations

import os
import shutil
import socket
import sys
import tempfile
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from localagent_bench.sandbox import _network_shim
from localagent_bench.sandbox_transport import TransportError, loopback_target, run


class SandboxTransportTests(unittest.TestCase):
    def test_target_requires_loopback(self):
        self.assertEqual(("127.0.0.1", 11434), loopback_target("http://127.0.0.1:11434"))
        with self.assertRaises(TransportError):
            loopback_target("https://example.invalid:11434")

    @unittest.skipUnless(os.name == "posix" and shutil.which("node"), "richiede Unix socket e Node")
    def test_node_shim_reaches_only_fixed_target_through_unix_socket(self):
        with socket.socket() as upstream:
            try:
                upstream.bind(("127.0.0.1", 0))
            except PermissionError:
                self.skipTest("il sandbox del test runner vieta anche il loopback locale")
            upstream.listen(1)
            port = int(upstream.getsockname()[1])

            def serve() -> None:
                connection, _ = upstream.accept()
                with connection:
                    self.assertEqual(b"ping", connection.recv(4))
                    connection.sendall(b"pong")

            server = threading.Thread(target=serve, daemon=True)
            server.start()
            with tempfile.TemporaryDirectory(dir=ROOT) as directory:
                root = Path(directory)
                socket_path = root / "ollama.sock"
                shim = root / "network-shim.cjs"
                _network_shim(shim, "127.0.0.1", port, str(socket_path))
                code = (
                    "const net=require('node:net');"
                    f"const client=net.connect({port},'127.0.0.1',()=>client.write('ping'));"
                    "client.once('data',data=>process.exit(data.toString()==='pong'?0:8));"
                    "client.once('error',error=>{console.error(error);process.exit(9)});"
                )
                command = [
                    shutil.which("env") or "/usr/bin/env",
                    f"NODE_OPTIONS=--require={shim}",
                    shutil.which("node") or "node",
                    "-e",
                    code,
                ]
                self.assertEqual(0, run(socket_path, f"http://127.0.0.1:{port}", command))
            server.join(timeout=2)
            self.assertFalse(server.is_alive())


if __name__ == "__main__":
    unittest.main()
