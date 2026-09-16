import curses
import textwrap
from contact.ui.colors import get_color
from contact.version import __version__


def draw_splash(stdscr: object, status: str = "connecting...") -> None:
    """Draw the splash screen with a logo and connecting message."""
    curses.curs_set(0)

    stdscr.clear()
    stdscr.bkgd(get_color("background"))

    height, width = stdscr.getmaxyx()
    message_1 = "/ Λ"
    message_2 = "/ / \\"
    message_3 = "P W R D"

    start_x = width // 2 - len(message_1) // 2
    start_y = height // 2 - 1
    stdscr.addstr(start_y, start_x, message_1, get_color("splash_logo", bold=True))
    stdscr.addstr(start_y + 1, start_x - 1, message_2, get_color("splash_logo", bold=True))
    stdscr.addstr(start_y + 2, start_x - 2, message_3, get_color("splash_logo", bold=True))
    if __version__:
        ver_line = f"v{__version__}"
        ver_x = max(1, (width - len(ver_line)) // 2)
        ver_y = start_y + 3
        if ver_y < height - 1:
            stdscr.addstr(ver_y, ver_x, ver_line, get_color("splash_text"))
    status_lines = []
    for line in status.splitlines():
        status_lines.extend(textwrap.wrap(line, max(1, width - 4)) or [""])
    for offset, line in enumerate(status_lines):
        row = start_y + 4 + offset
        if row >= height - 1:
            break
        stdscr.addstr(row, max(1, (width - len(line)) // 2), line, get_color("splash_text"))

    stdscr.attrset(get_color("window_frame"))
    stdscr.box()
    stdscr.refresh()
    curses.napms(500)
