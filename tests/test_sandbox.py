from __future__ import annotations

import json
import os
import socket
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from localagent_bench.sandbox import (
    SandboxError,
    SandboxSelection,
    _linux_command,
    prepare_sandbox_launch,
    select_sandbox,
)
from localagent_bench.windows_appcontainer import (
    PIPE_CLIENT_READ_WRITE,
    AppContainerError,
    _appcontainer_pipe_path,
    _connect_upstream,
    _npm_pi_command,
    _patch_windows_pi_shell,
    _pipe_sddl,
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
        failed_probe = lambda _command: (False, "backend unavailable")
        fallback = select_sandbox(
            "auto", system="Windows", which=lambda _name: None, probe=failed_probe
        )
        self.assertEqual("audit-only", fallback.backend)
        self.assertIn("fallback esplicito", fallback.detail)
        with self.assertRaises(SandboxError):
            select_sandbox(
                "required", system="Windows", which=lambda _name: None, probe=failed_probe
            )

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
            which=lambda name: f"/usr/bin/{name}" if name in {"bwrap", "unshare"} else None,
            probe=successful_probe,
        )
        self.assertTrue(linux.filesystem_isolation)
        self.assertTrue(linux.process_isolation)
        self.assertTrue(linux.network_isolation)

        windows = select_sandbox(
            "required",
            system="Windows",
            probe=successful_probe,
        )
        self.assertEqual("windows-appcontainer", windows.backend)
        self.assertTrue(windows.filesystem_isolation)
        self.assertTrue(windows.process_isolation)
        self.assertTrue(windows.network_isolation)

    @patch("localagent_bench.sandbox.shutil.which", return_value="/usr/bin/sandbox-exec")
    @patch("localagent_bench.sandbox.Path.home")
    def test_macos_launch_records_profile_and_loopback_policy(self, home_mock, _which_mock):
        selection = SandboxSelection(
            "required", "macos-seatbelt", True, True, True, True, "test", True
        )
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            root = Path(directory)
            home_mock.return_value = root
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
            self.assertIn(
                f"(allow file-read-metadata (literal {json.dumps(str(workspace.parent))}))",
                content,
            )
            self.assertNotIn(
                f"(allow file-read* (subpath {json.dumps(str(workspace.parent))}))",
                content,
            )
            self.assertEqual("sandbox.sb", Path(str(launch.metadata["profile_path"])).name)
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
        self.assertIn("--cap-drop", command)
        self.assertNotIn("--unshare-net", command)

    @patch(
        "localagent_bench.sandbox.shutil.which",
        side_effect=lambda name: f"/usr/bin/{name}" if name in {"bwrap", "unshare"} else None,
    )
    @patch("localagent_bench.sandbox._common_install_root", return_value=None)
    def test_linux_launch_uses_fixed_unix_transport_and_node_shim(self, _install_mock, _which_mock):
        selection = SandboxSelection(
            "required", "linux-bubblewrap", True, True, True, True, "test"
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
            self.assertIn("sandbox_transport.py", " ".join(launch.command))
            self.assertIn("--net", launch.command)
            self.assertIn("--map-root-user", launch.command)
            self.assertNotIn("--unshare-net", launch.command)
            self.assertEqual("workspace-unix-socket", launch.metadata["network_transport"])
            self.assertEqual("127.0.0.1:11434", launch.metadata["network_target"])
            self.assertIn("--import=data:text/javascript;base64,", launch.environment["NODE_OPTIONS"])
            self.assertEqual(64, len(str(launch.metadata["network_shim_sha256"])))

    def test_windows_pipe_acl_requires_owner_and_exact_appcontainer(self):
        owner = "S-1-5-21-1-2-3-1001"
        package = "S-1-15-2-1234"
        sddl = _pipe_sddl(owner, package)
        self.assertEqual(
            f"D:P(A;;GA;;;{owner})(A;;0x{PIPE_CLIENT_READ_WRITE:08x};;;{package})",
            sddl,
        )
        self.assertNotIn(";;;S-1-15-2-1)", sddl)

    @patch("localagent_bench.sandbox._probe_command", return_value=(True, "ok"))
    def test_windows_launch_uses_appcontainer_without_network_capabilities(self, _probe_mock):
        selection = SandboxSelection(
            "required", "windows-appcontainer", True, True, True, True, "test"
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
                timeout_seconds=60,
            )
            rendered = " ".join(launch.command)
            self.assertIn("windows_appcontainer.py run", rendered)
            self.assertIn("--pipe-name LocalAgentBenchmark-", rendered)
            self.assertIn("--timeout 60", rendered)
            self.assertEqual("appcontainer-named-pipe", launch.metadata["network_transport"])
            self.assertIn("--import=data:text/javascript;base64,", launch.environment["NODE_OPTIONS"])
            wrapper = root / "pi.cmd"
            cli = (
                root
                / "node_modules"
                / "@earendil-works"
                / "pi-coding-agent"
                / "dist"
                / "bundle"
                / "cli.js"
            )
            cli.parent.mkdir(parents=True)
            cli.write_text("", encoding="utf-8")
            with patch(
                "localagent_bench.windows_appcontainer.shutil.which",
                return_value=str(root / "node.exe"),
            ):
                self.assertEqual(
                    [str(root / "node.exe"), str(cli), "--offline"],
                    _npm_pi_command(wrapper, ["--offline"]),
                )

    def test_windows_host_pipe_targets_exact_appcontainer_namespace(self):
        path = _appcontainer_pipe_path("broker", "S-1-15-2-1234", 7)
        self.assertEqual(
            r"\\?\pipe\Sessions\7\AppContainerNamedObjects\S-1-15-2-1234\broker",
            path,
        )
        with self.assertRaises(AppContainerError):
            _appcontainer_pipe_path(r"nested\broker", "S-1-15-2-1234", 7)

    def test_windows_broker_uses_timeout_only_for_upstream_connection(self):
        upstream = MagicMock()
        with patch(
            "localagent_bench.windows_appcontainer.socket.create_connection",
            return_value=upstream,
        ) as connect:
            self.assertIs(upstream, _connect_upstream(("127.0.0.1", 11434)))
        connect.assert_called_once_with(("127.0.0.1", 11434), timeout=10)
        upstream.settimeout.assert_called_once_with(None)

    def test_windows_staged_pi_bundle_uses_cmd_shell(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            dist = Path(directory)
            chunks = dist / "bundle" / "chunks"
            chunks.mkdir(parents=True)
            chunk = chunks / "chunk.js"
            chunk.write_text(
                'if(process.platform==="win32"){let paths=[];'
                'snippet:"Execute bash commands (ls, grep, find, etc.)";'
                'let shellConfig=resolveShellConfig();try{await fsAccess(cwd,constants2.F_OK);'
                'stdio:[commandFromStdin?"pipe":"ignore","pipe","pipe"];'
                'let exitCode=await waitForChildProcess(child);if(signal?.aborted)',
                encoding="utf-8",
            )
            _patch_windows_pi_shell(dist)
            patched = chunk.read_text(encoding="utf-8")
            self.assertIn('shell:process.env.ComSpec??"cmd.exe"', patched)
            self.assertIn('args:["/d","/v:on","/s","/c"]', patched)
            self.assertIn("Execute Windows cmd.exe commands", patched)
            self.assertIn('stdio:process.platform==="win32"?"inherit"', patched)
            self.assertIn("process.getBuiltinModule", patched)

    def test_enforced_transport_rejects_non_loopback_ollama(self):
        selection = SandboxSelection(
            "required", "linux-bubblewrap", True, True, True, True, "test"
        )
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            root = Path(directory)
            workspace = root / "workspace"
            agent_dir = root / "agent"
            workspace.mkdir()
            agent_dir.mkdir()
            with self.assertRaises(SandboxError):
                prepare_sandbox_launch(
                    selection,
                    ["pi"],
                    workspace=workspace,
                    agent_dir=agent_dir,
                    ollama_url="https://example.invalid:11434",
                    pi_command=("pi",),
                )

    @unittest.skipUnless(
        sys.platform.startswith("linux")
        and shutil.which("bwrap")
        and shutil.which("unshare")
        and shutil.which("node"),
        "richiede Linux, bubblewrap, unshare e Node",
    )
    def test_linux_backend_enforces_network_namespace_with_fixed_ollama_broker(self):
        selection = select_sandbox("required")
        with socket.socket() as allowed_server, socket.socket() as denied_server:
            allowed_server.bind(("127.0.0.1", 0))
            denied_server.bind(("127.0.0.1", 0))
            allowed_server.listen(1)
            denied_server.listen(1)
            allowed_port = int(allowed_server.getsockname()[1])
            denied_port = int(denied_server.getsockname()[1])

            def serve() -> None:
                connection, _ = allowed_server.accept()
                with connection:
                    if connection.recv(4) == b"ping":
                        connection.sendall(b"pong")

            server = threading.Thread(target=serve, daemon=True)
            server.start()
            with tempfile.TemporaryDirectory(dir=ROOT) as directory:
                root = Path(directory)
                workspace = root / "workspace"
                agent_dir = root / "agent"
                workspace.mkdir()
                agent_dir.mkdir()
                node = shutil.which("node")
                assert node is not None
                code = (
                    "const net=require('node:net');"
                    f"const ok=net.connect({allowed_port},'127.0.0.1',()=>ok.write('ping'));"
                    "ok.setTimeout(5000,()=>process.exit(10));"
                    "ok.once('data',data=>{if(data.toString()!=='pong')process.exit(7);"
                    f"const denied=net.connect({denied_port},'127.0.0.1');"
                    "denied.setTimeout(3000,()=>process.exit(0));"
                    "denied.once('connect',()=>process.exit(8));"
                    "denied.once('error',()=>process.exit(0));});"
                    "ok.once('error',error=>{console.error(error);process.exit(9)});"
                )
                launch = prepare_sandbox_launch(
                    selection,
                    [node, "-e", code],
                    workspace=workspace,
                    agent_dir=agent_dir,
                    ollama_url=f"http://127.0.0.1:{allowed_port}",
                    pi_command=(node,),
                )
                env = os.environ.copy()
                env.update(launch.environment)
                result = subprocess.run(
                    launch.command,
                    cwd=workspace,
                    env=env,
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=30,
                )
                self.assertEqual(0, result.returncode, result.stderr)
            server.join(timeout=2)
            self.assertFalse(server.is_alive())

    @unittest.skipUnless(sys.platform == "win32", "richiede Windows")
    def test_windows_backend_blocks_external_file_and_cleans_profile(self):
        selection = select_sandbox("required")
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            root = Path(directory)
            workspace = root / "workspace"
            agent_dir = root / "agent"
            workspace.mkdir()
            agent_dir.mkdir()
            inside = workspace / "inside.txt"
            outside = root / "outside.txt"
            outside.write_text("private", encoding="utf-8")
            code = (
                "from pathlib import Path; import os, subprocess, sys; "
                "assert Path.cwd() == Path(sys.argv[3]); "
                "subprocess.run([os.environ['COMSPEC'], '/d', '/s', '/c', "
                "'echo child>child.txt'], check=True, timeout=5); "
                "Path(sys.argv[4]).write_text('scratch', encoding='utf-8'); "
                "Path(sys.argv[1]).write_text('inside', encoding='utf-8'); "
                "\ntry: Path(sys.argv[2]).read_text(encoding='utf-8')\n"
                "except (PermissionError, OSError): raise SystemExit(0)\n"
                "raise SystemExit(9)"
            )
            launch = prepare_sandbox_launch(
                selection,
                [
                    sys.executable,
                    "-c",
                    code,
                    str(inside),
                    str(outside),
                    str(workspace),
                    str(workspace / ".benchmark-scratch" / "python.txt"),
                ],
                workspace=workspace,
                agent_dir=agent_dir,
                ollama_url="http://127.0.0.1:11434",
                pi_command=(sys.executable,),
            )
            env = os.environ.copy()
            env.update(launch.environment)
            result = subprocess.run(
                launch.command,
                cwd=workspace,
                env=env,
                capture_output=True,
                text=True,
                check=False,
                timeout=90,
            )
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual("inside", inside.read_text(encoding="utf-8"))
            self.assertEqual("child", (workspace / "child.txt").read_text(encoding="utf-8").strip())
            self.assertEqual(
                "scratch",
                (workspace / ".benchmark-scratch" / "python.txt").read_text(encoding="utf-8"),
            )
            metadata = json.loads(
                (workspace / ".benchmark-scratch" / "windows-sandbox.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual([], metadata["network_capabilities"])
            self.assertTrue(metadata["job_kill_on_close"])
            self.assertTrue(metadata["acl_removed"])
            self.assertTrue(metadata["profile_deleted"])

    @unittest.skipUnless(sys.platform == "win32" and shutil.which("node"), "richiede Windows e Node")
    def test_windows_backend_node_child_runs_cmd_shell(self):
        selection = select_sandbox("required")
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            root = Path(directory)
            workspace = root / "workspace"
            agent_dir = root / "agent"
            workspace.mkdir()
            agent_dir.mkdir()
            node = shutil.which("node")
            assert node is not None
            code = (
                "const fs=require('fs');"
                "const {spawn}=require('child_process');"
                "const output='.benchmark-scratch/shell-output.log';"
                "const child=spawn(process.env.ComSpec,"
                "['/d','/v:on','/s','/c',"
                "`(echo staged) > ${output} 2>&1 & echo !errorlevel! > ${output}.exit`],"
                "{stdio:'inherit',windowsHide:true});"
                "child.on('error',error=>{console.error(error);process.exit(8)});"
                "child.on('exit',code=>{"
                "const reported=Number(fs.readFileSync(output+'.exit','utf8').trim());"
                "if(reported===0)fs.writeFileSync('shell.txt',fs.readFileSync(output));"
                "else console.error('cmd exit',code,'reported',reported);"
                "fs.rmSync(output,{force:true});fs.rmSync(output+'.exit',{force:true});"
                "process.exit(reported)});"
                "setTimeout(()=>process.exit(10),5000);"
            )
            launch = prepare_sandbox_launch(
                selection,
                [node, "-e", code],
                workspace=workspace,
                agent_dir=agent_dir,
                ollama_url="http://127.0.0.1:11434",
                pi_command=(node,),
                timeout_seconds=20,
            )
            result = subprocess.run(
                launch.command,
                cwd=workspace,
                capture_output=True,
                text=True,
                check=False,
                timeout=60,
            )
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual("staged", (workspace / "shell.txt").read_text(encoding="utf-8").strip())

    @unittest.skipUnless(sys.platform == "win32" and shutil.which("node"), "richiede Windows e Node")
    def test_windows_backend_routes_only_ollama_through_named_pipe(self):
        selection = select_sandbox("required")
        with socket.socket() as allowed_server, socket.socket() as denied_server:
            allowed_server.bind(("127.0.0.1", 0))
            denied_server.bind(("127.0.0.1", 0))
            allowed_server.listen(1)
            denied_server.listen(1)
            allowed_port = int(allowed_server.getsockname()[1])
            denied_port = int(denied_server.getsockname()[1])

            def serve() -> None:
                connection, _ = allowed_server.accept()
                with connection:
                    if connection.recv(4) == b"ping":
                        connection.sendall(b"pong")

            server = threading.Thread(target=serve, daemon=True)
            server.start()
            with tempfile.TemporaryDirectory(dir=ROOT) as directory:
                root = Path(directory)
                workspace = root / "workspace"
                agent_dir = root / "agent"
                workspace.mkdir()
                agent_dir.mkdir()
                node = shutil.which("node")
                assert node is not None
                code = (
                    "const net=require('node:net');"
                    f"const ok=net.connect({allowed_port},'127.0.0.1',()=>ok.write('ping'));"
                    "ok.setTimeout(5000,()=>process.exit(10));"
                    "ok.once('data',data=>{if(data.toString()!=='pong')process.exit(7);"
                    f"const denied=net.connect({denied_port},'127.0.0.1');"
                    "denied.setTimeout(3000,()=>process.exit(0));"
                    "denied.once('connect',()=>process.exit(8));"
                    "denied.once('error',()=>process.exit(0));});"
                    "ok.once('error',error=>{console.error(error);process.exit(9)});"
                )
                launch = prepare_sandbox_launch(
                    selection,
                    [node, "-e", code],
                    workspace=workspace,
                    agent_dir=agent_dir,
                    ollama_url=f"http://127.0.0.1:{allowed_port}",
                    pi_command=(node,),
                )
                env = os.environ.copy()
                env.update(launch.environment)
                result = subprocess.run(
                    launch.command,
                    cwd=workspace,
                    env=env,
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=90,
                )
                metadata_path = workspace / ".benchmark-scratch" / "windows-sandbox.json"
                diagnostic = result.stderr
                if metadata_path.is_file():
                    diagnostic += metadata_path.read_text(encoding="utf-8")
                self.assertEqual(0, result.returncode, diagnostic)
            server.join(timeout=2)
            self.assertFalse(server.is_alive())

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

    @unittest.skipUnless(
        sys.platform == "darwin" and shutil.which("sandbox-exec") and shutil.which("node"),
        "richiede sandbox-exec e Node",
    )
    def test_macos_backend_allows_node_realpath_and_internal_writes(self):
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
            inside.write_text("before", encoding="utf-8")
            outside.write_text("outside", encoding="utf-8")
            code = (
                "const fs = require('fs'); "
                "const inside = process.argv[1]; const outside = process.argv[2]; "
                "fs.realpathSync(inside); "
                "const temporary = inside + '.tmp'; "
                "fs.writeFileSync(temporary, 'after', 'utf8'); "
                "fs.renameSync(temporary, inside); "
                "try { fs.realpathSync(outside); process.exit(9); } "
                "catch (error) { if (!['EPERM', 'EACCES'].includes(error.code)) throw error; }"
            )
            node = shutil.which("node")
            assert node is not None
            launch = prepare_sandbox_launch(
                selection,
                [node, "-e", code, str(inside), str(outside)],
                workspace=workspace,
                agent_dir=agent_dir,
                ollama_url="http://127.0.0.1:11434",
                pi_command=(node,),
            )
            result = subprocess.run(
                launch.command,
                cwd=workspace,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual("after", inside.read_text(encoding="utf-8"))

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
