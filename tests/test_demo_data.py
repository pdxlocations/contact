import tempfile
import unittest
from unittest import mock

import contact.runtime as entrypoint
import contact.ui.default_config as config
from contact.utilities.db_handler import get_name_from_database
from contact.utilities.demo_data import DEMO_CHANNELS, DEMO_LOCAL_NODE_NUM, build_demo_interface, configure_demo_database
from contact.utilities.singleton import interface_state, ui_state

from tests.test_support import reset_singletons, restore_config, snapshot_config


class DemoDataTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_singletons()
        self.saved_config = snapshot_config("db_file_path", "node_sort", "single_pane_mode")

    def tearDown(self) -> None:
        restore_config(self.saved_config)
        reset_singletons()

    def test_build_demo_interface_exposes_expected_shape(self) -> None:
        interface = build_demo_interface()

        self.assertEqual(interface.getMyNodeInfo()["num"], DEMO_LOCAL_NODE_NUM)
        self.assertEqual([channel.settings.name for channel in interface.getNode("^local").channels], DEMO_CHANNELS)
        self.assertIn(DEMO_LOCAL_NODE_NUM, interface.nodesByNum)

    def test_initialize_globals_seed_demo_populates_ui_state_and_db(self) -> None:
        interface_state.interface = build_demo_interface()

        with tempfile.TemporaryDirectory() as tmpdir:
            demo_db_path = configure_demo_database(tmpdir)
            with mock.patch.object(entrypoint.pub, "subscribe"):
                entrypoint.initialize_globals(seed_demo=True)

            self.assertEqual(config.db_file_path, demo_db_path)
            self.assertIn("MediumFast", ui_state.channel_list)
            self.assertIn("Another Channel", ui_state.channel_list)
            self.assertIn(2701131788, ui_state.channel_list)
            self.assertEqual(ui_state.node_list[0], DEMO_LOCAL_NODE_NUM)
            self.assertEqual(get_name_from_database(2701131778, "short"), "SAT2")

            medium_fast = ui_state.all_messages["MediumFast"]
            self.assertTrue(medium_fast[0][0].startswith("-- "))
            self.assertTrue(any(config.sent_message_prefix in prefix and config.ack_str in prefix for prefix, _ in medium_fast))
            self.assertTrue(any("SAT2:" in prefix for prefix, _ in medium_fast))

            direct_messages = ui_state.all_messages[2701131788]
            self.assertEqual(len(direct_messages), 3)
