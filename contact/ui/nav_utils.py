import curses
import re
from unicodedata import east_asian_width

from contact.ui.colors import get_color
from contact.utilities.i18n import t
from contact.utilities.control_utils import transform_menu_path
from typing import Any, Optional, List, Dict
from contact.utilities.singleton import interface_state, ui_state


def get_node_color(node_index: int, reverse: bool = False):
    node_num = ui_state.node_list[node_index]
    node = interface_state.interface.nodesByNum.get(node_num, {})
    if node.get("isFavorite"):
        return get_color("node_favorite", reverse=reverse)
    elif node.get("isIgnored"):
        return get_color("node_ignored", reverse=reverse)
    return get_color("settings_default", reverse=reverse)


# Aliases
Segment = tuple[str, str, bool, bool]
WrappedLine = List[Segment]

sensitive_settings = ["Reboot", "Reset Node DB", "Shutdown", "Factory Reset"]
save_option = "Save Changes"


def get_save_option_label() -> str:
    return t("ui.save_changes", default=save_option)

def move_highlight(
    old_idx: int, options: List[str], menu_win: curses.window, menu_pad: curses.window, **kwargs: Any
) -> None:

    show_save_option = None
    start_index = [0]
    help_text = None
    max_help_lines = 0
    help_win = None

    if "help_win" in kwargs:
        help_win = kwargs["help_win"]

    if "menu_state" in kwargs:
        new_idx = kwargs["menu_state"].selected_index
        show_save_option = kwargs["menu_state"].show_save_option
        start_index = kwargs["menu_state"].start_index
        transformed_path = transform_menu_path(kwargs["menu_state"].menu_path)
    else:
        new_idx = kwargs["selected_index"]
        transformed_path = []

    if "help_text" in kwargs:
        help_text = kwargs["help_text"]

    if "max_help_lines" in kwargs:
        max_help_lines = kwargs["max_help_lines"]
    if not options:
        return

    if old_idx == new_idx:  # No-op
        return

    max_index = len(options) + (1 if show_save_option else 0) - 1
    visible_height = menu_win.getmaxyx()[0] - 5 - (2 if show_save_option else 0)

    # Adjust menu_state.start_index only when moving out of visible range
    if new_idx == max_index and show_save_option:
        pass
    elif new_idx < start_index[-1]:  # Moving above the visible area
        start_index[-1] = new_idx
    elif new_idx >= start_index[-1] + visible_height:  # Moving below the visible area
        start_index[-1] = new_idx - visible_height

    # Ensure menu_state.start_index is within bounds
    start_index[-1] = max(0, min(start_index[-1], max_index - visible_height + 1))

    # Clear old selection
    if show_save_option and old_idx == max_index:
        win_h, win_w = menu_win.getmaxyx()
        save_label = get_save_option_label()
        menu_win.chgat(
            win_h - 2, (win_w - len(save_label)) // 2, len(save_label), get_color("settings_save")
        )
    elif 0 <= old_idx < len(options):
        menu_pad.chgat(
            old_idx,
            0,
            menu_pad.getmaxyx()[1],
            (
                get_color("settings_sensitive")
                if options[old_idx] in sensitive_settings
                else get_color("settings_default")
            ),
        )

    # Highlight new selection
    if show_save_option and new_idx == max_index:
        win_h, win_w = menu_win.getmaxyx()
        save_label = get_save_option_label()
        menu_win.chgat(
            win_h - 2,
            (win_w - len(save_label)) // 2,
            len(save_label),
            get_color("settings_save", reverse=True),
        )
    elif 0 <= new_idx < len(options):
        menu_pad.chgat(
            new_idx,
            0,
            menu_pad.getmaxyx()[1],
            (
                get_color("settings_sensitive", reverse=True)
                if options[new_idx] in sensitive_settings
                else get_color("settings_default", reverse=True)
            ),
        )

    menu_win.refresh()

    # Refresh pad only if scrolling is needed
    menu_pad.refresh(
        start_index[-1],
        0,
        menu_win.getbegyx()[0] + 3,
        menu_win.getbegyx()[1] + 4,
        menu_win.getbegyx()[0] + 3 + visible_height,
        menu_win.getbegyx()[1] + menu_win.getmaxyx()[1] - 4,
    )

    # Update help window only if help_text is populated
    selected_option = options[new_idx] if new_idx < len(options) else None
    help_y = menu_win.getbegyx()[0] + menu_win.getmaxyx()[0]
    if help_win:
        win_h, win_w = menu_win.getmaxyx()
        help_win = update_help_window(
            help_win,
            help_text,
            transformed_path,
            selected_option,
            max_help_lines,
            win_w,
            help_y,
            menu_win.getbegyx()[1],
        )

    draw_arrows(menu_win, visible_height, max_index, start_index, show_save_option)


