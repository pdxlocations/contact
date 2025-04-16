# contact/ui/navigation_utils.py

import curses
from contact.ui.colors import get_color

save_option = "Save Changes"
sensitive_settings = ["Reboot", "Reset Node DB", "Shutdown", "Factory Reset"]


def move_highlight(
    old_idx: int,
    new_idx: int,
    options: list[str],
    win: curses.window,
    pad: curses.window,
    *,
    start_index_ref: list[int] = None,
    selected_index: int = None,
    max_help_lines: int = 0,
    show_save: bool = False,
    help_win: curses.window = None,
    help_updater=None,
    field_mapping=None,
    menu_path: list[str] = None,
    width: int = 80,
    sensitive_mode: bool = False,
):
    if old_idx == new_idx:
        return

    max_index = len(options) + (1 if show_save else 0) - 1
    visible_height = win.getmaxyx()[0] - 5 - (2 if show_save else 0)

    # Scrolling logic
    if start_index_ref is not None:
        if new_idx == max_index and show_save:
            pass
        elif new_idx < start_index_ref[0]:
            start_index_ref[0] = new_idx
        elif new_idx >= start_index_ref[0] + visible_height:
            start_index_ref[0] = new_idx - visible_height
        start_index_ref[0] = max(
            0, min(start_index_ref[0], max_index - visible_height + 1)
        )

    scroll = start_index_ref[0] if start_index_ref else 0

    # Clear previous highlight
    if show_save and old_idx == max_index:
        win.chgat(
            win.getmaxyx()[0] - 2,
            (width - len(save_option)) // 2,
            len(save_option),
            get_color("settings_save"),
        )
    else:
        color = (
            "settings_sensitive"
            if sensitive_mode and options[old_idx] in sensitive_settings
            else "settings_default"
        )
        pad.chgat(old_idx, 0, pad.getmaxyx()[1], get_color(color))

    # Apply new highlight
    if show_save and new_idx == max_index:
        win.chgat(
            win.getmaxyx()[0] - 2,
            (width - len(save_option)) // 2,
            len(save_option),
            get_color("settings_save", reverse=True),
        )
    else:
        color = (
            "settings_sensitive"
            if sensitive_mode and options[new_idx] in sensitive_settings
            else "settings_default"
        )
        pad.chgat(new_idx, 0, pad.getmaxyx()[1], get_color(color, reverse=True))

    win.refresh()
    pad.refresh(
        scroll,
        0,
        win.getbegyx()[0] + 3,
        win.getbegyx()[1] + 4,
        win.getbegyx()[0] + 3 + visible_height,
        win.getbegyx()[1] + win.getmaxyx()[1] - 4,
    )

    # Optional help update
    if help_win and help_updater and menu_path and selected_index is not None:
        selected_option = (
            options[selected_index] if selected_index < len(options) else None
        )
        help_y = win.getbegyx()[0] + win.getmaxyx()[0]
        help_updater(
            help_win,
            field_mapping,
            menu_path,
            selected_option,
            max_help_lines,
            width,
            help_y,
            win.getbegyx()[1],
        )


def draw_arrows(
    win: curses.window, visible_height: int, max_index: int, start_index: int
) -> None:
    if visible_height < max_index:
        if start_index > 0:
            win.addstr(3, 2, "▲", get_color("settings_default"))
        else:
            win.addstr(3, 2, " ", get_color("settings_default"))

        if max_index - start_index > visible_height:
            win.addstr(visible_height + 3, 2, "▼", get_color("settings_default"))
        else:
            win.addstr(visible_height + 3, 2, " ", get_color("settings_default"))
