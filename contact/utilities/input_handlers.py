import base64
import binascii
import curses
import ipaddress
from typing import Any, Optional, List

from contact.ui.colors import get_color
from contact.ui.nav_utils import move_highlight, draw_arrows, wrap_text


def get_text_input(prompt: str) -> Optional[str]:
    """Handles user input with wrapped text for long prompts."""
    height = 8
    width = 80
    margin = 2  # Left and right margin
    input_width = width - (2 * margin)  # Space available for text
    max_input_rows = height - 4  # Space for input

    start_y = (curses.LINES - height) // 2
    start_x = (curses.COLS - width) // 2

    input_win = curses.newwin(height, width, start_y, start_x)
    input_win.bkgd(get_color("background"))
    input_win.attrset(get_color("window_frame"))
    input_win.border()

    # Wrap the prompt text
    wrapped_prompt = wrap_text(prompt, wrap_width=input_width)
    row = 1
    for line in wrapped_prompt:
        input_win.addstr(row, margin, line[:input_width], get_color("settings_default", bold=True))
        row += 1
        if row >= height - 3:  # Prevent overflow
            break

    prompt_text = "Enter new value: "
    input_win.addstr(row + 1, margin, prompt_text, get_color("settings_default"))

    input_win.refresh()
    curses.curs_set(1)

    max_length = 4 if "shortName" in prompt else None
    user_input = ""

    # Start user input after the prompt text
    col_start = margin + len(prompt_text)
    first_line_width = input_width - len(prompt_text)  # Available space for first line

    while True:
        key = input_win.get_wch()  # Waits for user input

        if key == chr(27) or key == curses.KEY_LEFT:  # ESC or Left Arrow
            input_win.erase()
            input_win.refresh()
            curses.curs_set(0)
            return None  # Exit without saving

        elif key in (chr(curses.KEY_ENTER), chr(10), chr(13)):  # Enter key
            break

        elif key in (curses.KEY_BACKSPACE, chr(127)):  # Handle Backspace
            if user_input:
                user_input = user_input[:-1]  # Remove last character

        elif max_length is None or len(user_input) < max_length:  # Enforce max length
            if isinstance(key, str):
                user_input += key
            else:
                user_input += chr(key)

        # First line must be manually handled before using wrap_text()
        first_line = user_input[:first_line_width]  # Cut to max first line width
        remaining_text = user_input[first_line_width:]  # Remaining text for wrapping

        wrapped_lines = wrap_text(remaining_text, wrap_width=input_width) if remaining_text else []

        # Clear only the input area (without touching prompt text)
        for i in range(max_input_rows):
            if row + 1 + i < height - 1:
                input_win.addstr(
                    row + 1 + i, margin, " " * min(input_width, width - margin - 1), get_color("settings_default")
                )

        # Redraw the prompt text so it never disappears
        input_win.addstr(row + 1, margin, prompt_text, get_color("settings_default"))

        # Redraw wrapped input
        input_win.addstr(row + 1, col_start, first_line, get_color("settings_default"))  # First line next to prompt
        for i, line in enumerate(wrapped_lines):
            if row + 2 + i < height - 1:
                input_win.addstr(row + 2 + i, margin, line[:input_width], get_color("settings_default"))

        input_win.refresh()

    curses.curs_set(0)
    input_win.erase()
    input_win.refresh()
    return user_input