def draw_arrows(
    win: object, visible_height: int, max_index: int, start_index: List[int], show_save_option: bool
) -> None:

    mi = max_index - (2 if show_save_option else 0)

    if visible_height < mi:
        if start_index[-1] > 0:
            win.addstr(3, 2, "▲", get_color("settings_default"))
        else:
            win.addstr(3, 2, " ", get_color("settings_default"))

        if mi - start_index[-1] >= visible_height + (0 if show_save_option else 1):
            win.addstr(visible_height + 3, 2, "▼", get_color("settings_default"))
        else:
            win.addstr(visible_height + 3, 2, " ", get_color("settings_default"))


def update_help_window(
    help_win: object,  # curses window or None
    help_text: Dict[str, str],
    transformed_path: List[str],
    selected_option: Optional[str],
    max_help_lines: int,
    width: int,
    help_y: int,
    help_x: int,
) -> object:  # returns a curses window
    """Handles rendering the help window consistently."""

    # Clamp target position and width to the current terminal size
    help_x = max(0, help_x)
    help_y = max(0, help_y)
    # Ensure requested width fits on screen from help_x
    max_w_from_x = max(1, curses.COLS - help_x)
    safe_width = min(width, max_w_from_x)
    # Always leave a minimal border area; enforce a minimum usable width of 3
    safe_width = max(3, safe_width)

    wrapped_help = get_wrapped_help_text(help_text, transformed_path, selected_option, safe_width, max_help_lines)

    help_height = min(len(wrapped_help) + 2, max_help_lines + 2)  # +2 for border
    help_height = max(help_height, 3)  # Ensure at least 3 rows (1 text + border)

    # Re-clamp Y to keep the window visible
    if help_y + help_height > curses.LINES:
        help_y = max(0, curses.LINES - help_height)

    # If width would overflow the screen, shrink it
    if help_x + safe_width > curses.COLS:
        safe_width = max(3, curses.COLS - help_x)

    # Create or update the help window
    if help_win is None:
        help_win = curses.newwin(help_height, safe_width, help_y, help_x)
    else:
        help_win.erase()
        help_win.refresh()
        help_win.resize(help_height, safe_width)
        try:
            help_win.mvwin(help_y, help_x)
        except curses.error:
            # If moving fails due to edge conditions, pin to (0,0) as a fallback
            help_y = 0
            help_x = 0
            help_win.mvwin(help_y, help_x)

    help_win.bkgd(get_color("background"))
    help_win.attrset(get_color("window_frame"))
    help_win.border()

    for idx, line_segments in enumerate(wrapped_help):
        x_pos = 2  # Start after border
        for text, color, bold, underline in line_segments:
            try:
                attr = get_color(color, bold=bold, underline=underline)
                help_win.addstr(1 + idx, x_pos, text, attr)
                x_pos += len(text)
            except curses.error:
                pass  # Prevent crashes

    help_win.refresh()
    return help_win


