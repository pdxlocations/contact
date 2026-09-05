from contextlib import ExitStack
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import contact.ui.default_config
from contact.utilities import input_handlers
from tests.test_support import reset_singletons


class RestoredSettingsTests(unittest.TestCase):
    def test_blank_input_is_unset_only_when_allowed(self):
        for keys, allowed, expected in [
            (["\n"], True, ""), ([" ", " ", "\n"], True, ""),
            (["\x1b"], True, None), (["\n", "\x1b"], False, None),
        ]:
            with self.subTest(keys=keys, allowed=allowed), ExitStack() as stack:
                reset_singletons()
                stack.callback(reset_singletons)
                win = mock.Mock()
                win.get_wch.side_effect = keys
                stack.enter_context(mock.patch.object(input_handlers.curses, "newwin", return_value=win))
                for name, value in (("LINES", 24), ("COLS", 80)):
                    stack.enter_context(mock.patch.object(input_handlers.curses, name, value, create=True))
                stack.enter_context(mock.patch.object(input_handlers.curses, "curs_set"))
                stack.enter_context(mock.patch.object(input_handlers, "get_color", return_value=0))
                invalid = stack.enter_context(mock.patch.object(input_handlers, "invalid_input"))
                result = input_handlers.get_text_input("Channel name", "name", str, allow_empty=allowed)
                self.assertEqual(result, expected)
                self.assertEqual(invalid.call_count, 0 if allowed else 1)

    def test_missing_log_path_shows_configuration_guidance(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            config_path = root / "config.json"
            log_path = root / "missing" / "client.log"
            for module in ("contact", "contact.settings"):
                with self.subTest(module=module):
                    config_path.write_text(json.dumps({"log_file_path": str(log_path)}))
                    result = subprocess.run(
                        [sys.executable, "-m", module],
                        env={**os.environ, "CONTACT_CONFIG_ROOT": str(root)},
                        cwd=Path(__file__).resolve().parents[1],
                        capture_output=True, text=True, timeout=15,
                    )
                    self.assertEqual(result.returncode, 1)
                    self.assertIn(str(log_path), result.stderr)
                    self.assertIn(f"Please edit config.json at: {config_path}", result.stderr)
                    self.assertIn('"log_file_path"', result.stderr)
                    self.assertNotIn("Traceback", result.stdout + result.stderr)
