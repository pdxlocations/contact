import base64
import binascii
import curses
import ipaddress
from typing import Any, Optional, List

from contact.ui.colors import get_color
from contact.ui.nav_utils import move_highlight, draw_arrows, wrap_text
from contact.ui.dialog import dialog
from contact.utilities.i18n import t, t_text
from contact.utilities.validation_rules import get_validation_for
from contact.utilities.singleton import menu_state

# Dialogs should be at most 80 cols, but shrink on small terminals
MAX_DIALOG_WIDTH = 80
MIN_DIALOG_WIDTH = 20


def get_dialog_width() -> int:
    # Leave 2 columns for borders and clamp to a sane minimum
    try:
        return max(MIN_DIALOG_WIDTH, min(MAX_DIALOG_WIDTH, curses.COLS - 2))
    except Exception:
        # Fallback if curses not ready yet
        return MAX_DIALOG_WIDTH


def invalid_input(window: curses.window, message: str, redraw_func: Optional[callable] = None) -> None:
    """Displays an invalid input message in the given window and redraws if needed."""
    cursor_y, cursor_x = window.getyx()
    curses.curs_set(0)
    dialog(t("ui.dialog.invalid_input", default="Invalid Input"), t_text(message))
    if redraw_func:
        redraw_func()  # Redraw the original window content that got obscured
    else:
        window.refresh()
    window.move(cursor_y, cursor_x)
    curses.curs_set(1)


