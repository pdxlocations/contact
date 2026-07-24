import unittest
import importlib
import sys
import types
from unittest import mock

import contact.ui.default_config as config
from contact.utilities.singleton import interface_state
from tests.test_support import reset_singletons


class BotHandlerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        sys.modules.setdefault(
            "contact.message_handlers.tx_handler",
            types.SimpleNamespace(send_message=mock.Mock()),
        )
        cls.bot_handler = importlib.import_module("contact.message_handlers.bot_handler")

    def setUp(self) -> None:
        reset_singletons()
        self.bot_handler.send_message.reset_mock()

    def tearDown(self) -> None:
        reset_singletons()

    def test_is_bot_message_uses_configured_catch_words(self) -> None:
        with mock.patch.object(config, "ping_bot_catch_words", "ping; test; pong"):
            self.assertTrue(self.bot_handler.is_bot_message("PING"))
            self.assertTrue(self.bot_handler.is_bot_message("test"))
            self.assertFalse(self.bot_handler.is_bot_message("hello"))

    def test_is_bot_message_ignores_empty_config_values(self) -> None:
        with mock.patch.object(config, "ping_bot_catch_words", " ;  ; "):
            self.assertTrue(self.bot_handler.is_bot_message("ping"))

    def test_bot_response_replies_to_triggering_packet(self) -> None:
        interface_state.myNodeNum = 111
        packet = {"id": 900, "from": 222, "decoded": {}}

        with mock.patch.object(config, "ping_bot_enabled", "True"):
            with mock.patch.object(self.bot_handler.threading, "Thread") as thread:
                self.assertTrue(self.bot_handler.bot_respond(packet, "ping", 0))
                send_response = thread.call_args.kwargs["target"]
                with mock.patch.object(self.bot_handler.time, "sleep"):
                    with mock.patch.dict(
                        sys.modules,
                        {"contact.ui.contact_ui": types.SimpleNamespace(request_ui_redraw=mock.Mock())},
                    ):
                        send_response()

        self.bot_handler.send_message.assert_called_once_with(
            "Pong!", channel=0, reply_id=900
        )

    def test_bot_response_requires_enabled_app_setting(self) -> None:
        with mock.patch.object(config, "ping_bot_enabled", "False"):
            self.assertFalse(self.bot_handler.bot_respond({"from": 222}, "ping", 0))


if __name__ == "__main__":
    unittest.main()
