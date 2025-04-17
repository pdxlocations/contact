import curses
import contact.ui.default_config as config

COLOR_MAP = {
    "black": curses.COLOR_BLACK,
    "red": curses.COLOR_RED,
    "green": curses.COLOR_GREEN,
    "yellow": curses.COLOR_YELLOW,
    "blue": curses.COLOR_BLUE,
    "magenta": curses.COLOR_MAGENTA,
    "cyan": curses.COLOR_CYAN,
    "white": curses.COLOR_WHITE,
}


def setup_colors(reinit: bool = False) -> None:
    """
    Initialize curses color pairs based on the COLOR_CONFIG.
    """
    curses.start_color()
    if reinit:
        conf = config.initialize_config()
        config.assign_config_variables(conf)

    for idx, (category, (fg_name, bg_name)) in enumerate(config.COLOR_CONFIG.items(), start=1):
        fg = COLOR_MAP.get(fg_name.lower(), curses.COLOR_WHITE)
        bg = COLOR_MAP.get(bg_name.lower(), curses.COLOR_BLACK)
        curses.init_pair(idx, fg, bg)
        config.COLOR_CONFIG[category] = idx
    print()


def get_color(category: str, bold: bool = False, reverse: bool = False, underline: bool = False) -> int:
    """
    Retrieve a curses color pair with optional attributes.
    """
    color = curses.color_pair(config.COLOR_CONFIG[category])
    if bold:
        color |= curses.A_BOLD
    if reverse:
        color |= curses.A_REVERSE
    if underline:
        color |= curses.A_UNDERLINE
    return color
