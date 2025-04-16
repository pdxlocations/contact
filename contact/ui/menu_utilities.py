import curses
import re
from contact.ui.colors import get_color
from contact.utilities.control_utils import transform_menu_path

# Aliases
Segment = tuple[str, str, bool, bool]
WrappedLine = list[Segment]

width = 80
sensitive_settings = ["Reboot", "Reset Node DB", "Shutdown", "Factory Reset"]
save_option = "Save Changes"


def move_highlight(
    old_idx: int,
    options: list[str],
    menu_win: object,
    menu_pad: object,
    menu_state: any,
    help_win: object,
    help_text: dict[str, str],
    max_help_lines: int
) -> None:
    
    if old_idx == menu_state.selected_index:  # No-op
        return

    max_index = len(options) + (1 if menu_state.show_save_option else 0) - 1
    visible_height = menu_win.getmaxyx()[0] - 5 - (2 if menu_state.show_save_option else 0)

    # Adjust menu_state.start_index only when moving out of visible range
    if menu_state.selected_index == max_index and menu_state.show_save_option:
        pass
    elif menu_state.selected_index < menu_state.start_index[-1]:  # Moving above the visible area
        menu_state.start_index[-1] = menu_state.selected_index
    elif menu_state.selected_index >= menu_state.start_index[-1] + visible_height:  # Moving below the visible area
        menu_state.start_index[-1] = menu_state.selected_index - visible_height
    pass

    # Ensure menu_state.start_index is within bounds
    menu_state.start_index[-1] = max(0, min(menu_state.start_index[-1], max_index - visible_height + 1))

    # Clear old selection
    if menu_state.show_save_option and old_idx == max_index:
        menu_win.chgat(menu_win.getmaxyx()[0] - 2, (width - len(save_option)) // 2, len(save_option), get_color("settings_save"))
    else:
        menu_pad.chgat(old_idx, 0, menu_pad.getmaxyx()[1], get_color("settings_sensitive") if options[old_idx] in sensitive_settings else get_color("settings_default"))

    # Highlight new selection
    if menu_state.show_save_option and menu_state.selected_index == max_index:
        menu_win.chgat(menu_win.getmaxyx()[0] - 2, (width - len(save_option)) // 2, len(save_option), get_color("settings_save", reverse=True))
    else:
        menu_pad.chgat(menu_state.selected_index, 0, menu_pad.getmaxyx()[1], get_color("settings_sensitive", reverse=True) if options[menu_state.selected_index] in sensitive_settings else get_color("settings_default", reverse=True))

    menu_win.refresh()
    
    # Refresh pad only if scrolling is needed
    menu_pad.refresh(menu_state.start_index[-1], 0,
                     menu_win.getbegyx()[0] + 3, menu_win.getbegyx()[1] + 4,
                     menu_win.getbegyx()[0] + 3 + visible_height, 
                     menu_win.getbegyx()[1] + menu_win.getmaxyx()[1] - 4)

    # Update help window only if help_text is populated
    transformed_path = transform_menu_path(menu_state.menu_path)
    selected_option = options[menu_state.selected_index] if menu_state.selected_index < len(options) else None
    help_y = menu_win.getbegyx()[0] + menu_win.getmaxyx()[0]
    if help_text:
        help_win = update_help_window(help_win, help_text, transformed_path, selected_option, max_help_lines, width, help_y, menu_win.getbegyx()[1])

    draw_arrows(menu_win, visible_height, max_index, menu_state)





def draw_arrows(
    win: object,
    visible_height: int,
    max_index: int,
    menu_state: any
) -> None:

    # vh = visible_height + (1 if show_save_option else 0)
    mi = max_index - (2 if menu_state.show_save_option else 0) 

    if visible_height < mi:
        if menu_state.start_index[-1] > 0:
            win.addstr(3, 2, "▲", get_color("settings_default"))
        else:
            win.addstr(3, 2, " ", get_color("settings_default"))

        if mi - menu_state.start_index[-1] >= visible_height + (0 if menu_state.show_save_option else 1) :
            win.addstr(visible_height + 3, 2, "▼", get_color("settings_default"))
        else:
            win.addstr(visible_height + 3, 2, " ", get_color("settings_default"))


def update_help_window(
    help_win: object,  # curses window or None
    help_text: dict[str, str],
    transformed_path: list[str],
    selected_option: str | None,
    max_help_lines: int,
    width: int,
    help_y: int,
    help_x: int
) -> object:  # returns a curses window

    """Handles rendering the help window consistently."""
    wrapped_help = get_wrapped_help_text(help_text, transformed_path, selected_option, width, max_help_lines)

    help_height = min(len(wrapped_help) + 2, max_help_lines + 2)  # +2 for border
    help_height = max(help_height, 3)  # Ensure at least 3 rows (1 text + border)

    # Ensure help window does not exceed screen size
    if help_y + help_height > curses.LINES:
        help_y = curses.LINES - help_height

    # Create or update the help window
    if help_win is None:
        help_win = curses.newwin(help_height, width, help_y, help_x)
    else:
        help_win.erase()
        help_win.refresh()
        help_win.resize(help_height, width)
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
    help_text: dict[str, str],
    transformed_path: list[str],
    selected_option: str | None,
    width: int,
    max_lines: int
) -> list[WrappedLine]:
    """Fetches and formats help text for display, ensuring it fits within the allowed lines."""
    
    full_help_key = '.'.join(transformed_path + [selected_option]) if selected_option else None
    help_content = help_text.get(full_help_key, "No help available.")

    wrap_width = max(width - 6, 10)  # Ensure a valid wrapping width

    # Color replacements
    color_mappings = {
        r'\[warning\](.*?)\[/warning\]': ('settings_warning', True, False),  # Red for warnings
        r'\[note\](.*?)\[/note\]': ('settings_note', True, False),  # Green for notes
        r'\[underline\](.*?)\[/underline\]': ('settings_default', False, True),  # Underline

        r'\\033\[31m(.*?)\\033\[0m': ('settings_warning', True, False),  # Red text
        r'\\033\[32m(.*?)\\033\[0m': ('settings_note', True, False),  # Green text
        r'\\033\[4m(.*?)\\033\[0m': ('settings_default', False, True)  # Underline
    }

    def extract_ansi_segments(text: str) -> list[Segment]:
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

    def wrap_ansi_text(segments: list[Segment], wrap_width: int) -> list[WrappedLine]:
        """Wraps text while preserving ANSI formatting and spaces."""
        wrapped_lines = []
        line_buffer = []
        line_length = 0

        for text, color, bold, underline in segments:
            words = re.findall(r'\S+|\s+', text)  # Capture words and spaces separately

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