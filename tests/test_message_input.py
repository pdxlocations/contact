import unittest
from contextlib import ExitStack
from unittest import mock

from contact.ui import contact_ui
from contact.utilities.singleton import ui_state
from tests.test_support import reset_singletons


class MessageInputTests(unittest.TestCase):
    def setUp(self):
        reset_singletons()
        ui_state.current_window = 1
        for name in ("refresh_message_highlight", "refresh_main_window", "get_color"):
            patcher = mock.patch.object(contact_ui, name, return_value=1)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.addCleanup(reset_singletons)

    def test_keyboard_loop_sends_edited_draft_after_resize(self):
        win = mock.Mock()
        win.get_wch.side_effect = [
            "a", "b", "c", contact_ui.curses.KEY_LEFT,
            contact_ui.curses.KEY_DC, "d", contact_ui.curses.KEY_BACKSPACE,
            "e", contact_ui.curses.KEY_RESIZE, "\n", "\x1b",
        ]
        with ExitStack() as stack:
            stack.enter_context(mock.patch.object(contact_ui, "entry_win", win))
            for name in ("get_channels", "handle_resize", "process_pending_ui_updates", "draw_message_input"):
                stack.enter_context(mock.patch.object(contact_ui, name))
            stack.enter_context(mock.patch.object(contact_ui, "interface_is_connected", return_value=True))
            stack.enter_context(mock.patch.object(contact_ui, "drain_resize_events", return_value=None))
            send = stack.enter_context(mock.patch.object(contact_ui, "handle_enter", return_value=""))
            contact_ui.main_ui(mock.Mock())
        send.assert_called_once_with("abe")
        self.assertEqual(contact_ui.input_text, "")
        self.assertEqual(ui_state.input_cursor, 0)

    def test_typing_focuses_input_and_edits_at_cursor(self):
        draft = contact_ui.insert_input_text("", "helo")
        self.assertTrue(ui_state.input_focused)
        with mock.patch.object(contact_ui, "input_text", draft):
            contact_ui.handle_leftright(contact_ui.curses.KEY_LEFT)
        draft = contact_ui.insert_input_text(draft, "l")
        self.assertEqual(draft, "hello")
        self.assertEqual(ui_state.input_cursor, 4)
        draft = contact_ui.handle_backspace(mock.Mock(), draft)
        self.assertEqual(draft, "helo")
        self.assertEqual(ui_state.input_cursor, 3)

    def test_up_and_down_return_to_messages_without_scrolling(self):
        for handler in (contact_ui.handle_up, contact_ui.handle_down):
            ui_state.input_focused = True
            ui_state.input_cursor = 2
            with mock.patch.object(contact_ui, "scroll_messages") as scroll:
                handler()
            self.assertFalse(ui_state.input_focused)
            self.assertEqual(ui_state.current_window, 1)
            self.assertEqual(ui_state.input_cursor, 2)
            scroll.assert_not_called()

    def test_cursor_stops_at_draft_boundaries(self):
        ui_state.input_focused = True
        with mock.patch.object(contact_ui, "input_text", "abc"):
            contact_ui.handle_leftright(contact_ui.curses.KEY_LEFT)
            self.assertEqual(ui_state.input_cursor, 0)
            self.assertEqual(contact_ui.handle_backspace(mock.Mock(), "abc"), "abc")
            contact_ui.handle_end()
            contact_ui.handle_leftright(contact_ui.curses.KEY_RIGHT)
            self.assertEqual(ui_state.input_cursor, 3)
            contact_ui.handle_home()
            self.assertEqual(ui_state.input_cursor, 0)

    def test_redraw_clears_line_and_shows_text_after_cursor(self):
        win = mock.Mock()
        win.getmaxyx.return_value = (3, 30)
        ui_state.input_focused = True
        ui_state.input_cursor = 2
        with mock.patch.object(contact_ui, "entry_win", win), mock.patch.object(contact_ui.curses, "curs_set"):
            contact_ui.draw_message_input("hello")
        win.addstr.assert_any_call(1, 1, " " * 28, 1)
        win.addstr.assert_any_call(1, 1, "Message: hello", 1)
        win.move.assert_called_once_with(1, 12)
        contact_ui.get_color.assert_any_call("window_frame_selected")

    def test_long_draft_scrolls_to_cursor_with_reply_context(self):
        win = mock.Mock()
        win.getmaxyx.return_value = (3, 24)
        ui_state.reply_context = "Reply to someone: "
        ui_state.input_cursor = 20
        with mock.patch.object(contact_ui, "entry_win", win), mock.patch.object(contact_ui.curses, "curs_set"):
            contact_ui.draw_message_input("x" * 20)
        self.assertLess(win.move.call_args.args[1], 23)
        rendered = [call.args[2] for call in win.addstr.call_args_list if call.args[:2] == (1, 1)][-1]
        self.assertEqual(rendered, "Message: " + "x" * 12)