def get_wrapped_help_text(
    help_text: Dict[str, str], transformed_path: List[str], selected_option: Optional[str], width: int, max_lines: int
) -> List[WrappedLine]:
    """Fetches and formats help text for display, ensuring it fits within the allowed lines."""

    full_help_key = ".".join(transformed_path + [selected_option]) if selected_option else None
    help_content = help_text.get(full_help_key, t("ui.help.no_help", default="No help available."))

    wrap_width = max(width - 6, 10)  # Ensure a valid wrapping width

    # Color replacements
    color_mappings = {
        r"\[warning\](.*?)\[/warning\]": ("settings_warning", True, False),  # Red for warnings
        r"\[note\](.*?)\[/note\]": ("settings_note", True, False),  # Green for notes
        r"\[underline\](.*?)\[/underline\]": ("settings_default", False, True),  # Underline
        r"\\033\[31m(.*?)\\033\[0m": ("settings_warning", True, False),  # Red text
        r"\\033\[32m(.*?)\\033\[0m": ("settings_note", True, False),  # Green text
        r"\\033\[4m(.*?)\\033\[0m": ("settings_default", False, True),  # Underline
    }

    def extract_ansi_segments(text: str) -> List[Segment]:
        """Extracts and replaces ANSI color codes, ensuring spaces are preserved."""
        matches = []
        last_pos = 0
        pattern_matches = []

        # Find all matches and store their positions
        for pattern, (color, bold, underline) in color_mappings.items():
            for match in re.finditer(pattern, text):
                pattern_matches.append((match.start(), match.end(), match.group(1), color, bold, underline))

        # Sort matches by start position to process sequentially
        pattern_matches.sort(key=lambda x: x[0])

        for start, end, content, color, bold, underline in pattern_matches:
            # Preserve non-matching text including spaces
            if last_pos < start:
                segment = text[last_pos:start]
                matches.append((segment, "settings_default", False, False))

            # Append the colored segment
            matches.append((content, color, bold, underline))
            last_pos = end

        # Preserve any trailing text
        if last_pos < len(text):
            matches.append((text[last_pos:], "settings_default", False, False))

        return matches

    def wrap_ansi_text(segments: List[Segment], wrap_width: int) -> List[WrappedLine]:
        """Wraps text while preserving ANSI formatting and spaces."""
        wrapped_lines = []
        line_buffer = []
        line_length = 0

        for text, color, bold, underline in segments:
            words = re.findall(r"\S+|\s+", text)  # Capture words and spaces separately

            for word in words:
                word_length = len(word)

                if line_length + word_length > wrap_width and word.strip():
                    # If the word (ignoring spaces) exceeds width, wrap the line
                    wrapped_lines.append(line_buffer)
                    line_buffer = []
                    line_length = 0

                line_buffer.append((word, color, bold, underline))
                line_length += word_length

        if line_buffer:
            wrapped_lines.append(line_buffer)

        return wrapped_lines

    raw_lines = help_content.split("\\n")  # Preserve new lines
    wrapped_help = []

    for raw_line in raw_lines:
        color_segments = extract_ansi_segments(raw_line)
        wrapped_segments = wrap_ansi_text(color_segments, wrap_width)
        wrapped_help.extend(wrapped_segments)
        pass

    # Trim and add ellipsis if needed
    if len(wrapped_help) > max_lines:
        wrapped_help = wrapped_help[:max_lines]
        wrapped_help[-1].append(("...", "settings_default", False, False))

    return wrapped_help


def text_width(text: str) -> int:
    return sum(2 if east_asian_width(c) in "FW" else 1 for c in text)


def wrap_text(text: str, wrap_width: int) -> List[str]:
    """Wraps text while preserving spaces and breaking long words."""

    whitespace = "\t\n\x0b\x0c\r "
    whitespace_trans = dict.fromkeys(map(ord, whitespace), ord(" "))
    text = text.translate(whitespace_trans)

    words = re.findall(r"\S+|\s+", text)  # Capture words and spaces separately
    wrapped_lines = []
    line_buffer = ""
    line_length = 0
    margin = 2  # Left and right margin
    wrap_width -= margin

    for word in words:
        word_length = text_width(word)

        if word_length > wrap_width:  # Break long words
            if line_buffer:
                wrapped_lines.append(line_buffer.strip())
                line_buffer = ""
                line_length = 0
            for i in range(0, word_length, wrap_width):
                wrapped_lines.append(word[i : i + wrap_width])
            continue

        if line_length + word_length > wrap_width and word.strip():
            wrapped_lines.append(line_buffer.strip())
            line_buffer = ""
            line_length = 0

        line_buffer += word
        line_length += word_length

    if line_buffer:
        wrapped_lines.append(line_buffer.strip())

    return wrapped_lines