def get_text_input(prompt: str, selected_config: str, input_type: str) -> Optional[str]:
    """Handles user input with wrapped text for long prompts."""

    def redraw_input_win():
        """Redraw the input window with the current prompt and user input."""
        input_win.erase()
        input_win.border()
        row = 1
        for line in wrapped_prompt:
            input_win.addstr(row, margin, line[:input_width], get_color("settings_default", bold=True))
            row += 1
            if row >= height - 3:
                break
        input_win.addstr(row + 1, margin, prompt_text, get_color("settings_default"))
        input_win.addstr(row + 1, col_start, user_input[:first_line_width], get_color("settings_default"))
        for i, line in enumerate(wrap_text(user_input[first_line_width:], wrap_width=input_width)):
            if row + 2 + i < height - 1:
                input_win.addstr(row + 2 + i, margin, line[:input_width], get_color("settings_default"))
        input_win.refresh()

    height = 8
    width = get_dialog_width()
    margin = 2  # Left and right margin
    input_width = width - (2 * margin)  # Space available for text
    max_input_rows = height - 4  # Space for input

    start_y = max(0, (curses.LINES - height) // 2)
    start_x = max(0, (curses.COLS - width) // 2)

    input_win = curses.newwin(height, width, start_y, start_x)
    input_win.timeout(200)
    input_win.bkgd(get_color("background"))
    input_win.attrset(get_color("window_frame"))
    input_win.border()

    prompt = t_text(prompt)
    # Wrap the prompt text
    wrapped_prompt = wrap_text(prompt, wrap_width=input_width)
    row = 1

    for line in wrapped_prompt:
        input_win.addstr(row, margin, line[:input_width], get_color("settings_default", bold=True))
        row += 1
        if row >= height - 3:  # Prevent overflow
            break

    prompt_text = t("ui.prompt.enter_new_value", default="Enter new value: ")
    input_win.addstr(row + 1, margin, prompt_text, get_color("settings_default"))

    input_win.refresh()
    curses.curs_set(1)

    min_value = 0
    max_value = 4294967295
    min_length = 0
    max_length = None

    if selected_config is not None:
        validation = get_validation_for(selected_config) or {}
        min_value = validation.get("min_value", 0)
        max_value = validation.get("max_value", 4294967295)
        min_length = validation.get("min_length", 0)
        max_length = validation.get("max_length")

    user_input = ""
    col_start = margin + len(prompt_text)
    first_line_width = input_width - len(prompt_text)

    while True:
        if menu_state.need_redraw:
            menu_state.need_redraw = False
            redraw_input_win()

        try:
            key = input_win.get_wch()
        except curses.error:
            continue

        if key == chr(27) or key == curses.KEY_LEFT:
            input_win.erase()
            input_win.refresh()
            curses.curs_set(0)
            menu_state.need_redraw = True
            return None

        elif key in (chr(curses.KEY_ENTER), chr(10), chr(13)):
            menu_state.need_redraw = True

            if not user_input.strip():
                invalid_input(
                    input_win,
                    t("ui.error.value_empty", default="Value cannot be empty."),
                    redraw_func=redraw_input_win,
                )
                continue

            length = len(user_input)
            if min_length == max_length and max_length is not None:
                if length != min_length:
                    invalid_input(
                        input_win,
                        t("ui.error.value_exact_length", default="Value must be exactly {length} characters long.", length=min_length),
                        redraw_func=redraw_input_win,
                    )
                    continue
            else:
                if length < min_length:
                    invalid_input(
                        input_win,
                        t("ui.error.value_min_length", default="Value must be at least {length} characters long.", length=min_length),
                        redraw_func=redraw_input_win,
                    )
                    continue
                if max_length is not None and length > max_length:
                    invalid_input(
                        input_win,
                        t("ui.error.value_max_length", default="Value must be no more than {length} characters long.", length=max_length),
                        redraw_func=redraw_input_win,
                    )
                    continue

            if input_type is int:
                if not user_input.isdigit():
                    invalid_input(
                        input_win,
                        t("ui.error.digits_only", default="Only numeric digits (0-9) allowed."),
                        redraw_func=redraw_input_win,
                    )
                    continue

                int_val = int(user_input)
                if not (min_value <= int_val <= max_value):
                    invalid_input(
                        input_win,
                        t(
                            "ui.error.number_range",
                            default="Enter a number between {min_value} and {max_value}.",
                            min_value=min_value,
                            max_value=max_value,
                        ),
                        redraw_func=redraw_input_win,
                    )
                    continue

                curses.curs_set(0)
                return int_val

            elif input_type is float:
                try:
                    float_val = float(user_input)
                    if not (min_value <= float_val <= max_value):
                        invalid_input(
                            input_win,
                            t(
                                "ui.error.number_range",
                                default="Enter a number between {min_value} and {max_value}.",
                                min_value=min_value,
                                max_value=max_value,
                            ),
                            redraw_func=redraw_input_win,
                        )
                        continue
                except ValueError:
                    invalid_input(
                        input_win,
                        t("ui.error.float_invalid", default="Must be a valid floating point number."),
                        redraw_func=redraw_input_win,
                    )
                    continue
                else:
                    curses.curs_set(0)
                    return float_val

            else:
                break

        elif key in (curses.KEY_BACKSPACE, chr(127)):  # Handle Backspace
            if user_input:
                user_input = user_input[:-1]  # Remove last character

        elif max_length is None or len(user_input) < max_length:
            try:
                char = chr(key) if not isinstance(key, str) else key
                if input_type is int:
                    if char.isdigit() or (char == "-" and len(user_input) == 0):
                        user_input += char
                elif input_type is float:
                    if (
                        char.isdigit()
                        or (char == "." and "." not in user_input)
                        or (char == "-" and len(user_input) == 0)
                    ):
                        user_input += char
                else:
                    user_input += char
            except ValueError:
                pass  # Ignore invalid input

        # First line must be manually handled before using wrap_text()
        first_line = user_input[:first_line_width]  # Cut to max first line width
        remaining_text = user_input[first_line_width:]  # Remaining text for wrapping

        wrapped_lines = wrap_text(remaining_text, wrap_width=input_width) if remaining_text else []

        # Clear only the input area (without touching prompt text)
        for i in range(max_input_rows):
            if row + 1 + i < height - 1:
                input_win.addstr(row + 1 + i, margin, " " * input_width, get_color("settings_default"))

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
    return user_input.strip()


def get_admin_key_input(current_value: List[bytes]) -> Optional[List[str]]:
    """Handles user input for editing up to 3 Admin Keys in Base64 format."""

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
    width = get_dialog_width()
    start_y = max(0, (curses.LINES - height) // 2)
    start_x = max(0, (curses.COLS - width) // 2)

    admin_key_win = curses.newwin(height, width, start_y, start_x)
    admin_key_win.timeout(200)
    admin_key_win.bkgd(get_color("background"))
    admin_key_win.attrset(get_color("window_frame"))
    admin_key_win.keypad(True)  # Enable keypad for special keys

    curses.echo()
    curses.curs_set(1)

    # Editable list of values (max 3 values)
    user_values = cvalue[:3] + [""] * (3 - len(cvalue))  # Ensure always 3 fields
    cursor_pos = 0  # Track which value is being edited
    invalid_input = ""

    while True:
        admin_key_win.erase()
        admin_key_win.border()
        admin_key_win.addstr(
            1,
            2,
            t("ui.prompt.edit_admin_keys", default="Edit up to 3 Admin Keys:"),
            get_color("settings_default", bold=True),
        )

        # Display current values, allowing editing
        for i, line in enumerate(user_values):
            prefix = "→ " if i == cursor_pos else "  "  # Highlight the current line
            admin_key_win.addstr(
                3 + i,
                2,
                f"{prefix}{t('ui.label.admin_key', default='Admin Key')} {i + 1}: ",
                get_color("settings_default", bold=(i == cursor_pos)),
            )
            admin_key_win.addstr(3 + i, 18, line)  # Align text for easier editing

        # Move cursor to the correct position inside the field
        curses.curs_set(1)
        admin_key_win.move(3 + cursor_pos, 18 + len(user_values[cursor_pos]))  # Position cursor at end of text

        # Show error message if needed
        if invalid_input:
            admin_key_win.addstr(7, 2, t_text(invalid_input), get_color("settings_default", bold=True))

        admin_key_win.refresh()
        key = admin_key_win.getch()

        if key == 27 or key == curses.KEY_LEFT:  # Escape or Left Arrow -> Cancel and return original
            admin_key_win.erase()
            admin_key_win.refresh()
            curses.noecho()
            curses.curs_set(0)
            menu_state.need_redraw = True
            return None

        elif key == ord("\n"):  # Enter key to save and return
            menu_state.need_redraw = True
            if all(is_valid_base64(val) for val in user_values):  # Ensure all values are valid Base64 and 32 bytes
                curses.noecho()
                curses.curs_set(0)
                return user_values  # Return the edited Base64 values
            else:
                invalid_input = t(
                    "ui.error.admin_key_invalid",
                    default="Error: Each key must be valid Base64 and 32 bytes long!",
                )
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
                invalid_input = ""  # Clear error if user starts fixing input
            except ValueError:
                pass  # Ignore invalid character inputs


from contact.utilities.singleton import menu_state  # Required if not already imported


def get_repeated_input(current_value: List[str]) -> Optional[str]:
    height = 9
    width = get_dialog_width()
    start_y = max(0, (curses.LINES - height) // 2)
    start_x = max(0, (curses.COLS - width) // 2)

    repeated_win = curses.newwin(height, width, start_y, start_x)
    repeated_win.timeout(200)
    repeated_win.bkgd(get_color("background"))
    repeated_win.attrset(get_color("window_frame"))
    repeated_win.keypad(True)

    curses.echo()
    curses.curs_set(1)

    user_values = current_value[:3] + [""] * (3 - len(current_value))  # Always 3 fields
    cursor_pos = 0
    invalid_input = ""

    def redraw():
        repeated_win.erase()
        repeated_win.border()
        repeated_win.addstr(
            1,
            2,
            t("ui.prompt.edit_values", default="Edit up to 3 Values:"),
            get_color("settings_default", bold=True),
        )

        win_h, win_w = repeated_win.getmaxyx()
        for i, line in enumerate(user_values):
            prefix = "→ " if i == cursor_pos else "  "
            repeated_win.addstr(
                3 + i,
                2,
                f"{prefix}{t('ui.label.value', default='Value')}{i + 1}: ",
                get_color("settings_default", bold=(i == cursor_pos)),
            )
            repeated_win.addstr(3 + i, 18, line[: max(0, win_w - 20)])  # Prevent overflow

        if invalid_input:
            win_h, win_w = repeated_win.getmaxyx()
            repeated_win.addstr(7, 2, invalid_input[: max(0, win_w - 4)], get_color("settings_default", bold=True))

        repeated_win.move(3 + cursor_pos, 18 + len(user_values[cursor_pos]))
        repeated_win.refresh()

    while True:
        if menu_state.need_redraw:
            menu_state.need_redraw = False
            redraw()

        redraw()

        try:
            key = repeated_win.get_wch()
        except curses.error:
            continue  # ignore timeout or input issues

        if key in (27, curses.KEY_LEFT):  # ESC or Left Arrow
            repeated_win.erase()
            repeated_win.refresh()
            curses.noecho()
            curses.curs_set(0)
            menu_state.need_redraw = True
            return None
        elif key in ("\n", curses.KEY_ENTER):
            curses.noecho()
            curses.curs_set(0)
            menu_state.need_redraw = True
            return ", ".join(user_values).strip()
        elif key == curses.KEY_UP:
            cursor_pos = (cursor_pos - 1) % 3
        elif key == curses.KEY_DOWN:
            cursor_pos = (cursor_pos + 1) % 3
        elif key in (curses.KEY_BACKSPACE, 127):
            user_values[cursor_pos] = user_values[cursor_pos][:-1]
        else:
            try:
                ch = chr(key) if isinstance(key, int) else key
                if ch.isprintable():
                    user_values[cursor_pos] += ch
                    invalid_input = ""
            except Exception:
                pass


from contact.utilities.singleton import menu_state  # Ensure this is imported


def get_fixed32_input(current_value: int) -> int:
    original_value = current_value
    ip_string = str(ipaddress.IPv4Address(current_value))
    height = 10
    width = get_dialog_width()
    start_y = max(0, (curses.LINES - height) // 2)
    start_x = max(0, (curses.COLS - width) // 2)

    fixed32_win = curses.newwin(height, width, start_y, start_x)
    fixed32_win.bkgd(get_color("background"))
    fixed32_win.attrset(get_color("window_frame"))
    fixed32_win.keypad(True)
    fixed32_win.timeout(200)

    curses.echo()
    curses.curs_set(1)
    user_input = ""

    def redraw():
        fixed32_win.erase()
        fixed32_win.border()
        fixed32_win.addstr(
            1,
            2,
            t("ui.prompt.enter_ip", default="Enter an IP address (xxx.xxx.xxx.xxx):"),
            get_color("settings_default", bold=True),
        )
        fixed32_win.addstr(
            3, 2, f"{t('ui.label.current', default='Current')}: {ip_string}", get_color("settings_default")
        )
        fixed32_win.addstr(
            5,
            2,
            f"{t('ui.label.new_value', default='New value')}: {user_input}",
            get_color("settings_default"),
        )
        fixed32_win.refresh()

    while True:
        if menu_state.need_redraw:
            menu_state.need_redraw = False
            redraw()

        redraw()

        try:
            key = fixed32_win.get_wch()
        except curses.error:
            continue  # ignore timeout

        if key in (27, curses.KEY_LEFT):  # ESC or Left Arrow to cancel
            fixed32_win.erase()
            fixed32_win.refresh()
            curses.noecho()
            curses.curs_set(0)
            menu_state.need_redraw = True
            return original_value

        elif key in ("\n", curses.KEY_ENTER):
            octets = user_input.split(".")
            menu_state.need_redraw = True
            if len(octets) == 4 and all(octet.isdigit() and 0 <= int(octet) <= 255 for octet in octets):
                curses.noecho()
                curses.curs_set(0)
                return int(ipaddress.ip_address(user_input))
            else:
                fixed32_win.addstr(
                    7,
                    2,
                    t("ui.error.ip_invalid", default="Invalid IP address. Try again."),
                    get_color("settings_default", bold=True),
                )
                fixed32_win.refresh()
                curses.napms(1500)
                user_input = ""

        elif key in (curses.KEY_BACKSPACE, 127):
            user_input = user_input[:-1]

        else:
            try:
                ch = chr(key) if isinstance(key, int) else key
                if ch.isdigit() or ch == ".":
                    user_input += ch
            except Exception:
                pass  # Ignore unprintable inputs


from typing import List, Optional  # ensure Optional is imported


def get_list_input(
    prompt: str, current_option: Optional[str], list_options: List[str], mandatory: bool = False
) -> Optional[str]:
    """
    List selector.
    """
    selected_index = list_options.index(current_option) if current_option in list_options else 0

    height = min(len(list_options) + 5, curses.LINES)
    width = get_dialog_width()
    start_y = max(0, (curses.LINES - height) // 2)
    start_x = max(0, (curses.COLS - width) // 2)

    list_win = curses.newwin(height, width, start_y, start_x)
    list_win.timeout(200)
    list_win.bkgd(get_color("background"))
    list_win.attrset(get_color("window_frame"))
    list_win.keypad(True)

    list_pad = curses.newpad(len(list_options) + 1, max(1, width - 8))
    list_pad.bkgd(get_color("background"))

    max_index = len(list_options) - 1
    visible_height = list_win.getmaxyx()[0] - 5

    def redraw_list_ui():
        translated_prompt = t_text(prompt)
        list_win.erase()
        list_win.border()
        list_win.addstr(1, 2, translated_prompt, get_color("settings_default", bold=True))

        win_h, win_w = list_win.getmaxyx()
        pad_w = max(1, win_w - 8)
        for idx, item in enumerate(list_options):
            color = get_color("settings_default", reverse=(idx == selected_index))
            display_item = t_text(item)
            list_pad.addstr(idx, 0, display_item[:pad_w].ljust(pad_w), color)

        list_win.refresh()
        list_pad.refresh(
            0,
            0,
            list_win.getbegyx()[0] + 3,
            list_win.getbegyx()[1] + 4,
            list_win.getbegyx()[0] + list_win.getmaxyx()[0] - 2,
            list_win.getbegyx()[1] + list_win.getmaxyx()[1] - 4,
        )
        # Recompute visible height each draw in case of resize
        vis_h = list_win.getmaxyx()[0] - 5
        draw_arrows(list_win, vis_h, max_index, [0], show_save_option=False)

    # Initial draw
    redraw_list_ui()

    while True:
        if menu_state.need_redraw:
            menu_state.need_redraw = False
            redraw_list_ui()

        try:
            key = list_win.getch()
        except curses.error:
            continue

        if key == curses.KEY_UP:
            old_selected_index = selected_index
            selected_index = max(0, selected_index - 1)
            move_highlight(old_selected_index, list_options, list_win, list_pad, selected_index=selected_index)

        elif key == curses.KEY_DOWN:
            old_selected_index = selected_index
            selected_index = min(len(list_options) - 1, selected_index + 1)
            move_highlight(old_selected_index, list_options, list_win, list_pad, selected_index=selected_index)

        elif key == ord("\n"):  # Enter
            list_win.clear()
            list_win.refresh()
            menu_state.need_redraw = True
            return list_options[selected_index]

        elif key == 27 or key == curses.KEY_LEFT:  # ESC or Left
            if mandatory:
                continue
            list_win.clear()
            list_win.refresh()
            menu_state.need_redraw = True
            return current_option
