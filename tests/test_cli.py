import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

import contact.__main__ as cli
import contact.settings as settings_cli
from contact.version import __version__


class CliTests(unittest.TestCase):
    def test_help_version_and_errors_work_without_runtime_configuration(self) -> None:
        cases = [
            (["--help"], 0, "usage:"),
            (["-h"], 0, "usage:"),
            (["--version"], 0, __version__),
            (["-V"], 0, __version__),
            (["--unknown"], 2, "unrecognized arguments"),
            (["--host", "localhost", "--ble"], 2, "not allowed with argument"),
            (["--", "--version"], 2, "unrecognized arguments"),
        ]
        with tempfile.TemporaryDirectory() as directory:
            config_root = Path(directory) / "missing"
            env = dict(os.environ, CONTACT_CONFIG_ROOT=str(config_root))
            for command in (["-m", "contact"], ["-m", "contact.settings"],
                            ["-c", "from contact.__main__ import start; start()"]):
                for flags, code, expected in cases:
                    with self.subTest(command=command, flags=flags):
                        result = subprocess.run(
                            [sys.executable, *command, *flags], env=env,
                            capture_output=True, text=True, timeout=10,
                        )
                        self.assertEqual(result.returncode, code, result.stderr)
                        self.assertIn(expected, result.stderr if code else result.stdout)
                        self.assertEqual(result.stdout if code else result.stderr, "")
                        self.assertFalse(config_root.exists())

    def test_control_aliases_preserve_connection_options(self) -> None:
        for alias in ("--settings", "--set", "--control", "-c"):
            for connection, value, attribute in (
                ("--host", "mesh.local", "host"),
                ("--port", "/dev/ttyUSB0", "port"),
                ("--ble", "my-radio", "ble"),
            ):
                with self.subTest(alias=alias, connection=connection):
                    runtime = SimpleNamespace(start=mock.Mock())
                    with mock.patch.dict(sys.modules, {"contact.settings_runtime": runtime}):
                        cli.start([alias, connection, value])
                    runtime.start.assert_called_once()
                    self.assertEqual(getattr(runtime.start.call_args.args[0], attribute), value)

    def test_main_and_standalone_settings_pass_parsed_options(self) -> None:
        for entrypoint, module in ((cli, "contact.runtime"),
                                   (settings_cli, "contact.settings_runtime")):
            runtime = SimpleNamespace(start=mock.Mock())
            with mock.patch.dict(sys.modules, {module: runtime}):
                entrypoint.start(["--host=mesh.local"])
            runtime.start.assert_called_once()
            self.assertEqual(runtime.start.call_args.args[0].host, "mesh.local")
