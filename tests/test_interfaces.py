from argparse import Namespace
from types import SimpleNamespace
import unittest
from unittest import mock

from meshtastic.protobuf import localonly_pb2, mesh_pb2

from contact.ui.menus import generate_menu_from_protobuf
from contact.utilities.interfaces import BLEInterface, SerialInterface, TCPInterface, reconnect_interface


class InterfacesTests(unittest.TestCase):
    def test_received_status_message_appears_in_settings_after_reconnect(self):
        for transport in (SerialInterface, TCPInterface, BLEInterface):
            with self.subTest(transport=transport.__name__):
                # A fresh interface has no cached value from the previous save.
                interface = transport.__new__(transport)
                interface.configId = 123
                interface.localNode = SimpleNamespace(
                    localConfig=localonly_pb2.LocalConfig(),
                    moduleConfig=localonly_pb2.LocalModuleConfig(),
                    getChannelByChannelIndex=lambda _: None,
                )
                interface.getMyNodeInfo = lambda: {"position": {}}
                for status in ("Available", ""):
                    packet = mesh_pb2.FromRadio()
                    packet.moduleConfig.statusmessage.node_status = status
                    interface._handleFromRadio(packet.SerializeToString())

                    # Other module packets must still pass through normally,
                    # without clearing the status message already received.
                    packet = mesh_pb2.FromRadio()
                    packet.moduleConfig.mqtt.enabled = True
                    interface._handleFromRadio(packet.SerializeToString())

                    self.assertTrue(interface.localNode.moduleConfig.mqtt.enabled)
                    menu = generate_menu_from_protobuf(interface)
                    value = menu["Main Menu"]["Module Settings"]["statusmessage"]["node_status"][1]
                    self.assertEqual(value, status)

    def test_reconnect_interface_retries_until_connection_succeeds(self) -> None:
        args = Namespace()

        ready_interface = SimpleNamespace(localNode=SimpleNamespace(localConfig=object(), nodeNum=123))
        with mock.patch(
            "contact.utilities.interfaces.initialize_interface", side_effect=[None, None, ready_interface]
        ) as initialize:
            with mock.patch("contact.utilities.interfaces.time.sleep") as sleep:
                with mock.patch("contact.utilities.interfaces.logging.info") as info:
                    result = reconnect_interface(args, attempts=3, delay_seconds=0.25)

        self.assertIs(result, ready_interface)
        self.assertEqual(initialize.call_count, 3)
        self.assertEqual(sleep.call_count, 2)
        self.assertTrue(any("Reconnected to Meshtastic node" in call.args[0] for call in info.call_args_list))

    def test_reconnect_interface_raises_after_exhausting_attempts(self) -> None:
        args = Namespace()

        with mock.patch("contact.utilities.interfaces.initialize_interface", return_value=None):
            with mock.patch("contact.utilities.interfaces.time.sleep"):
                with self.assertRaises(RuntimeError):
                    reconnect_interface(args, attempts=2, delay_seconds=0)
