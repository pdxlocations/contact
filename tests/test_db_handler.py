import os
import sqlite3
import tempfile
import unittest

import contact.ui.default_config as config
from contact.utilities import db_handler
from contact.utilities.demo_data import DEMO_LOCAL_NODE_NUM, build_demo_interface
from contact.utilities.singleton import interface_state, ui_state
from contact.utilities.utils import decimal_to_hex

from tests.test_support import reset_singletons, restore_config, snapshot_config


class DbHandlerTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_singletons()
        self.saved_config = snapshot_config(
            "db_file_path",
            "message_prefix",
            "sent_message_prefix",
            "ack_str",
            "ack_implicit_str",
            "ack_unknown_str",
            "nak_str",
        )
        self.tempdir = tempfile.TemporaryDirectory()
        config.db_file_path = os.path.join(self.tempdir.name, "client.db")
        interface_state.myNodeNum = 123

    def tearDown(self) -> None:
        self.tempdir.cleanup()
        restore_config(self.saved_config)
        reset_singletons()

    def test_save_message_to_db_and_update_ack_roundtrip(self) -> None:
        timestamp = db_handler.save_message_to_db("Primary", "123", "hello")

        self.assertIsInstance(timestamp, int)

        db_handler.update_ack_nak("Primary", timestamp, "hello", "Ack")

        with sqlite3.connect(config.db_file_path) as conn:
            row = conn.execute('SELECT user_id, message_text, ack_type FROM "123_Primary_messages"').fetchone()

        self.assertEqual(row, ("123", "hello", "Ack"))

    def test_update_node_info_in_db_fills_defaults_and_preserves_existing_values(self) -> None:
        db_handler.update_node_info_in_db(999, short_name="ABCD")

        original_long_name = db_handler.get_name_from_database(999, "long")
        self.assertTrue(original_long_name.startswith("Meshtastic "))
        self.assertEqual(db_handler.get_name_from_database(999, "short"), "ABCD")
        self.assertEqual(db_handler.is_chat_archived(999), 0)

        db_handler.update_node_info_in_db(999, chat_archived=1)

        self.assertEqual(db_handler.get_name_from_database(999, "long"), original_long_name)
        self.assertEqual(db_handler.get_name_from_database(999, "short"), "ABCD")
        self.assertEqual(db_handler.is_chat_archived(999), 1)

    def test_get_name_from_database_returns_hex_when_user_is_missing(self) -> None:
        user_id = 0x1234ABCD
        db_handler.ensure_node_table_exists()

        self.assertEqual(db_handler.get_name_from_database(user_id, "short"), decimal_to_hex(user_id))
        self.assertEqual(db_handler.is_chat_archived(user_id), 0)

    def test_load_messages_from_db_populates_channels_and_messages(self) -> None:
        db_handler.update_node_info_in_db(123, long_name="Local Node", short_name="ME")
        db_handler.update_node_info_in_db(456, long_name="Remote Node", short_name="RM")
        db_handler.update_node_info_in_db(789, long_name="Archived", short_name="AR", chat_archived=1)

        db_handler.ensure_table_exists(
            '"123_Primary_messages"',
            """
            user_id TEXT,
            message_text TEXT,
            timestamp INTEGER,
            ack_type TEXT
            """,
        )
        db_handler.ensure_table_exists(
            '"123_789_messages"',
            """
            user_id TEXT,
            message_text TEXT,
            timestamp INTEGER,
            ack_type TEXT
            """,
        )

        with sqlite3.connect(config.db_file_path) as conn:
            conn.execute('INSERT INTO "123_Primary_messages" VALUES (?, ?, ?, ?)', ("123", "sent", 1700000000, "Ack"))
            conn.execute('INSERT INTO "123_Primary_messages" VALUES (?, ?, ?, ?)', ("456", "reply", 1700000001, None))
            conn.execute('INSERT INTO "123_789_messages" VALUES (?, ?, ?, ?)', ("789", "hidden", 1700000002, None))
            conn.commit()

        ui_state.channel_list = []
        ui_state.all_messages = {}

        db_handler.load_messages_from_db()

        self.assertIn("Primary", ui_state.channel_list)
        self.assertNotIn(789, ui_state.channel_list)
        self.assertIn("Primary", ui_state.all_messages)
        self.assertIn(789, ui_state.all_messages)

        messages = ui_state.all_messages["Primary"]
        self.assertTrue(messages[0][0].startswith("-- "))
        self.assertTrue(any(config.sent_message_prefix in prefix and config.ack_str in prefix for prefix, _ in messages))
        self.assertTrue(any("RM:" in prefix for prefix, _ in messages))
        self.assertEqual(ui_state.all_messages[789][-1][1], "hidden")

    def test_message_history_is_loaded_in_bounded_pages(self) -> None:
        db_handler.update_node_info_in_db(456, long_name="Remote Node", short_name="RM")
        db_handler.ensure_table_exists(
            '"123_Primary_messages"',
            "user_id TEXT, message_text TEXT, timestamp INTEGER, ack_type TEXT",
        )
        with sqlite3.connect(config.db_file_path) as conn:
            conn.executemany(
                'INSERT INTO "123_Primary_messages" VALUES (?, ?, ?, ?)',
                [("456", f"message-{i}", 1700000000 + i, None) for i in range(7)],
            )

        db_handler.load_messages_from_db(page_size=3)

        loaded_text = [message for _, message in ui_state.all_messages["Primary"] if message]
        self.assertEqual(loaded_text, ["message-4", "message-5", "message-6"])
        self.assertTrue(ui_state.has_older_messages["Primary"])

        self.assertEqual(db_handler.load_older_messages("Primary", page_size=3), 3)
        loaded_text = [message for _, message in ui_state.all_messages["Primary"] if message]
        self.assertEqual(
            loaded_text,
            ["message-1", "message-2", "message-3", "message-4", "message-5", "message-6"],
        )
        self.assertTrue(ui_state.has_older_messages["Primary"])

        self.assertEqual(db_handler.load_older_messages("Primary", page_size=3), 1)
        loaded_text = [message for _, message in ui_state.all_messages["Primary"] if message]
        self.assertEqual(loaded_text, [f"message-{i}" for i in range(7)])
        self.assertFalse(ui_state.has_older_messages["Primary"])

    def test_message_table_channel_name_may_contain_underscores(self) -> None:
        db_handler.ensure_node_table_exists()
        db_handler.ensure_table_exists(
            '"123_My_Channel_messages"',
            "user_id TEXT, message_text TEXT, timestamp INTEGER, ack_type TEXT",
        )
        with sqlite3.connect(config.db_file_path) as conn:
            conn.execute(
                'INSERT INTO "123_My_Channel_messages" VALUES (?, ?, ?, ?)',
                ("123", "hello", 1700000000, None),
            )

        db_handler.load_messages_from_db()

        self.assertIn("My_Channel", ui_state.channel_list)
        self.assertEqual(ui_state.all_messages["My_Channel"][-1][1], "hello")

    def test_init_nodedb_inserts_nodes_from_interface(self) -> None:
        interface_state.interface = build_demo_interface()
        interface_state.myNodeNum = DEMO_LOCAL_NODE_NUM

        db_handler.init_nodedb()

        self.assertEqual(db_handler.get_name_from_database(2701131778, "short"), "SAT2")
