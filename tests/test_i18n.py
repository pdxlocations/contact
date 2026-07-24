import os
import tempfile
import unittest
from unittest import mock

import contact.ui.default_config as config
from contact.utilities import i18n
from contact.utilities.ini_utils import parse_ini_file

from tests.test_support import restore_config, snapshot_config


class I18nTests(unittest.TestCase):
    def setUp(self) -> None:
        self.saved_config = snapshot_config("language")
        i18n._translations = {}
        i18n._language = None

    def tearDown(self) -> None:
        restore_config(self.saved_config)
        i18n._translations = {}
        i18n._language = None

    def test_t_loads_translation_file_and_formats_placeholders(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            translation_file = os.path.join(tmpdir, "xx.ini")
            with open(translation_file, "w", encoding="utf-8") as handle:
                handle.write('[ui]\n')
                handle.write('greeting,"Hello {name}"\n')

            config.language = "xx"
            with mock.patch.object(config, "get_localisation_file", return_value=translation_file):
                self.assertEqual(i18n.t("ui.greeting", name="Ben"), "Hello Ben")

    def test_t_falls_back_to_default_and_returns_unformatted_text_on_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            translation_file = os.path.join(tmpdir, "xx.ini")
            with open(translation_file, "w", encoding="utf-8") as handle:
                handle.write('[ui]\n')
                handle.write('greeting,"Hello {name}"\n')

            config.language = "xx"
            with mock.patch.object(config, "get_localisation_file", return_value=translation_file):
                self.assertEqual(i18n.t("ui.greeting"), "Hello {name}")
                self.assertEqual(i18n.t("ui.missing", default="Fallback"), "Fallback")
                self.assertEqual(i18n.t_text("Literal {value}", value=7), "Literal 7")

    def test_loader_cache_is_reused_until_language_changes(self) -> None:
        config.language = "en"

        with mock.patch.object(i18n, "parse_ini_file", return_value=({"key": "value"}, {})) as parse_ini_file:
            self.assertEqual(i18n.t("key"), "value")
            self.assertEqual(i18n.t("key"), "value")
            self.assertEqual(parse_ini_file.call_count, 1)

            config.language = "ru"
            self.assertEqual(i18n.t("missing", default="fallback"), "fallback")
            self.assertEqual(parse_ini_file.call_count, 2)

    def test_ping_bot_settings_translation_keys_exist_in_all_locales(self) -> None:
        required_keys = {
            "app_settings.ping_bot",
            "app_settings.ping_bot.enabled",
            "app_settings.ping_bot.catch_words",
            "app_settings.ping_bot.response_word",
        }

        for language in config.get_localisation_options():
            field_mapping, _ = parse_ini_file(config.get_localisation_file(language))
            self.assertTrue(required_keys.issubset(field_mapping), msg=f"Missing bot translation keys in {language}")
