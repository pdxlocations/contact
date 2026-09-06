import unittest
from unittest import mock

from meshtastic.protobuf import config_pb2, mesh_pb2, telemetry_pb2

import contact.ui.default_config as config
from contact.utilities.demo_data import DEMO_LOCAL_NODE_NUM, build_demo_interface
from contact.utilities.singleton import interface_state, ui_state
from contact.utilities.utils import (
    _get_channel_name,
    _get_modem_preset_name,
    add_new_message,
    get_channels,
    get_node_list,
    parse_protobuf,
)

from tests.test_support import reset_singletons, restore_config, snapshot_config


class UtilsTests(unittest.TestCase):
    def test_parse_protobuf_beautifies_local_stats(self) -> None:
        telemetry = telemetry_pb2.Telemetry(time=1788677531)
        telemetry.local_stats.uptime_seconds = 7200
        telemetry.local_stats.channel_utilization = 2.90333319
        telemetry.local_stats.num_packets_tx = 12
        telemetry.local_stats.num_packets_rx_bad = 3
        telemetry.local_stats.num_online_nodes = 4
        telemetry.local_stats.heap_free_bytes = 1024

        rendered = parse_protobuf({"decoded": {
            "portnum": "TELEMETRY_APP", "payload": telemetry.SerializeToString(),
        }})

        self.assertIn("🆙 2.0h", rendered)
        self.assertIn("ChUtil:2.9%", rendered)
        self.assertIn("📤 Tx:12", rendered)
        self.assertIn("⚠️ RxBad:3", rendered)
        self.assertIn("📡 Online:4", rendered)
        self.assertIn("💾 Free:1024B", rendered)
        self.assertNotIn("local_stats", rendered)

    def test_parse_protobuf_beautifies_position_details(self) -> None:
        position = mesh_pb2.Position(
            latitude_i=454230020, longitude_i=-1228472320,
            location_source=mesh_pb2.Position.LOC_INTERNAL,
            ground_speed=2, ground_track=9000, PDOP=211, sats_in_view=8,
        )
        rendered = parse_protobuf({"decoded": {
            "portnum": "POSITION_APP", "payload": position.SerializeToString(),
        }})

        self.assertIn("🌍 45.423002", rendered)
        self.assertIn("-122.847232", rendered)
        self.assertIn("📍 LOC_INTERNAL", rendered)
        self.assertIn("💨 2m/s", rendered)
        self.assertIn("🧭 90.0°", rendered)
        self.assertIn("🎯 PDOP:2.11", rendered)
        self.assertIn("🛰️ 8", rendered)

    def setUp(self) -> None:
        reset_singletons()
        _get_modem_preset_name.cache_clear()
        self.saved_config = snapshot_config("node_sort")

    def tearDown(self) -> None:
        restore_config(self.saved_config)
        reset_singletons()

    def test_get_node_list_keeps_local_first_and_ignored_last(self) -> None:
        config.node_sort = "lastHeard"
        interface = build_demo_interface()
        interface_state.interface = interface
        interface_state.myNodeNum = DEMO_LOCAL_NODE_NUM

        node_list = get_node_list()

        self.assertEqual(node_list[0], DEMO_LOCAL_NODE_NUM)
        self.assertEqual(node_list[-1], 0xA1000008)

    def test_add_new_message_groups_messages_by_hour(self) -> None:
        ui_state.all_messages = {"MediumFast": []}

        with mock.patch("contact.utilities.utils.time.time", side_effect=[1000, 1000]):
            with mock.patch("contact.utilities.utils.time.strftime", return_value="[00:16:40] "):
                with mock.patch("contact.utilities.utils.datetime.datetime") as mocked_datetime:
                    mocked_datetime.fromtimestamp.return_value.strftime.return_value = "2025-02-04 17:00"
                    add_new_message("MediumFast", ">> Test: ", "First")
                    add_new_message("MediumFast", ">> Test: ", "Second")

        self.assertEqual(
            ui_state.all_messages["MediumFast"],
            [
                ("-- 2025-02-04 17:00 --", ""),
                ("[00:16:40] >> Test: ", "First"),
                ("[00:16:40] >> Test: ", "Second"),
            ],
        )

    def test_get_channels_populates_message_buckets_for_device_channels(self) -> None:
        interface_state.interface = build_demo_interface()
        ui_state.channel_list = []
        ui_state.all_messages = {}

        channels = get_channels()

        self.assertIn("MediumFast", channels)
        self.assertIn("Another Channel", channels)
        self.assertIn("MediumFast", ui_state.all_messages)
        self.assertIn("Another Channel", ui_state.all_messages)

    def test_get_channel_name_handles_newer_known_modem_preset(self) -> None:
        device_channel = mock.Mock()
        device_channel.settings.name = ""
        node = mock.Mock()
        node.localConfig.lora.modem_preset = 14

        with mock.patch("contact.utilities.utils.logging.warning") as warning:
            self.assertEqual(_get_channel_name(device_channel, node), "TinyFast")

        warning.assert_called_once()

    def test_get_channel_name_handles_unknown_modem_preset(self) -> None:
        device_channel = mock.Mock()
        device_channel.settings.name = ""
        node = mock.Mock()
        node.localConfig.lora.modem_preset = 99

        with mock.patch("contact.utilities.utils.logging.warning") as warning:
            self.assertEqual(_get_channel_name(device_channel, node), "UnknownPreset99")

        warning.assert_called_once()

    def test_get_channel_name_prefers_public_protobuf_enum_over_compatibility_map(self) -> None:
        device_channel = mock.Mock()
        device_channel.settings.name = ""
        node = mock.Mock()
        node.localConfig.lora.modem_preset = 14

        with mock.patch.object(
            config_pb2.Config.LoRaConfig.ModemPreset,
            "Name",
            return_value="TINY_FAST",
        ) as enum_name:
            with mock.patch("contact.utilities.utils.logging.warning") as warning:
                self.assertEqual(_get_channel_name(device_channel, node), "TinyFast")

        enum_name.assert_called_once_with(14)
        warning.assert_not_called()

    def test_get_channels_rebuilds_renamed_channels_and_preserves_messages(self) -> None:
        interface = build_demo_interface()
        interface.localNode.channels[0].settings.name = "Renamed Channel"
        interface_state.interface = interface
        ui_state.channel_list = ["MediumFast", "Another Channel", 2701131788]
        ui_state.all_messages = {
            "MediumFast": [("prefix", "first")],
            "Another Channel": [("prefix", "second")],
            2701131788: [("prefix", "dm")],
        }
        ui_state.selected_channel = 2

        channels = get_channels()

        self.assertEqual(channels[0], "Renamed Channel")
        self.assertEqual(channels[1], "Another Channel")
        self.assertEqual(channels[2], 2701131788)
        self.assertEqual(ui_state.all_messages["Renamed Channel"], [("prefix", "first")])
        self.assertEqual(ui_state.all_messages["Another Channel"], [("prefix", "second")])
        self.assertEqual(ui_state.all_messages[2701131788], [("prefix", "dm")])
        self.assertNotIn("MediumFast", ui_state.all_messages)

    def test_parse_protobuf_returns_string_payload_unchanged(self) -> None:
        packet = {"decoded": {"portnum": "TEXT_MESSAGE_APP", "payload": "hello"}}

        self.assertEqual(parse_protobuf(packet), "hello")

    def test_parse_protobuf_returns_placeholder_for_text_messages(self) -> None:
        packet = {"decoded": {"portnum": "TEXT_MESSAGE_APP", "payload": b"hello"}}

        self.assertEqual(parse_protobuf(packet), "✉️")
