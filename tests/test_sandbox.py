from __future__ import annotations

import json
import socket
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from localagent_bench.sandbox import (
    SandboxError,
    SandboxSelection,
    _linux_command,
    prepare_sandbox_launch,
    select_sandbox,
)


def successful_probe(_command: list[str]) -> tuple[bool, str]:
    return True, "ok"


class SandboxTests(unittest.TestCase):
    def test_audit_mode_is_explicitly_unenforced(self):
        selection = select_sandbox("audit")
        self.assertEqual("audit-only", selection.backend)
        self.assertFalse(selection.enforced)
        self.assertFalse(selection.filesystem_isolation)

    def test_auto_falls_back_but_required_fails_without_backend(self):
        fallback = select_sandbox("auto", system="Windows", which=lambda _name: None)
        self.assertEqual("audit-only", fallback.backend)
        self.assertIn("fallback esplicito", fallback.detail)
        with self.assertRaises(SandboxError):
            select_sandbox("required", system="Windows", which=lambda _name: None)

    def test_native_capabilities_are_not_overstated(self):
        mac = select_sandbox(
            "required",
            system="Darwin",
            which=lambda name: "/usr/bin/sandbox-exec" if name == "sandbox-exec" else None,
            probe=successful_probe,
        )
        self.assertTrue(mac.filesystem_isolation)
        self.assertTrue(mac.network_isolation)
        self.assertTrue(mac.deprecated_backend)

        linux = select_sandbox(
            "required",
            system="Linux",
            which=lambda name: "/usr/bin/bwrap" if name == "bwrap" else None,
            probe=successful_probe,
        )
        self.assertTrue(linux.filesystem_isolation)
        self.assertTrue(linux.process_isolation)
        self.assertFalse(linux.network_isolation)

    @patch("localagent_bench.sandbox.shutil.which", return_value="/usr/bin/sandbox-exec")
    def test_macos_launch_records_profile_and_loopback_policy(self, _which_mock):
        selection = SandboxSelection(
            "required", "macos-seatbelt", True, True, True, True, "test", True
        )
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            root = Path(directory)
            workspace = root / "workspace"
            agent_dir = root / "agent"
            workspace.mkdir()
            agent_dir.mkdir()
            launch = prepare_sandbox_launch(
                selection,
                ["pi", "--offline"],
                workspace=workspace,
                agent_dir=agent_dir,
                ollama_url="http://127.0.0.1:11434",
                pi_command=("pi",),
            )
            profile = workspace / ".benchmark-scratch" / "sandbox.sb"
            self.assertTrue(profile.is_file())
            content = profile.read_text(encoding="utf-8")
            self.assertIn("(deny network-outbound)", content)
            self.assertIn('localhost:11434', content)
            self.assertIn("(allow file-read-metadata (literal", content)
            self.assertIn(json.dumps(str(workspace)), content)
            self.assertEqual("sandbox.sb", launch.metadata["profile_path"].split("/")[-1])
            self.assertEqual(64, len(str(launch.metadata["profile_sha256"])))

    @patch("localagent_bench.sandbox._common_install_root", return_value=None)
    def test_linux_command_mounts_only_explicit_user_paths(self, _install_mock):
        workspace = Path("/home/test/run/workspace").absolute()
        agent_dir = Path("/home/test/run/agent").absolute()
        command = _linux_command(
            "/usr/bin/bwrap",
            ("pi",),
            workspace,
            agent_dir,
            ("pi",),
        )
        rendered = " ".join(command)
        self.assertIn(f"--bind {workspace} {workspace}", rendered)
        self.assertIn(f"--bind {agent_dir} {agent_dir}", rendered)
        self.assertNotIn(f"--ro-bind {workspace.parent.parent.parent} {workspace.parent.parent.parent}", rendered)
        self.assertIn("--unshare-pid", command)
        self.assertNotIn("--unshare-net", command)

    @unittest.skipUnless(sys.platform == "darwin" and shutil.which("sandbox-exec"), "richiede sandbox-exec")
    def test_macos_backend_blocks_indirect_child_read_outside_workspace(self):
        probe = subprocess.run(
            ["sandbox-exec", "-p", "(version 1) (allow default)", "/usr/bin/true"],
            capture_output=True,
            text=True,
            check=False,
        )
        if probe.returncode != 0:
            self.skipTest("sandbox-exec presente ma non utilizzabile in questo ambiente")
        selection = select_sandbox("required")
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            root = Path(directory)
            workspace = root / "workspace"
            agent_dir = root / "agent"
            workspace.mkdir()
            agent_dir.mkdir()
            inside = workspace / "inside.txt"
            outside = root / "outside.txt"
            inside.write_text("inside", encoding="utf-8")
            outside.write_text("outside", encoding="utf-8")
            code = (
                "from pathlib import Path; import sys; "
                "assert Path(sys.argv[1]).read_text() == 'inside'; "
                "Path(sys.argv[2]).read_text()"
            )
            launch = prepare_sandbox_launch(
                selection,
                [sys.executable, "-c", code, str(inside), str(outside)],
                workspace=workspace,
                agent_dir=agent_dir,
                ollama_url="http://127.0.0.1:11434",
                pi_command=(sys.executable,),
            )
            result = subprocess.run(
                launch.command,
                cwd=workspace,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(0, result.returncode)
            self.assertIn("Operation not permitted", result.stderr)

    @unittest.skipUnless(sys.platform == "darwin" and shutil.which("sandbox-exec"), "richiede sandbox-exec")
    def test_macos_backend_allows_only_configured_loopback_port(self):
        probe = subprocess.run(
            ["sandbox-exec", "-p", "(version 1) (allow default)", "/usr/bin/true"],
            capture_output=True,
            text=True,
            check=False,
        )
        if probe.returncode != 0:
            self.skipTest("sandbox-exec presente ma non utilizzabile in questo ambiente")
        with socket.socket() as allowed_server, socket.socket() as denied_server:
            allowed_server.bind(("127.0.0.1", 0))
            denied_server.bind(("127.0.0.1", 0))
            allowed_server.listen(1)
            denied_server.listen(1)
            allowed_port = int(allowed_server.getsockname()[1])
            denied_port = int(denied_server.getsockname()[1])
            selection = select_sandbox("required")
            with tempfile.TemporaryDirectory(dir=ROOT) as directory:
                root = Path(directory)
                workspace = root / "workspace"
                agent_dir = root / "agent"
                workspace.mkdir()
                agent_dir.mkdir()
                code = (
                    "import socket, sys; "
                    "first=socket.create_connection(('127.0.0.1', int(sys.argv[1])), 2); first.close(); "
                    "\ntry: socket.create_connection(('127.0.0.1', int(sys.argv[2])), 2)\n"
                    "except PermissionError: raise SystemExit(0)\n"
                    "raise SystemExit(9)"
                )
                launch = prepare_sandbox_launch(
                    selection,
                    [sys.executable, "-c", code, str(allowed_port), str(denied_port)],
                    workspace=workspace,
                    agent_dir=agent_dir,
                    ollama_url=f"http://127.0.0.1:{allowed_port}",
                    pi_command=(sys.executable,),
                )
                result = subprocess.run(
                    launch.command,
                    cwd=workspace,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(0, result.returncode, result.stderr)


if __name__ == "__main__":
    unittest.main()