def get_admin_key_input(current_value: List[bytes]) -> Optional[List[str]]:
    def to_base64(byte_strings):
        """Convert byte values to Base64-encoded strings."""
        return [base64.b64encode(b).decode() for b in byte_strings]

    def is_valid_base64(s):
        """Check if a string is valid Base64 or blank."""
        if s == "":
            return True
        try:
            decoded = base64.b64decode(s, validate=True)
            return len(decoded) == 32  # Ensure it's exactly 32 bytes
        except (binascii.Error, ValueError):
            return False

    cvalue = to_base64(current_value)  # Convert current values to Base64
    height = 9
    width = 80
    start_y = (curses.LINES - height) // 2
    start_x = (curses.COLS - width) // 2

    repeated_win = curses.newwin(height, width, start_y, start_x)
    repeated_win.bkgd(get_color("background"))
    repeated_win.attrset(get_color("window_frame"))
    repeated_win.keypad(True)  # Enable keypad for special keys

    curses.echo()
    curses.curs_set(1)

    # Editable list of values (max 3 values)
    user_values = cvalue[:3] + [""] * (3 - len(cvalue))  # Ensure always 3 fields
    cursor_pos = 0  # Track which value is being edited
    error_message = ""

    while True:
        repeated_win.erase()
        repeated_win.border()
        repeated_win.addstr(1, 2, "Edit up to 3 Admin Keys:", get_color("settings_default", bold=True))

        # Display current values, allowing editing
        for i, line in enumerate(user_values):
            prefix = "→ " if i == cursor_pos else "  "  # Highlight the current line
            repeated_win.addstr(
                3 + i, 2, f"{prefix}Admin Key {i + 1}: ", get_color("settings_default", bold=(i == cursor_pos))
            )
            repeated_win.addstr(3 + i, 18, line)  # Align text for easier editing

        # Move cursor to the correct position inside the field
        curses.curs_set(1)
        repeated_win.move(3 + cursor_pos, 18 + len(user_values[cursor_pos]))  # Position cursor at end of text

        # Show error message if needed
        if error_message:
            repeated_win.addstr(7, 2, error_message, get_color("settings_default", bold=True))

        repeated_win.refresh()
        key = repeated_win.getch()

        if key == 27 or key == curses.KEY_LEFT:  # Escape or Left Arrow -> Cancel and return original
            repeated_win.erase()
            repeated_win.refresh()
            curses.noecho()
            curses.curs_set(0)
            return None

        elif key == ord("\n"):  # Enter key to save and return
            if all(is_valid_base64(val) for val in user_values):  # Ensure all values are valid Base64 and 32 bytes
                curses.noecho()
                curses.curs_set(0)
                return user_values  # Return the edited Base64 values
            else:
                error_message = "Error: Each key must be valid Base64 and 32 bytes long!"
        elif key == curses.KEY_UP:  # Move cursor up
            cursor_pos = (cursor_pos - 1) % len(user_values)
        elif key == curses.KEY_DOWN:  # Move cursor down
            cursor_pos = (cursor_pos + 1) % len(user_values)
        elif key == curses.KEY_BACKSPACE or key == 127:  # Backspace key
            if len(user_values[cursor_pos]) > 0:
                user_values[cursor_pos] = user_values[cursor_pos][:-1]  # Remove last character
        else:
            try:
                user_values[cursor_pos] += chr(key)  # Append valid character input to the selected field
                error_message = ""  # Clear error if user starts fixing input
            except ValueError:
                pass  # Ignore invalid character inputs


def get_repeated_input(current_value: List[str]) -> Optional[str]:
    height = 9
    width = 80
    start_y = (curses.LINES - height) // 2
    start_x = (curses.COLS - width) // 2

    repeated_win = curses.newwin(height, width, start_y, start_x)
    repeated_win.bkgd(get_color("background"))
    repeated_win.attrset(get_color("window_frame"))
    repeated_win.keypad(True)  # Enable keypad for special keys

    curses.echo()
    curses.curs_set(1)  #  Show the cursor

    # Editable list of values (max 3 values)
    user_values = current_value[:3]
    cursor_pos = 0  # Track which value is being edited
    error_message = ""

    while True:
        repeated_win.erase()
        repeated_win.border()
        repeated_win.addstr(1, 2, "Edit up to 3 Values:", get_color("settings_default", bold=True))

        # Display current values, allowing editing
        for i, line in enumerate(user_values):
            prefix = "→ " if i == cursor_pos else "  "  # Highlight the current line
            repeated_win.addstr(
                3 + i, 2, f"{prefix}Value{i + 1}: ", get_color("settings_default", bold=(i == cursor_pos))
            )
            repeated_win.addstr(3 + i, 18, line)

        # Move cursor to the correct position inside the field
        curses.curs_set(1)
        repeated_win.move(3 + cursor_pos, 18 + len(user_values[cursor_pos]))  #  Position cursor at end of text

        # Show error message if needed
        if error_message:
            repeated_win.addstr(7, 2, error_message, get_color("settings_default", bold=True))

        repeated_win.refresh()
        key = repeated_win.getch()

        if key == 27 or key == curses.KEY_LEFT:  # Escape or Left Arrow -> Cancel and return original
            repeated_win.erase()
            repeated_win.refresh()
            curses.noecho()
            curses.curs_set(0)
            return None

        elif key == ord("\n"):  # Enter key to save and return
            curses.noecho()
            curses.curs_set(0)
            return ", ".join(user_values)
        elif key == curses.KEY_UP:  # Move cursor up
            cursor_pos = (cursor_pos - 1) % len(user_values)
        elif key == curses.KEY_DOWN:  # Move cursor down
            cursor_pos = (cursor_pos + 1) % len(user_values)
        elif key == curses.KEY_BACKSPACE or key == 127:  # Backspace key
            if len(user_values[cursor_pos]) > 0:
                user_values[cursor_pos] = user_values[cursor_pos][:-1]  # Remove last character
        else:
            try:
                user_values[cursor_pos] += chr(key)  # Append valid character input to the selected field
                error_message = ""  # Clear error if user starts fixing input
            except ValueError:
                pass  # Ignore invalid character inputs


