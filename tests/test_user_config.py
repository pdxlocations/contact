import unittest
from tempfile import NamedTemporaryFile
from unittest import mock

import contact.ui.default_config  # Initialize config before the color helpers.
from contact.ui import user_config


class UserConfigTests(unittest.TestCase):
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
