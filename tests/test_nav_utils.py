import unittest
from unittest import mock

from contact.ui import nav_utils
from contact.ui.nav_utils import truncate_with_ellipsis, wrap_text
from contact.utilities.shared_state import ui_state


class NavUtilsTests(unittest.TestCase):
    def setUp(self) -> None:
        ui_state.current_window = 0
        ui_state.node_list = []
        ui_state.start_index = [0, 0, 0]

    def test_wrap_text_splits_wide_characters_by_display_width(self) -> None:
        self.assertEqual(wrap_text("🔐🔐🔐", 4), ["🔐", "🔐", "🔐"])

    def test_truncate_with_ellipsis_respects_display_width(self) -> None:
        self.assertEqual(truncate_with_ellipsis("🔐Alpha", 5), "🔐Al…")

    def test_highlight_line_reserves_scroll_arrow_column_for_nodes(self) -> None:
        ui_state.current_window = 2
        ui_state.start_index = [0, 0, 0]
        menu_win = mock.Mock()
        menu_win.getbegyx.return_value = (0, 0)
        menu_win.getmaxyx.return_value = (8, 20)
        menu_pad = mock.Mock()
        menu_pad.getmaxyx.return_value = (4, 20)

        with mock.patch.object(nav_utils, "get_node_color", side_effect=[11, 22]):
            nav_utils.highlight_line(menu_win, menu_pad, 0, 1, 5)

        self.assertEqual(
            menu_pad.chgat.call_args_list,
            [mock.call(0, 1, 16, 11), mock.call(1, 1, 16, 22)],
        )
