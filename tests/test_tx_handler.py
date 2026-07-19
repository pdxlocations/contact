from types import SimpleNamespace
import unittest
from unittest import mock

from meshtastic import BROADCAST_NUM

import contact.ui.default_config as config
from contact.message_handlers import tx_handler
from contact.utilities.singleton import interface_state, ui_state

from tests.test_support import reset_singletons, restore_config, snapshot_config


class TxHandlerTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_singletons()
        tx_handler.ack_naks.clear()
        self.saved_config = snapshot_config("sent_message_prefix", "ack_str", "ack_implicit_str", "nak_str", "ack_unknown_str")

    def tearDown(self) -> None:
        tx_handler.ack_naks.clear()
        restore_config(self.saved_config)
        reset_singletons()

    def test_send_message_on_named_channel_tracks_ack_request(self) -> None:
        interface = mock.Mock()
        interface.sendText.return_value = SimpleNamespace(id="req-1")
        interface_state.interface = interface
        interface_state.myNodeNum = 111
        ui_state.channel_list = ["Primary"]
        ui_state.all_messages = {"Primary": []}

        with mock.patch.object(tx_handler, "save_message_to_db", return_value=999) as save_message_to_db:
            with mock.patch("contact.message_handlers.tx_handler.time.strftime", return_value="[00:00:00] "):
                tx_handler.send_message("hello", channel=0)

        interface.sendText.assert_called_once_with(
            text="hello",
            destinationId=BROADCAST_NUM,
            wantAck=True,
            wantResponse=False,
            onResponse=tx_handler.onAckNak,
            channelIndex=0,
        )
        save_message_to_db.assert_called_once_with("Primary", 111, "hello", packet_id="req-1", reply_id=None)
        self.assertEqual(tx_handler.ack_naks["req-1"]["channel"], "Primary")
        self.assertEqual(tx_handler.ack_naks["req-1"]["messageIndex"], 1)
        self.assertEqual(tx_handler.ack_naks["req-1"]["timestamp"], 999)
        self.assertEqual(ui_state.all_messages["Primary"][-1][1], "hello")

    def test_send_message_to_direct_node_uses_node_as_destination(self) -> None:
        interface = mock.Mock()
        interface.sendText.return_value = SimpleNamespace(id="req-2")
        interface_state.interface = interface
        interface_state.myNodeNum = 111
        ui_state.channel_list = [222]
        ui_state.all_messages = {222: []}

        with mock.patch.object(tx_handler, "save_message_to_db", return_value=123):
            with mock.patch("contact.message_handlers.tx_handler.time.strftime", return_value="[00:00:00] "):
                tx_handler.send_message("dm", channel=0)

        interface.sendText.assert_called_once_with(
            text="dm",
            destinationId=222,
            wantAck=True,
            wantResponse=False,
            onResponse=tx_handler.onAckNak,
            channelIndex=0,
        )
        self.assertEqual(tx_handler.ack_naks["req-2"]["channel"], 222)

    def test_send_message_uses_native_reply_id_but_only_displays_reply_context_locally(self) -> None:
        interface = mock.Mock()
        interface.sendText.return_value = SimpleNamespace(id="req-3")
        interface_state.interface = interface
        interface_state.myNodeNum = 111
        ui_state.channel_list = ["Primary"]
        ui_state.all_messages = {"Primary": []}

        with mock.patch.object(tx_handler, "save_message_to_db", return_value=123):
            tx_handler.send_message("hello", channel=0, reply_id=77, reply_context="<Re: NODE: hello> ")

        self.assertEqual(interface.sendText.call_args.kwargs["text"], "hello")
        self.assertEqual(interface.sendText.call_args.kwargs["replyId"], 77)
        self.assertEqual(ui_state.all_messages["Primary"][-1][1], "<Re: NODE: hello> hello")

    def test_on_ack_nak_updates_message_for_explicit_ack(self) -> None:
        interface_state.myNodeNum = 111
        ui_state.channel_list = ["Primary"]
        ui_state.selected_channel = 0
        ui_state.all_messages = {"Primary": [("pending", "hello")]}
        tx_handler.ack_naks["req"] = {"channel": "Primary", "messageIndex": 0, "timestamp": 55, "dbMessage": "hello"}

        packet = {"from": 222, "decoded": {"requestId": "req", "routing": {"errorReason": "NONE"}}}

        with mock.patch.object(tx_handler, "update_ack_nak") as update_ack_nak:
            with mock.patch("contact.message_handlers.tx_handler.time.strftime", return_value="[01:02:03] "):
                with mock.patch("contact.ui.contact_ui.request_ui_redraw") as request_ui_redraw:
                    tx_handler.onAckNak(packet)

        update_ack_nak.assert_called_once_with("Primary", 55, "hello", "Ack")
        request_ui_redraw.assert_called_once_with(messages=True)
        self.assertIn(config.sent_message_prefix, ui_state.all_messages["Primary"][0][0])
        self.assertIn(config.ack_str, ui_state.all_messages["Primary"][0][0])

    def test_on_ack_nak_uses_implicit_marker_for_self_ack(self) -> None:
        interface_state.myNodeNum = 111
        ui_state.channel_list = ["Primary"]
        ui_state.selected_channel = 0
        ui_state.all_messages = {"Primary": [("pending", "hello")]}
        tx_handler.ack_naks["req"] = {"channel": "Primary", "messageIndex": 0, "timestamp": 55, "dbMessage": "hello"}

        packet = {"from": 111, "decoded": {"requestId": "req", "routing": {"errorReason": "NONE"}}}

        with mock.patch.object(tx_handler, "update_ack_nak") as update_ack_nak:
            with mock.patch("contact.message_handlers.tx_handler.time.strftime", return_value="[01:02:03] "):
                with mock.patch("contact.ui.contact_ui.request_ui_redraw"):
                    tx_handler.onAckNak(packet)

        update_ack_nak.assert_called_once_with("Primary", 55, "hello", "Implicit")
        self.assertIn(config.ack_implicit_str, ui_state.all_messages["Primary"][0][0])
