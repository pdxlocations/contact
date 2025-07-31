import curses
from contact.ui.colors import get_color
from contact.utilities.singleton import menu_state, ui_state


def dialog(title: str, message: str) -> None:
    """Display a dialog with a title and message."""

    previous_window = ui_state.current_window
    ui_state.current_window = 4

    curses.update_lines_cols()
    height, width = curses.LINES, curses.COLS

    # Parse message into lines and calculate dimensions
    message_lines = message.splitlines()
    max_line_length = max(len(l) for l in message_lines)
    dialog_width = max(len(title) + 4, max_line_length + 4)
    dialog_height = len(message_lines) + 4
    x = (width - dialog_width) // 2
    y = (height - dialog_height) // 2

    def draw_window():
        win.erase()
        win.bkgd(get_color("background"))
        win.attrset(get_color("window_frame"))
        win.border(0)

        win.addstr(0, 2, title, get_color("settings_default"))

        for i, line in enumerate(message_lines):
            msg_x = (dialog_width - len(line)) // 2
            win.addstr(2 + i, msg_x, line, get_color("settings_default"))

        ok_text = " Ok "
        win.addstr(
            dialog_height - 2,
            (dialog_width - len(ok_text)) // 2,
            ok_text,
            get_color("settings_default", reverse=True),
        )

        win.refresh()

    win = curses.newwin(dialog_height, dialog_width, y, x)
    draw_window()

    while True:
        win.timeout(200)
        char = win.getch()

        if menu_state.need_redraw:
            menu_state.need_redraw = False
            draw_window()

        if char in (curses.KEY_ENTER, 10, 13, 32, 27):  # Enter, space, Esc
            win.erase()
            win.refresh()
            ui_state.current_window = previous_window
            return

        if char == -1:
            continue
