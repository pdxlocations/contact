import unittest
from unittest import mock

import contact.ui.default_config as config
from contact.ui import contact_ui
from contact.ui.nav_utils import text_width
from contact.utilities.singleton import ui_state

from tests.test_support import reset_singletons, restore_config, snapshot_config


class ContactUiTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_singletons()
        self.saved_config = snapshot_config("single_pane_mode")

    def tearDown(self) -> None:
        restore_config(self.saved_config)
        reset_singletons()

    def test_handle_backtick_refreshes_channels_after_settings_menu(self) -> None:
        stdscr = mock.Mock()
        ui_state.current_window = 1
        config.single_pane_mode = "False"

        with mock.patch.object(contact_ui.curses, "curs_set") as curs_set:
            with mock.patch.object(contact_ui, "settings_menu") as settings_menu:
                with mock.patch.object(contact_ui, "get_channels") as get_channels:
                    with mock.patch.object(contact_ui, "refresh_node_list") as refresh_node_list:
                        with mock.patch.object(contact_ui, "handle_resize") as handle_resize:
                            contact_ui.handle_backtick(stdscr)

        settings_menu.assert_called_once()
        get_channels.assert_called_once_with()
        refresh_node_list.assert_called_once_with()
        handle_resize.assert_called_once_with(stdscr, False)
        self.assertEqual(curs_set.call_args_list[0].args, (0,))
        self.assertEqual(curs_set.call_args_list[-1].args, (1,))
        self.assertEqual(ui_state.current_window, 1)

    def test_process_pending_ui_updates_draws_requested_windows(self) -> None:
        stdscr = mock.Mock()
        ui_state.redraw_channels = True
        ui_state.redraw_messages = True
        ui_state.redraw_nodes = True
        ui_state.redraw_packetlog = True
        ui_state.scroll_messages_to_bottom = True

        with mock.patch.object(contact_ui, "draw_channel_list") as draw_channel_list:
            with mock.patch.object(contact_ui, "draw_messages_window") as draw_messages_window:
                with mock.patch.object(contact_ui, "draw_node_list") as draw_node_list:
                    with mock.patch.object(contact_ui, "draw_packetlog_win") as draw_packetlog_win:
                        contact_ui.process_pending_ui_updates(stdscr)

        draw_channel_list.assert_called_once_with()
        draw_messages_window.assert_called_once_with(True)
        draw_node_list.assert_called_once_with()
        draw_packetlog_win.assert_called_once_with()

    def test_process_pending_ui_updates_full_redraw_uses_handle_resize(self) -> None:
        stdscr = mock.Mock()
        ui_state.redraw_full_ui = True
        ui_state.redraw_channels = True
        ui_state.redraw_messages = True

        with mock.patch.object(contact_ui, "handle_resize") as handle_resize:
            contact_ui.process_pending_ui_updates(stdscr)

        handle_resize.assert_called_once_with(stdscr, False)
        self.assertFalse(ui_state.redraw_channels)
        self.assertFalse(ui_state.redraw_messages)

    def test_draw_messages_resizes_pad_once(self) -> None:
        ui_state.channel_list = ["Primary"]
        ui_state.all_messages = {"Primary": [("[10:00] RX: ", "one"), ("[10:01] RX: ", "two")]}
        contact_ui.messages_pad = mock.Mock()
        contact_ui.messages_win = mock.Mock()
        contact_ui.messages_win.getmaxyx.return_value = (10, 40)
        contact_ui.packetlog_win = mock.Mock()
        contact_ui.packetlog_win.getmaxyx.return_value = (1, 40)
        contact_ui.messages_win.getbegyx.return_value = (0, 0)

        with mock.patch.object(contact_ui, "paint_frame"):
            with mock.patch.object(contact_ui, "get_color", return_value=0):
                with mock.patch.object(contact_ui, "refresh_pad"):
                    with mock.patch.object(contact_ui, "draw_packetlog_win"):
                        with mock.patch.object(contact_ui, "draw_window_arrows"):
                            contact_ui.draw_messages_window()

        contact_ui.messages_pad.resize.assert_called_once_with(2, 40)

    def test_refresh_node_selection_reserves_scroll_arrow_column(self) -> None:
        ui_state.node_list = [101, 202]
        ui_state.selected_node = 1
        ui_state.start_index = [0, 0, 0]
        contact_ui.nodes_pad = mock.Mock()
        contact_ui.nodes_pad.getmaxyx.return_value = (4, 20)
        contact_ui.nodes_win = mock.Mock()
        contact_ui.nodes_win.getmaxyx.return_value = (10, 20)

        interface = mock.Mock()
        interface.nodesByNum = {101: {}, 202: {}}

        with mock.patch.object(contact_ui, "refresh_pad") as refresh_pad:
            with mock.patch.object(contact_ui, "draw_window_arrows") as draw_window_arrows:
                with mock.patch.object(contact_ui, "get_node_row_color", side_effect=[11, 22]):
                    with mock.patch("contact.ui.contact_ui.interface_state.interface", interface):
                        contact_ui.refresh_node_selection(old_index=0, highlight=True)

        self.assertEqual(
            contact_ui.nodes_pad.chgat.call_args_list,
            [mock.call(0, 1, 16, 11), mock.call(1, 1, 16, 22)],
        )
        refresh_pad.assert_called_once_with(2)
        draw_window_arrows.assert_called_once_with(2)

    def test_draw_channel_list_reserves_scroll_arrow_column(self) -> None:
        ui_state.channel_list = ["VeryLongChannelName"]
        ui_state.notifications = []
        ui_state.selected_channel = 0
        ui_state.current_window = 0
        contact_ui.channel_pad = mock.Mock()
        contact_ui.channel_win = mock.Mock()
        contact_ui.channel_win.getmaxyx.return_value = (10, 20)

        with mock.patch.object(contact_ui, "get_color", return_value=1):
            with mock.patch.object(contact_ui, "paint_frame"):
                with mock.patch.object(contact_ui, "refresh_pad"):
                    with mock.patch.object(contact_ui, "draw_window_arrows"):
                        with mock.patch.object(contact_ui, "remove_notification"):
                            contact_ui.draw_channel_list()

        text = contact_ui.channel_pad.addstr.call_args.args[2]
        self.assertEqual(len(text), 16)

    def test_draw_node_list_reserves_scroll_arrow_column(self) -> None:
        ui_state.node_list = [101]
        ui_state.current_window = 2
        contact_ui.nodes_pad = mock.Mock()
        contact_ui.nodes_win = mock.Mock()
        contact_ui.nodes_win.getmaxyx.return_value = (10, 20)
        contact_ui.entry_win = mock.Mock()
        interface = mock.Mock()
        interface.nodesByNum = {101: {"user": {"longName": "VeryLongNodeName", "publicKey": ""}}}

        with mock.patch("contact.ui.contact_ui.interface_state.interface", interface):
            with mock.patch.object(contact_ui, "get_node_row_color", return_value=1):
                with mock.patch.object(contact_ui.curses, "curs_set"):
                    with mock.patch.object(contact_ui, "paint_frame"):
                        with mock.patch.object(contact_ui, "refresh_pad"):
                            with mock.patch.object(contact_ui, "draw_window_arrows"):
                                contact_ui.draw_node_list()

        text = contact_ui.nodes_pad.addstr.call_args.args[2]
        self.assertEqual(text_width(text), 16)
        self.assertIn("…", text)

    def test_handle_resize_single_pane_keeps_full_width_windows(self) -> None:
        stdscr = mock.Mock()
        stdscr.getmaxyx.return_value = (24, 80)
        ui_state.single_pane_mode = True
        ui_state.current_window = 1

        contact_ui.entry_win = mock.Mock()
        contact_ui.channel_win = mock.Mock()
        contact_ui.messages_win = mock.Mock()
        contact_ui.nodes_win = mock.Mock()
        contact_ui.packetlog_win = mock.Mock()
        contact_ui.messages_pad = mock.Mock()
        contact_ui.nodes_pad = mock.Mock()
        contact_ui.channel_pad = mock.Mock()

        with mock.patch.object(contact_ui.curses, "curs_set"):
            with mock.patch.object(contact_ui, "draw_channel_list") as draw_channel_list:
                with mock.patch.object(contact_ui, "draw_messages_window") as draw_messages_window:
                    with mock.patch.object(contact_ui, "draw_node_list") as draw_node_list:
                        with mock.patch.object(contact_ui, "draw_window_arrows") as draw_window_arrows:
                            contact_ui.handle_resize(stdscr, False)

        contact_ui.channel_win.resize.assert_called_once_with(21, 80)
        contact_ui.messages_win.resize.assert_called_once_with(21, 80)
        contact_ui.nodes_win.resize.assert_called_once_with(21, 80)
        contact_ui.channel_win.mvwin.assert_called_once_with(0, 0)
        contact_ui.messages_win.mvwin.assert_called_once_with(0, 0)
        contact_ui.nodes_win.mvwin.assert_called_once_with(0, 0)
        contact_ui.channel_win.box.assert_not_called()
        contact_ui.nodes_win.box.assert_not_called()
        contact_ui.messages_win.box.assert_called_once_with()
        draw_channel_list.assert_called_once_with()
        draw_messages_window.assert_called_once_with(True)
        draw_node_list.assert_called_once_with()
        draw_window_arrows.assert_called_once_with(1)

    def test_get_window_title_uses_selected_channel_only_for_messages_in_single_pane_mode(self) -> None:
        ui_state.single_pane_mode = True
        ui_state.channel_list = ["Primary"]
        ui_state.selected_channel = 0

        self.assertEqual(contact_ui.get_window_title(0), "")
        self.assertEqual(contact_ui.get_window_title(1), "Primary")

    def test_refresh_pad_draws_selected_channel_title_on_message_frame(self) -> None:
        ui_state.single_pane_mode = True
        ui_state.current_window = 1
        ui_state.channel_list = ["Primary"]
        ui_state.selected_channel = 0
        ui_state.start_index = [0, 0, 0]
        ui_state.display_log = False

        contact_ui.channel_win = mock.Mock()
        contact_ui.channel_win.getmaxyx.return_value = (10, 20)
        contact_ui.messages_pad = mock.Mock()
        contact_ui.messages_pad.getmaxyx.return_value = (5, 20)
        contact_ui.messages_win = mock.Mock()
        contact_ui.messages_win.getbegyx.return_value = (0, 0)
        contact_ui.messages_win.getmaxyx.return_value = (10, 20)

        with mock.patch.object(contact_ui, "get_msg_window_lines", return_value=4):
            contact_ui.refresh_pad(1)

        contact_ui.messages_win.addstr.assert_called_once_with(0, 2, " Primary ", contact_ui.curses.A_BOLD)

    def test_search_ignores_no_input_from_curses(self) -> None:
        ui_state.node_list = [101]
        ui_state.selected_node = 0
        contact_ui.entry_win = mock.Mock()
        contact_ui.entry_win.get_wch.side_effect = contact_ui.curses.error("no input")

        with mock.patch.object(contact_ui, "draw_centered_text_field"):
            with mock.patch.object(contact_ui, "get_color", return_value=0):
                contact_ui.search(2)

        contact_ui.entry_win.timeout.assert_has_calls([mock.call(-1), mock.call(200)])
        contact_ui.entry_win.erase.assert_called()

    def test_f5_node_details_ignores_no_input_from_curses(self) -> None:
        stdscr = mock.Mock()
        ui_state.node_list = [101]
        ui_state.selected_node = 0
        ui_state.current_window = 2

        dialog_win = mock.Mock()
        dialog_win.getch.side_effect = [contact_ui.curses.error("no input"), 27]
        msg_win = mock.Mock()
        dialog_win.derwin.return_value = msg_win

        interface = mock.Mock()
        interface.nodesByNum = {
            101: {
                "num": 101,
                "user": {
                    "longName": "Test Node",
                    "shortName": "TN",
                    "hwModel": "T-Beam",
                    "role": "CLIENT",
                    "publicKey": "abc",
                },
            }
        }

        with mock.patch("contact.ui.contact_ui.interface_state.interface", interface):
            with mock.patch.object(contact_ui.curses, "LINES", 24, create=True):
                with mock.patch.object(contact_ui.curses, "COLS", 80, create=True):
                    with mock.patch.object(contact_ui.curses, "curs_set"):
                        with mock.patch.object(contact_ui.curses, "update_lines_cols"):
                            with mock.patch.object(contact_ui.curses, "doupdate"):
                                with mock.patch.object(contact_ui.curses, "newwin", return_value=dialog_win):
                                    with mock.patch.object(contact_ui, "get_color", return_value=0):
                                        with mock.patch.object(contact_ui, "refresh_node_selection"):
                                            with mock.patch.object(contact_ui, "handle_resize") as handle_resize:
                                                contact_ui.handle_f5_key(stdscr)

        self.assertEqual(dialog_win.getch.call_count, 2)
        handle_resize.assert_called_once_with(stdscr, False)

    def test_f5_node_details_tolerates_none_metrics(self) -> None:
        stdscr = mock.Mock()
        ui_state.node_list = [101]
        ui_state.selected_node = 0
        ui_state.current_window = 2

        dialog_win = mock.Mock()
        dialog_win.getch.return_value = 27
        msg_win = mock.Mock()
        dialog_win.derwin.return_value = msg_win

        interface = mock.Mock()
        interface.nodesByNum = {
            101: {
                "num": 101,
                "snr": None,
                "hopsAway": None,
                "deviceMetrics": {
                    "batteryLevel": None,
                    "channelUtilization": None,
                    "airUtilTx": None,
                    "uptimeSeconds": None,
                },
                "user": {
                    "longName": "Test Node",
                    "shortName": "TN",
                    "hwModel": "T-Beam",
                    "role": "CLIENT",
                    "publicKey": "abc",
                },
            }
        }

        with mock.patch("contact.ui.contact_ui.interface_state.interface", interface):
            with mock.patch.object(contact_ui.curses, "LINES", 24, create=True):
                with mock.patch.object(contact_ui.curses, "COLS", 80, create=True):
                    with mock.patch.object(contact_ui.curses, "curs_set"):
                        with mock.patch.object(contact_ui.curses, "update_lines_cols"):
                            with mock.patch.object(contact_ui.curses, "doupdate"):
                                with mock.patch.object(contact_ui.curses, "newwin", return_value=dialog_win):
                                    with mock.patch.object(contact_ui, "get_color", return_value=0):
                                        with mock.patch.object(contact_ui, "refresh_node_selection"):
                                            with mock.patch.object(contact_ui, "handle_resize") as handle_resize:
                                                contact_ui.handle_f5_key(stdscr)

        handle_resize.assert_called_once_with(stdscr, False)
