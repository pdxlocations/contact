import unittest
import json
from contextlib import ExitStack
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory
from types import SimpleNamespace
from unittest import mock

import contact.ui.default_config  # Initialize config before the color helpers.
from contact.ui import user_config


class UserConfigTests(unittest.TestCase):
    def test_editor_reads_and_saves_active_config_outside_installation(self):
        for existing in (False, True):
            with self.subTest(existing=existing), TemporaryDirectory() as directory, ExitStack() as stack:
                root = Path(directory)
                config_path = root / "config.json"
                package = root / "site-packages" / "contact"
                (package / "ui").mkdir(parents=True)
                if existing:
                    config_path.write_text(json.dumps({"message_prefix": "Custom"}), encoding="utf-8")
                stack.enter_context(mock.patch.object(user_config, "__file__", str(package / "ui" / "user_config.py")))
                stack.enter_context(mock.patch.object(user_config.config, "json_file_path", str(config_path)))
                reload_config = stack.enter_context(mock.patch.object(user_config.config, "reload_config"))
                stack.enter_context(mock.patch.object(user_config, "reload_translations"))
                stack.enter_context(mock.patch.object(user_config, "update_app_settings_help"))
                window = mock.Mock()
                state = SimpleNamespace()
                stack.enter_context(mock.patch.object(user_config, "display_menu", return_value=(window, mock.Mock(), [])))

                def save_from_editor():
                    self.assertEqual(state.current_menu["message_prefix"], "Custom" if existing else ">>")
                    state.current_menu["message_prefix"] = "Edited"
                    return 10  # Save button.

                window.getch.side_effect = save_from_editor
                self.assertFalse(user_config.json_editor(mock.Mock(), state))
                self.assertEqual(json.loads(config_path.read_text())["message_prefix"], "Edited")
                self.assertFalse((package / "config.json").exists())
                reload_config.assert_called_once_with()

    def test_ping_bot_enabled_uses_boolean_picker(self) -> None:
        with mock.patch.object(user_config, "get_list_input", return_value="True") as picker:
            result = user_config.edit_value("enabled", "Enabled", "False")

        self.assertEqual(result, "True")
        picker.assert_called_once_with("Enabled", "False", ["True", "False"])

    def test_load_log_tail_returns_only_requested_recent_lines(self) -> None:
        with NamedTemporaryFile("w") as log_file:
            log_file.write("".join(f"line {index}\n" for index in range(600)))
            log_file.flush()

            lines = user_config.load_log_tail(log_file.name, max_lines=500)

        self.assertEqual(len(lines), 500)
        self.assertEqual(lines[0], "line 100")
        self.assertEqual(lines[-1], "line 599")


if __name__ == "__main__":
    unittest.main()
