import tempfile
import unittest

from contact.ui import default_config


class DefaultConfigTests(unittest.TestCase):
    def test_get_localisation_options_filters_hidden_and_non_ini_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            for filename in ("en.ini", "ru.ini", ".hidden.ini", "notes.txt"):
                with open(f"{tmpdir}/{filename}", "w", encoding="utf-8") as handle:
                    handle.write("")

            self.assertEqual(default_config.get_localisation_options(tmpdir), ["en", "ru"])

    def test_get_localisation_file_normalizes_extensions_and_falls_back_to_english(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            for filename in ("en.ini", "ru.ini"):
                with open(f"{tmpdir}/{filename}", "w", encoding="utf-8") as handle:
                    handle.write("")

            self.assertTrue(default_config.get_localisation_file("RU.ini", tmpdir).endswith("/ru.ini"))
            self.assertTrue(default_config.get_localisation_file("missing", tmpdir).endswith("/en.ini"))

    def test_update_dict_only_adds_missing_values(self) -> None:
        default = {"theme": "dark", "nested": {"language": "en", "sound": True}}
        actual = {"nested": {"language": "ru"}}

        updated = default_config.update_dict(default, actual)

        self.assertTrue(updated)
        self.assertEqual(actual, {"theme": "dark", "nested": {"language": "ru", "sound": True}})

    def test_migrate_delivery_status_defaults_preserves_custom_values(self) -> None:
        actual = {
            "ack_implicit_str": "[◌]",
            "ack_str": "custom ack",
            "nak_str": "[x]",
            "ack_unknown_str": "[…]",
        }

        updated = default_config.migrate_delivery_status_defaults(actual)

        self.assertTrue(updated)
        self.assertEqual(actual["ack_implicit_str"], "Delivered to mesh")
        self.assertEqual(actual["ack_str"], "custom ack")
        self.assertEqual(actual["nak_str"], "Failed to deliver to mesh")
        self.assertEqual(actual["ack_unknown_str"], "Sending...")

    def test_format_json_single_line_arrays_keeps_arrays_inline(self) -> None:
        rendered = default_config.format_json_single_line_arrays({"items": [1, 2], "nested": {"flags": ["a", "b"]}})

        self.assertIn('"items": [1, 2]', rendered)
        self.assertIn('"flags": ["a", "b"]', rendered)
