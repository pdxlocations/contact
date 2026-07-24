import unittest
from unittest import mock

import contact.ui.default_config  # Initialize config before the color helpers.
from contact.ui import user_config


class UserConfigTests(unittest.TestCase):
    def test_ping_bot_enabled_uses_boolean_picker(self) -> None:
        with mock.patch.object(user_config, "get_list_input", return_value="True") as picker:
            result = user_config.edit_value("enabled", "Enabled", "False")

        self.assertEqual(result, "True")
        picker.assert_called_once_with("Enabled", "False", ["True", "False"])


if __name__ == "__main__":
    unittest.main()