def get_fixed32_input(current_value: int) -> int:
    cvalue = current_value
    current_value = str(ipaddress.IPv4Address(current_value))
    height = 10
    width = 80
    start_y = (curses.LINES - height) // 2
    start_x = (curses.COLS - width) // 2

    fixed32_win = curses.newwin(height, width, start_y, start_x)
    fixed32_win.bkgd(get_color("background"))
    fixed32_win.attrset(get_color("window_frame"))
    fixed32_win.keypad(True)

    curses.echo()
    curses.curs_set(1)
    user_input = ""

    while True:
        fixed32_win.erase()
        fixed32_win.border()
        fixed32_win.addstr(1, 2, "Enter an IP address (xxx.xxx.xxx.xxx):", curses.A_BOLD)
        fixed32_win.addstr(3, 2, f"Current: {current_value}")
        fixed32_win.addstr(5, 2, f"New value: {user_input}")
        fixed32_win.refresh()

        key = fixed32_win.getch()

        if key == 27 or key == curses.KEY_LEFT:  # Escape or Left Arrow to cancel
            fixed32_win.erase()
            fixed32_win.refresh()
            curses.noecho()
            curses.curs_set(0)
            return cvalue  # Return the current value unchanged
        elif key == ord("\n"):  # Enter key to validate and save
            # Validate IP address
            octets = user_input.split(".")
            if len(octets) == 4 and all(octet.isdigit() and 0 <= int(octet) <= 255 for octet in octets):
                curses.noecho()
                curses.curs_set(0)
                fixed32_address = ipaddress.ip_address(user_input)
                return int(fixed32_address)  # Return the valid IP address
            else:
                fixed32_win.addstr(7, 2, "Invalid IP address. Try again.", curses.A_BOLD | curses.color_pair(5))
                fixed32_win.refresh()
                curses.napms(1500)  # Wait for 1.5 seconds before refreshing
                user_input = ""  # Clear invalid input
        elif key == curses.KEY_BACKSPACE or key == 127:  # Backspace key
            user_input = user_input[:-1]
        else:
            try:
                char = chr(key)
                if char.isdigit() or char == ".":
                    user_input += char  # Append only valid characters (digits or dots)
            except ValueError:
                pass  # Ignore invalid inputs


def get_list_input(prompt: str, current_option: Optional[str], list_options: List[str]) -> Optional[str]:
    """
    Displays a scrollable list of list_options for the user to choose from.
    """
    selected_index = list_options.index(current_option) if current_option in list_options else 0

    height = min(len(list_options) + 5, curses.LINES)
    width = 80
    start_y = (curses.LINES - height) // 2
    start_x = (curses.COLS - width) // 2

    list_win = curses.newwin(height, width, start_y, start_x)
    list_win.bkgd(get_color("background"))
    list_win.attrset(get_color("window_frame"))
    list_win.keypad(True)

    list_pad = curses.newpad(len(list_options) + 1, width - 8)
    list_pad.bkgd(get_color("background"))

    # Render header
    list_win.erase()
    list_win.border()
    list_win.addstr(1, 2, prompt, get_color("settings_default", bold=True))

    # Render options on the pad
    for idx, color in enumerate(list_options):
        if idx == selected_index:
            list_pad.addstr(idx, 0, color.ljust(width - 8), get_color("settings_default", reverse=True))
        else:
            list_pad.addstr(idx, 0, color.ljust(width - 8), get_color("settings_default"))

    # Initial refresh
    list_win.refresh()
    list_pad.refresh(
        0,
        0,
        list_win.getbegyx()[0] + 3,
        list_win.getbegyx()[1] + 4,
        list_win.getbegyx()[0] + list_win.getmaxyx()[0] - 2,
        list_win.getbegyx()[1] + list_win.getmaxyx()[1] - 4,
    )

    max_index = len(list_options) - 1
    visible_height = list_win.getmaxyx()[0] - 5

    draw_arrows(list_win, visible_height, max_index, [0], show_save_option=False)  # Initial call to draw arrows

    while True:
        key = list_win.getch()

        if key == curses.KEY_UP:
            old_selected_index = selected_index
            selected_index = max(0, selected_index - 1)
            move_highlight(old_selected_index, list_options, list_win, list_pad, selected_index=selected_index)
        elif key == curses.KEY_DOWN:
            old_selected_index = selected_index
            selected_index = min(len(list_options) - 1, selected_index + 1)
            move_highlight(old_selected_index, list_options, list_win, list_pad, selected_index=selected_index)
        elif key == ord("\n"):  # Enter key
            list_win.clear()
            list_win.refresh()
            return list_options[selected_index]
        elif key == 27 or key == curses.KEY_LEFT:  # ESC or Left Arrow
            list_win.clear()
            list_win.refresh()
            return current_option