def move_main_highlight(
    old_idx: int, new_idx, options: List[str], menu_win: curses.window, menu_pad: curses.window, ui_state: object
) -> None:

    if old_idx == new_idx:  # No-op
        return

    max_index = len(options) - 1
    visible_height = menu_win.getmaxyx()[0] - 2

    if new_idx < ui_state.start_index[ui_state.current_window]:  # Moving above the visible area
        ui_state.start_index[ui_state.current_window] = new_idx
    elif new_idx >= ui_state.start_index[ui_state.current_window] + visible_height:  # Moving below the visible area
        ui_state.start_index[ui_state.current_window] = new_idx - visible_height + 1

    # Ensure start_index is within bounds
    ui_state.start_index[ui_state.current_window] = max(
        0, min(ui_state.start_index[ui_state.current_window], max_index - visible_height + 1)
    )

    highlight_line(menu_win, menu_pad, old_idx, new_idx, visible_height)

    if ui_state.current_window == 0:  # hack to fix max_index
        max_index += 1

    draw_main_arrows(menu_win, max_index, window=ui_state.current_window)
    menu_win.refresh()


def highlight_line(
    menu_win: curses.window, menu_pad: curses.window, old_idx: int, new_idx: int, visible_height: int
) -> None:

    if ui_state.current_window == 0:
        color_old = (
            get_color("channel_selected") if old_idx == ui_state.selected_channel else get_color("channel_list")
        )
        color_new = get_color("channel_list", reverse=True) if True else get_color("channel_list", reverse=True)
        menu_pad.chgat(old_idx, 1, menu_pad.getmaxyx()[1] - 4, color_old)
        menu_pad.chgat(new_idx, 1, menu_pad.getmaxyx()[1] - 4, color_new)

    elif ui_state.current_window == 2:
        menu_pad.chgat(old_idx, 1, menu_pad.getmaxyx()[1] - 4, get_node_color(old_idx))
        menu_pad.chgat(new_idx, 1, menu_pad.getmaxyx()[1] - 4, get_node_color(new_idx, reverse=True))

    menu_win.refresh()

    # Refresh pad only if scrolling is needed
    menu_pad.refresh(
        ui_state.start_index[ui_state.current_window],
        0,
        menu_win.getbegyx()[0] + 1,
        menu_win.getbegyx()[1] + 1,
        menu_win.getbegyx()[0] + visible_height,
        menu_win.getbegyx()[1] + menu_win.getmaxyx()[1] - 3,
    )


def draw_main_arrows(win: object, max_index: int, window: int, **kwargs) -> None:

    height, width = win.getmaxyx()
    usable_height = height - 2
    usable_width = width - 2

    if window == 1 and ui_state.display_log:
        if log_height := kwargs.get("log_height"):
            usable_height -= log_height - 1

    if usable_height < max_index:
        if ui_state.start_index[window] > 0:
            win.addstr(1, usable_width, "▲", get_color("settings_default"))
        else:
            win.addstr(1, usable_width, " ", get_color("settings_default"))

        if max_index - ui_state.start_index[window] - 1 >= usable_height:
            win.addstr(usable_height, usable_width, "▼", get_color("settings_default"))
        else:
            win.addstr(usable_height, usable_width, " ", get_color("settings_default"))
    else:
        win.addstr(1, usable_width, " ", get_color("settings_default"))
        win.addstr(usable_height, usable_width, " ", get_color("settings_default"))


def get_msg_window_lines(messages_win, packetlog_win) -> None:
    packetlog_height = packetlog_win.getmaxyx()[0] - 1 if ui_state.display_log else 0
    return messages_win.getmaxyx()[0] - 2 - packetlog_height
