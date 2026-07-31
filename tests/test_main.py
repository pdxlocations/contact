from argparse import Namespace
from types import SimpleNamespace
import unittest
from unittest import mock

import contact.__main__ as entrypoint
import contact.ui.default_config as config
from contact.utilities.singleton import interface_state, ui_state

from tests.test_support import reset_singletons, restore_config, snapshot_config


class MainRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_singletons()
        self.saved_config = snapshot_config("single_pane_mode")

    def tearDown(self) -> None:
        restore_config(self.saved_config)
        reset_singletons()

    def test_initialize_runtime_interface_uses_demo_branch(self) -> None:
        args = Namespace(demo_screenshot=True)

        with mock.patch.object(entrypoint, "configure_demo_database") as configure_demo_database:
            with mock.patch.object(entrypoint, "build_demo_interface", return_value="demo-interface") as build_demo:
                with mock.patch.object(entrypoint, "initialize_interface") as initialize_interface:
                    result = entrypoint.initialize_runtime_interface(args)

        self.assertEqual(result, "demo-interface")
        configure_demo_database.assert_called_once_with()
        build_demo.assert_called_once_with()
        initialize_interface.assert_not_called()

    def test_initialize_runtime_interface_uses_live_branch_without_demo_flag(self) -> None:
        args = Namespace(demo_screenshot=False)

        with mock.patch.object(entrypoint, "initialize_interface", return_value="live-interface") as initialize_interface:
            result = entrypoint.initialize_runtime_interface(args)

        self.assertEqual(result, "live-interface")
        initialize_interface.assert_called_once_with(args)

    def test_interface_is_ready_detects_missing_local_node(self) -> None:
        self.assertFalse(entrypoint.interface_is_ready(object()))
        self.assertTrue(entrypoint.interface_is_ready(SimpleNamespace(localNode=SimpleNamespace(localConfig=mock.Mock()))))

    def test_initialize_runtime_interface_with_retry_retries_until_node_is_ready(self) -> None:
        args = Namespace(demo_screenshot=False)
        stdscr = mock.Mock()
        bad_interface = mock.Mock(spec=["close"])
        good_interface = SimpleNamespace(localNode=SimpleNamespace(localConfig=mock.Mock()))

        with mock.patch.object(entrypoint, "initialize_runtime_interface", side_effect=[bad_interface, good_interface]):
            with mock.patch.object(entrypoint, "get_list_input", return_value="Retry") as get_list_input:
                with mock.patch.object(entrypoint, "draw_splash") as draw_splash:
                    result = entrypoint.initialize_runtime_interface_with_retry(stdscr, args)

        self.assertIs(result, good_interface)
        get_list_input.assert_called_once()
        bad_interface.close.assert_called_once_with()
        draw_splash.assert_called_once_with(stdscr)

    def test_initialize_runtime_interface_with_retry_returns_none_when_user_closes(self) -> None:
        args = Namespace(demo_screenshot=False)
        stdscr = mock.Mock()
        bad_interface = mock.Mock(spec=["close"])

        with mock.patch.object(entrypoint, "initialize_runtime_interface", return_value=bad_interface):
            with mock.patch.object(entrypoint, "get_list_input", return_value="Close") as get_list_input:
                with mock.patch.object(entrypoint, "draw_splash") as draw_splash:
                    result = entrypoint.initialize_runtime_interface_with_retry(stdscr, args)

        self.assertIsNone(result)
        get_list_input.assert_called_once()
        bad_interface.close.assert_called_once_with()
        draw_splash.assert_not_called()

    def test_prompt_region_if_unset_reinitializes_interface_after_confirmation(self) -> None:
        args = Namespace()
        old_interface = mock.Mock()
        new_interface = mock.Mock()
        stdscr = mock.Mock()
        interface_state.interface = old_interface

        with mock.patch.object(entrypoint, "get_list_input", return_value="Yes"):
            with mock.patch.object(entrypoint, "set_region") as set_region:
                with mock.patch.object(entrypoint, "draw_splash") as draw_splash:
                    with mock.patch.object(entrypoint, "reconnect_interface", return_value=new_interface) as reconnect:
                        entrypoint.prompt_region_if_unset(args, stdscr)

        set_region.assert_called_once_with(old_interface)
        old_interface.close.assert_called_once_with()
        draw_splash.assert_called_once_with(stdscr)
        reconnect.assert_called_once_with(args)
        self.assertIs(interface_state.interface, new_interface)

    def test_prompt_region_if_unset_leaves_interface_unchanged_when_declined(self) -> None:
        args = Namespace()
        interface = mock.Mock()
        interface_state.interface = interface

        with mock.patch.object(entrypoint, "get_list_input", return_value="No"):
            with mock.patch.object(entrypoint, "set_region") as set_region:
                with mock.patch.object(entrypoint, "reconnect_interface") as reconnect:
                    entrypoint.prompt_region_if_unset(args)

        set_region.assert_not_called()
        reconnect.assert_not_called()
        interface.close.assert_not_called()
        self.assertIs(interface_state.interface, interface)

    def test_initialize_globals_resets_and_populates_runtime_state(self) -> None:
        ui_state.channel_list = ["stale"]
        ui_state.all_messages = {"stale": [("old", "message")]}
        ui_state.notifications = [1]
        ui_state.packet_buffer = ["packet"]
        ui_state.node_list = [99]
        ui_state.selected_channel = 3
        ui_state.selected_message = 4
        ui_state.selected_node = 5
        ui_state.start_index = [9, 9, 9]
        config.single_pane_mode = "True"

        with mock.patch.object(entrypoint, "get_nodeNum", return_value=123):
            with mock.patch.object(entrypoint, "get_channels", return_value=["Primary"]) as get_channels:
                with mock.patch.object(entrypoint, "get_node_list", return_value=[123, 456]) as get_node_list:
                    with mock.patch.object(entrypoint.pub, "subscribe") as subscribe:
                        with mock.patch.object(entrypoint, "init_nodedb") as init_nodedb:
                            with mock.patch.object(entrypoint, "seed_demo_messages") as seed_demo_messages:
                                with mock.patch.object(entrypoint, "load_messages_from_db") as load_messages:
                                    entrypoint.initialize_globals(seed_demo=True)

        self.assertEqual(ui_state.channel_list, ["Primary"])
        self.assertEqual(ui_state.all_messages, {})
        self.assertEqual(ui_state.notifications, [])
        self.assertEqual(ui_state.packet_buffer, [])
        self.assertEqual(ui_state.node_list, [123, 456])
        self.assertEqual(ui_state.selected_channel, 0)
        self.assertEqual(ui_state.selected_message, 0)
        self.assertEqual(ui_state.selected_node, 0)
        self.assertEqual(ui_state.start_index, [0, 0, 0])
        self.assertTrue(ui_state.single_pane_mode)
        self.assertEqual(interface_state.myNodeNum, 123)
        get_channels.assert_called_once_with()
        get_node_list.assert_called_once_with()
        subscribe.assert_called_once_with(entrypoint.on_receive, "meshtastic.receive")
        init_nodedb.assert_called_once_with()
        seed_demo_messages.assert_called_once_with()
        load_messages.assert_called_once_with()

    def test_ensure_min_rows_retries_until_terminal_is_large_enough(self) -> None:
        stdscr = mock.Mock()
        stdscr.getmaxyx.side_effect = [(10, 80), (11, 80)]

        with mock.patch.object(entrypoint, "dialog") as dialog:
            with mock.patch.object(entrypoint.curses, "update_lines_cols") as update_lines_cols:
                entrypoint.ensure_min_rows(stdscr, min_rows=11)

        dialog.assert_called_once()
        update_lines_cols.assert_called_once_with()
        stdscr.clear.assert_called_once_with()
        stdscr.refresh.assert_called_once_with()

    def test_start_prints_help_and_exits_zero(self) -> None:
        parser = mock.Mock()

        with mock.patch.object(entrypoint.sys, "argv", ["contact", "--help"]):
            with mock.patch.object(entrypoint, "setup_parser", return_value=parser):
                with mock.patch.object(entrypoint.sys, "exit", side_effect=SystemExit(0)) as exit_mock:
                    with self.assertRaises(SystemExit) as raised:
                        entrypoint.start()

        self.assertEqual(raised.exception.code, 0)
        parser.print_help.assert_called_once_with()
        exit_mock.assert_called_once_with(0)

    def test_start_runs_curses_wrapper_and_closes_interface(self) -> None:
        interface = mock.Mock()
        interface_state.interface = interface

        with mock.patch.object(entrypoint.sys, "argv", ["contact"]):
            with mock.patch.object(entrypoint.curses, "wrapper") as wrapper:
                entrypoint.start()

        wrapper.assert_called_once_with(entrypoint.main)
        interface.close.assert_called_once_with()

    def test_start_does_not_crash_when_wrapper_returns_without_interface(self) -> None:
        interface_state.interface = None

        with mock.patch.object(entrypoint.sys, "argv", ["contact"]):
            with mock.patch.object(entrypoint.curses, "wrapper") as wrapper:
                entrypoint.start()

        wrapper.assert_called_once_with(entrypoint.main)

    def test_main_returns_cleanly_when_user_closes_missing_node_dialog(self) -> None:
        stdscr = mock.Mock()
        args = Namespace(settings=False, demo_screenshot=False)

        with mock.patch.object(entrypoint, "setup_colors"):
            with mock.patch.object(entrypoint, "ensure_min_rows"):
                with mock.patch.object(entrypoint, "draw_splash"):
                    with mock.patch.object(entrypoint, "setup_parser") as setup_parser:
                        with mock.patch.object(entrypoint, "initialize_runtime_interface_with_retry", return_value=None):
                            with mock.patch.object(entrypoint, "initialize_globals") as initialize_globals:
                                setup_parser.return_value.parse_args.return_value = args
                                entrypoint.main(stdscr)

        initialize_globals.assert_not_called()

    def test_start_handles_keyboard_interrupt(self) -> None:
        interface = mock.Mock()
        interface_state.interface = interface

        with mock.patch.object(entrypoint.sys, "argv", ["contact"]):
            with mock.patch.object(entrypoint.curses, "wrapper", side_effect=KeyboardInterrupt):
                with mock.patch.object(entrypoint.sys, "exit", side_effect=SystemExit(0)) as exit_mock:
                    with self.assertRaises(SystemExit) as raised:
                        entrypoint.start()

        self.assertEqual(raised.exception.code, 0)
        interface.close.assert_called_once_with()
        exit_mock.assert_called_once_with(0)

    def test_start_handles_keyboard_interrupt_with_no_interface(self) -> None:
        interface_state.interface = None

        with mock.patch.object(entrypoint.sys, "argv", ["contact"]):
            with mock.patch.object(entrypoint.curses, "wrapper", side_effect=KeyboardInterrupt):
                with mock.patch.object(entrypoint.sys, "exit", side_effect=SystemExit(0)) as exit_mock:
                    with self.assertRaises(SystemExit) as raised:
                        entrypoint.start()

        self.assertEqual(raised.exception.code, 0)
        exit_mock.assert_called_once_with(0)

    def test_start_handles_fatal_exception_and_exits_one(self) -> None:
        with mock.patch.object(entrypoint.sys, "argv", ["contact"]):
            with mock.patch.object(entrypoint.curses, "wrapper", side_effect=RuntimeError("boom")):
                with mock.patch.object(entrypoint.curses, "endwin") as endwin:
                    with mock.patch.object(entrypoint.traceback, "print_exception") as print_exception:
                        with mock.patch("builtins.print") as print_mock:
                            with mock.patch.object(entrypoint.sys, "exit", side_effect=SystemExit(1)) as exit_mock:
                                with self.assertRaises(SystemExit) as raised:
                                    entrypoint.start()

        self.assertEqual(raised.exception.code, 1)
        endwin.assert_called_once_with()
        exception_type, exception, exception_traceback = print_exception.call_args_list[-1].args
        self.assertIs(exception_type, RuntimeError)
        self.assertEqual(str(exception), "boom")
        self.assertIsNotNone(exception_traceback)
        print_mock.assert_any_call("Fatal error:", mock.ANY)
        exit_mock.assert_called_once_with(1)
