import curses
from contact.ui.colors import get_color


def draw_splash(stdscr: object) -> None:
    """Draw the splash screen with a logo and connecting message."""
    curses.curs_set(0)

    stdscr.clear()
    stdscr.bkgd(get_color("background"))

    height, width = stdscr.getmaxyx()
    message_1 = "/ Λ"
    message_2 = "/ / \\"
    message_3 = "P W R D"
    message_4 = "connecting..."

    start_x = width // 2 - len(message_1) // 2
    start_x2 = width // 2 - len(message_4) // 2
    start_y = height // 2 - 1
    stdscr.addstr(start_y, start_x, message_1, get_color("splash_logo", bold=True))
    stdscr.addstr(start_y + 1, start_x - 1, message_2, get_color("splash_logo", bold=True))
    stdscr.addstr(start_y + 2, start_x - 2, message_3, get_color("splash_logo", bold=True))
    stdscr.addstr(start_y + 4, start_x2, message_4, get_color("splash_text"))

    stdscr.attrset(get_color("window_frame"))
    stdscr.box()
    stdscr.refresh()
    curses.napms(500)
