import unittest
from unittest import mock

from contact.ui import dialog as dialog_module
from contact.utilities.shared_state import menu_state, ui_state


class _FakeWindow:
    def __init__(self, height: int, width: int) -> None:
        self.height = height
        self.width = width
        self.children = []
        self.added_strings = []
        self._getch_values = [10]

    def erase(self) -> None:
        return None

    def bkgd(self, *_args) -> None:
        return None

    def attrset(self, *_args) -> None:
        return None

    def border(self, *_args) -> None:
        return None

    def addstr(self, y: int, x: int, text: str, *_args) -> None:
        self.added_strings.append((y, x, text))

    def derwin(self, height: int, width: int, _y: int, _x: int):
        child = _FakeWindow(height, width)
        self.children.append(child)
        return child

    def noutrefresh(self) -> None:
        return None

    def keypad(self, *_args) -> None:
        return None

    def timeout(self, *_args) -> None:
        return None

    def getch(self) -> int:
        return self._getch_values.pop(0) if self._getch_values else -1

    def refresh(self) -> None:
        return None

    def getmaxyx(self):
        return (self.height, self.width)


class DialogTests(unittest.TestCase):
    def setUp(self) -> None:
        self.previous_window = ui_state.current_window
        self.previous_start_index = list(ui_state.start_index)
        self.previous_need_redraw = menu_state.need_redraw

    def tearDown(self) -> None:
        ui_state.current_window = self.previous_window
        ui_state.start_index = self.previous_start_index
        menu_state.need_redraw = self.previous_need_redraw

    def test_dialog_renders_full_message_when_width_is_sufficient(self) -> None:
        root = _FakeWindow(5, 33)
        ui_state.current_window = 0
        ui_state.start_index = [0, 0, 0]
        menu_state.need_redraw = False

        with mock.patch.object(dialog_module, "t_text", side_effect=lambda text: text):
            with mock.patch.object(dialog_module, "get_color", return_value=0):
                with mock.patch.object(dialog_module, "draw_main_arrows"):
                    with mock.patch.object(dialog_module.curses, "update_lines_cols"):
                        with mock.patch.object(dialog_module.curses, "doupdate"):
                            with mock.patch.object(dialog_module.curses, "LINES", 24, create=True):
                                with mock.patch.object(dialog_module.curses, "COLS", 80, create=True):
                                    with mock.patch.object(dialog_module.curses, "newwin", return_value=root):
                                        dialog_module.dialog("Bot Responder", "Bot responder is now Enabled.")

        self.assertTrue(root.children)
        message_text = [text for _y, _x, text in root.children[0].added_strings]
        self.assertIn("Bot responder is now Enabled.", message_text)


if __name__ == "__main__":
    unittest.main()
