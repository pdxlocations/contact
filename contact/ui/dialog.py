import curses
from contact.ui.colors import get_color


def dialog(title: str, message: str) -> None:

    height, width = curses.LINES, curses.COLS

    # Calculate dialog dimensions
    message_lines = message.splitlines()
    max_line_length = max(len(l) for l in message_lines)
    dialog_width = max(len(title) + 4, max_line_length + 4)
    dialog_height = len(message_lines) + 4
    x = (width - dialog_width) // 2
    y = (height - dialog_height) // 2

    # Create dialog window
    win = curses.newwin(dialog_height, dialog_width, y, x)
    win.bkgd(get_color("background"))
    win.attrset(get_color("window_frame"))
    win.border(0)

    # Add title
    win.addstr(0, 2, title, get_color("settings_default"))

    # Add message (centered)
    for i, line in enumerate(message_lines):
        msg_x = (dialog_width - len(line)) // 2
        win.addstr(2 + i, msg_x, line, get_color("settings_default"))

    # Add centered OK button
    ok_text = " Ok "
    win.addstr(
        dialog_height - 2,
        (dialog_width - len(ok_text)) // 2,
        ok_text,
        get_color("settings_default", reverse=True),
    )

    # Refresh dialog window
    win.refresh()

    # Get user input
    while True:
        char = win.getch()
        if char in (curses.KEY_ENTER, 10, 13, 32, 27):  # Enter, space, or Esc
            win.erase()
            win.refresh()
            return
