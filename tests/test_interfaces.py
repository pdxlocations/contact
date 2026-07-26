from argparse import Namespace
from types import SimpleNamespace
import unittest
from unittest import mock

from contact.utilities.interfaces import reconnect_interface


class InterfacesTests(unittest.TestCase):
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
