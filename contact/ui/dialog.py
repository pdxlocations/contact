import curses

from contact.utilities.i18n import t_text
from contact.ui.colors import get_color
from contact.ui.nav_utils import draw_main_arrows
from contact.utilities.singleton import menu_state, ui_state


def dialog(title: str, message: str) -> None:
    title = t_text(title)
    message = t_text(message)
    """Display a dialog with a title and message."""

    previous_window = ui_state.current_window
    ui_state.current_window = 4

    curses.update_lines_cols()
    height, width = curses.LINES, curses.COLS

    # Parse message into lines and calculate dimensions
    message_lines = message.splitlines() or [""]
    max_line_length = max(len(l) for l in message_lines)

    # Desired size
    dialog_width = max(len(title) + 4, max_line_length + 4)
    desired_height = len(message_lines) + 4

    # Clamp dialog size to the screen (leave a 1-cell margin if possible)
    max_w = max(10, width - 2)
    max_h = max(6, height - 2)
    dialog_width = min(dialog_width, max_w)
    dialog_height = min(desired_height, max_h)

    x = max(0, (width - dialog_width) // 2)
    y = max(0, (height - dialog_height) // 2)

    # Ensure we have a start index slot for this dialog window id (4)
    # ui_state.start_index is used by draw_main_arrows()
    try:
        while len(ui_state.start_index) <= 4:
            ui_state.start_index.append(0)
    except Exception:
        # If start_index isn't list-like, fall back to an attribute
        if not hasattr(ui_state, "start_index"):
            ui_state.start_index = [0, 0, 0, 0, 0]

    def visible_message_rows() -> int:
        # Rows available for message text inside the border, excluding title row and OK row.
        # Layout:
        #   row 0: title
        #   rows 1..(dialog_height-3): message viewport (with arrows drawn on a subwindow)
        #   row dialog_height-2: OK button
        # So message viewport height is dialog_height - 3 - 1 + 1 = dialog_height - 3
        return max(1, dialog_height - 4)

    def draw_window():
        win.erase()
        win.bkgd(get_color("background"))
        win.attrset(get_color("window_frame"))
        win.border(0)

        # Title
        try:
            win.addstr(0, 2, title[: max(0, dialog_width - 4)], get_color("settings_default"))
        except curses.error:
            pass

        # Message viewport
        viewport_h = visible_message_rows()
        start = ui_state.start_index[4]
        start = max(0, min(start, max(0, len(message_lines) - viewport_h)))
        ui_state.start_index[4] = start

        # Create a subwindow covering the message region so draw_main_arrows() doesn't collide with the OK row
        msg_win = win.derwin(viewport_h + 2, dialog_width - 2, 1, 1)
        msg_win.erase()

        for i in range(viewport_h):
            idx = start + i
            if idx >= len(message_lines):
                break
            line = message_lines[idx]
            # Hard-trim lines that don't fit
            trimmed = line[: max(0, dialog_width - 6)]
            msg_x = max(0, ((dialog_width - 2) - len(trimmed)) // 2)
            try:
                msg_win.addstr(1 + i, msg_x, trimmed, get_color("settings_default"))
            except curses.error:
                pass

        # Draw arrows only when scrolling is needed
        if len(message_lines) > viewport_h:
            draw_main_arrows(msg_win, len(message_lines) - 1, window=4)
        else:
            # Clear arrow positions if not needed
            try:
                h, w = msg_win.getmaxyx()
                msg_win.addstr(1, w - 2, " ", get_color("settings_default"))
                msg_win.addstr(h - 2, w - 2, " ", get_color("settings_default"))
            except curses.error:
                pass

        msg_win.noutrefresh()

        # OK button
        ok_text = " Ok "
        try:
            win.addstr(
                dialog_height - 2,
                (dialog_width - len(ok_text)) // 2,
                ok_text,
                get_color("settings_default", reverse=True),
            )
        except curses.error:
            pass

        win.noutrefresh()
        curses.doupdate()

    win = curses.newwin(dialog_height, dialog_width, y, x)
    win.keypad(True)
    draw_window()

    while True:
        win.timeout(200)
        char = win.getch()

        if menu_state.need_redraw:
            menu_state.need_redraw = False
            curses.update_lines_cols()
            height, width = curses.LINES, curses.COLS
            draw_window()

        # Close dialog
        ok_selected = True
        if char in (27, curses.KEY_LEFT):  # Esc or Left arrow
            win.erase()
            win.refresh()
            ui_state.current_window = previous_window
            return

        if ok_selected and char in (curses.KEY_ENTER, 10, 13, 32):
            win.erase()
            win.refresh()
            ui_state.current_window = previous_window
            return

        if char == -1:
            continue

        # Scroll if the dialog is clipped vertically
        viewport_h = visible_message_rows()
        if len(message_lines) > viewport_h:
            start = ui_state.start_index[4]
            max_start = max(0, len(message_lines) - viewport_h)

            if char in (curses.KEY_UP, ord("k")):
                ui_state.start_index[4] = max(0, start - 1)
                draw_window()
            elif char in (curses.KEY_DOWN, ord("j")):
                ui_state.start_index[4] = min(max_start, start + 1)
                draw_window()
            elif char == curses.KEY_PPAGE:  # Page up
                ui_state.start_index[4] = max(0, start - viewport_h)
                draw_window()
            elif char == curses.KEY_NPAGE:  # Page down
                ui_state.start_index[4] = min(max_start, start + viewport_h)
                draw_window()
