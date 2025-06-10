import os
import json
import curses
from typing import Any, List, Dict

from contact.ui.colors import get_color, setup_colors, COLOR_MAP
from contact.ui.default_config import format_json_single_line_arrays, loaded_config
from contact.ui.nav_utils import move_highlight, draw_arrows
from contact.utilities.input_handlers import get_list_input


width = 80
max_help_lines = 6
save_option = "Save Changes"


def edit_color_pair(key: str, current_value: List[str]) -> List[str]:
    """
    Allows the user to select a foreground and background color for a key.
    """
    color_list = [" "] + list(COLOR_MAP.keys())
    fg_color = get_list_input(f"Select Foreground Color for {key}", current_value[0], color_list)
    bg_color = get_list_input(f"Select Background Color for {key}", current_value[1], color_list)

    return [fg_color, bg_color]


def edit_value(key: str, current_value: str) -> str:

    height = 10
    input_width = width - 16  # Allow space for "New Value: "
    start_y = (curses.LINES - height) // 2
    start_x = (curses.COLS - width) // 2

    # Create a centered window
    edit_win = curses.newwin(height, width, start_y, start_x)
    edit_win.bkgd(get_color("background"))
    edit_win.attrset(get_color("window_frame"))
    edit_win.border()

    # Display instructions
    edit_win.addstr(1, 2, f"Editing {key}", get_color("settings_default", bold=True))
    edit_win.addstr(3, 2, "Current Value:", get_color("settings_default"))

    wrap_width = width - 4  # Account for border and padding
    wrapped_lines = [current_value[i : i + wrap_width] for i in range(0, len(current_value), wrap_width)]

    for i, line in enumerate(wrapped_lines[:4]):  # Limit display to fit the window height
        edit_win.addstr(4 + i, 2, line, get_color("settings_default"))

    edit_win.refresh()

    # Handle theme selection dynamically
    if key == "theme":
        # Load theme names dynamically from the JSON
        theme_options = [k.split("_", 2)[2].lower() for k in loaded_config.keys() if k.startswith("COLOR_CONFIG")]
        return get_list_input("Select Theme", current_value, theme_options)

    elif key == "node_sort":
        sort_options = ["lastHeard", "name", "hops"]
        return get_list_input("Sort By", current_value, sort_options)

    elif key == "notification_sound":
        sound_options = ["True", "False"]
        return get_list_input("Notification Sound", current_value, sound_options)

    # Standard Input Mode (Scrollable)
    edit_win.addstr(7, 2, "New Value: ", get_color("settings_default"))
    curses.curs_set(1)

    scroll_offset = 0  # Determines which part of the text is visible
    user_input = ""
    input_position = (7, 13)  # Tuple for row and column
    row, col = input_position  # Unpack tuple
    while True:
        visible_text = user_input[scroll_offset : scroll_offset + input_width]  # Only show what fits
        edit_win.addstr(row, col, " " * input_width, get_color("settings_default"))  # Clear previous text
        edit_win.addstr(row, col, visible_text, get_color("settings_default"))  # Display text
        edit_win.refresh()

        edit_win.move(row, col + min(len(user_input) - scroll_offset, input_width))  # Adjust cursor position
        key = edit_win.get_wch()

        if key in (chr(27), curses.KEY_LEFT):  # ESC or Left Arrow
            curses.curs_set(0)
            return current_value  # Exit without returning a value

        elif key in (chr(curses.KEY_ENTER), chr(10), chr(13)):
            break

        elif key in (curses.KEY_BACKSPACE, chr(127)):  # Backspace
            if user_input:  # Only process if there's something to delete
                user_input = user_input[:-1]
                if scroll_offset > 0 and len(user_input) < scroll_offset + input_width:
                    scroll_offset -= 1  # Move back if text is shorter than scrolled area
        else:
            if isinstance(key, str):
                user_input += key
            else:
                user_input += chr(key)

            if len(user_input) > input_width:  # Scroll if input exceeds visible area
                scroll_offset += 1

    curses.curs_set(0)
    return user_input if user_input else current_value


def display_menu(menu_state: Any) -> tuple[Any, Any, List[str]]:
    """
    Render the configuration menu with a Save button directly added to the window.
    """
    num_items = len(menu_state.current_menu) + (1 if menu_state.show_save_option else 0)

    # Determine menu items based on the type of current_menu
    if isinstance(menu_state.current_menu, dict):
        options = list(menu_state.current_menu.keys())
    elif isinstance(menu_state.current_menu, list):
        options = [f"[{i}]" for i in range(len(menu_state.current_menu))]
    else:
        options = []  # Fallback in case of unexpected data types

    # Calculate dynamic dimensions for the menu
    max_menu_height = curses.LINES
    menu_height = min(max_menu_height, num_items + 5)
    num_items = len(options)
    start_y = (curses.LINES - menu_height) // 2
    start_x = (curses.COLS - width) // 2

    # Create the window
    menu_win = curses.newwin(menu_height, width, start_y, start_x)
    menu_win.erase()
    menu_win.bkgd(get_color("background"))
    menu_win.attrset(get_color("window_frame"))
    menu_win.border()
    menu_win.keypad(True)

    # Create the pad for scrolling
    menu_pad = curses.newpad(num_items + 1, width - 8)
    menu_pad.bkgd(get_color("background"))

    # Display the menu path
    header = " > ".join(menu_state.menu_path)
    if len(header) > width - 4:
        header = header[: width - 7] + "..."
    menu_win.addstr(1, 2, header, get_color("settings_breadcrumbs", bold=True))

    # Populate the pad with menu options
    for idx, key in enumerate(options):
        value = (
            menu_state.current_menu[key]
            if isinstance(menu_state.current_menu, dict)
            else menu_state.current_menu[int(key.strip("[]"))]
        )
        display_key = f"{key}"[: width // 2 - 2]
        display_value = f"{value}"[: width // 2 - 8]

        color = get_color("settings_default", reverse=(idx == menu_state.selected_index))
        menu_pad.addstr(idx, 0, f"{display_key:<{width // 2 - 2}} {display_value}".ljust(width - 8), color)

    # Add Save button to the main window
    if menu_state.show_save_option:
        save_position = menu_height - 2
        menu_win.addstr(
            save_position,
            (width - len(save_option)) // 2,
            save_option,
            get_color("settings_save", reverse=(menu_state.selected_index == len(menu_state.current_menu))),
        )

    menu_win.refresh()
    menu_pad.refresh(
        menu_state.start_index[-1],
        0,
        menu_win.getbegyx()[0] + 3,
        menu_win.getbegyx()[1] + 4,
        menu_win.getbegyx()[0] + 3 + menu_win.getmaxyx()[0] - 5 - (2 if menu_state.show_save_option else 0),
        menu_win.getbegyx()[1] + menu_win.getmaxyx()[1] - 4,
    )

    max_index = num_items + (1 if menu_state.show_save_option else 0) - 1
    visible_height = menu_win.getmaxyx()[0] - 5 - (2 if menu_state.show_save_option else 0)

    draw_arrows(menu_win, visible_height, max_index, menu_state.start_index, menu_state.show_save_option)

    return menu_win, menu_pad, options


def json_editor(stdscr: curses.window, menu_state: Any) -> None:

    menu_state.selected_index = 0  # Track the selected option

    script_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.abspath(os.path.join(script_dir, os.pardir))
    file_path = os.path.join(parent_dir, "config.json")

    menu_state.show_save_option = True  # Always show the Save button
    menu_state.help_win = None
    menu_state.help_text = {}

    # Ensure the file exists
    if not os.path.exists(file_path):
        with open(file_path, "w") as f:
            json.dump({}, f)

    # Load JSON data
    with open(file_path, "r", encoding="utf-8") as f:
        original_data = json.load(f)

    data = original_data  # Reference to the original data
    menu_state.current_menu = data  # Track the current level of the menu

    # Render the menu
    menu_win, menu_pad, options = display_menu(menu_state)
    need_redraw = True

    while True:
        if need_redraw:
            menu_win, menu_pad, options = display_menu(menu_state)
            menu_win.refresh()
            need_redraw = False

        max_index = len(options) + (1 if menu_state.show_save_option else 0) - 1
        key = menu_win.getch()

        if key == curses.KEY_UP:

            old_selected_index = menu_state.selected_index
            menu_state.selected_index = max_index if menu_state.selected_index == 0 else menu_state.selected_index - 1
            menu_state.help_win = move_highlight(
                old_selected_index, options, menu_win, menu_pad, menu_state=menu_state, max_help_lines=max_help_lines
            )

        elif key == curses.KEY_DOWN:

            old_selected_index = menu_state.selected_index
            menu_state.selected_index = 0 if menu_state.selected_index == max_index else menu_state.selected_index + 1
            menu_state.help_win = move_highlight(
                old_selected_index, options, menu_win, menu_pad, menu_state=menu_state, max_help_lines=max_help_lines
            )

        elif key == ord("\t") and menu_state.show_save_option:
            old_selected_index = menu_state.selected_index
            menu_state.selected_index = max_index
            menu_state.help_win = move_highlight(
                old_selected_index, options, menu_win, menu_pad, menu_state=menu_state, max_help_lines=max_help_lines
            )

        elif key in (curses.KEY_RIGHT, 10, 13):  # 10 = \n, 13 = carriage return

            need_redraw = True
            menu_win.erase()
            menu_win.refresh()

            if menu_state.selected_index < len(options):  # Handle selection of a menu item
                selected_key = options[menu_state.selected_index]
                menu_state.menu_path.append(str(selected_key))
                menu_state.start_index.append(0)
                menu_state.menu_index.append(menu_state.selected_index)

                # Handle nested data
                if isinstance(menu_state.current_menu, dict):
                    if selected_key in menu_state.current_menu:
                        selected_data = menu_state.current_menu[selected_key]
                    else:
                        continue  # Skip invalid key
                elif isinstance(menu_state.current_menu, list):
                    selected_data = menu_state.current_menu[int(selected_key.strip("[]"))]

                if isinstance(selected_data, list) and len(selected_data) == 2:
                    # Edit color pair
                    new_value = edit_color_pair(selected_key, selected_data)
                    menu_state.menu_path.pop()
                    menu_state.start_index.pop()
                    menu_state.menu_index.pop()
                    menu_state.current_menu[selected_key] = new_value

                elif isinstance(selected_data, (dict, list)):
                    # Navigate into nested data
                    menu_state.current_menu = selected_data
                    menu_state.selected_index = 0  # Reset the selected index

                else:
                    # General value editing
                    new_value = edit_value(selected_key, selected_data)
                    menu_state.menu_path.pop()
                    menu_state.menu_index.pop()
                    menu_state.start_index.pop()
                    menu_state.current_menu[selected_key] = new_value
                    need_redraw = True

            else:
                # Save button selected
                save_json(file_path, data)
                stdscr.refresh()
                continue

        elif key in (27, curses.KEY_LEFT):  # Escape or Left Arrow

            need_redraw = True
            menu_win.erase()
            menu_win.refresh()

            # menu_state.selected_index = menu_state.menu_index[-1]

            # Navigate back in the menu
            if len(menu_state.menu_path) > 2:
                menu_state.menu_path.pop()
                menu_state.start_index.pop()
                menu_state.current_menu = data

                for path in menu_state.menu_path[2:]:
                    menu_state.current_menu = (
                        menu_state.current_menu[path]
                        if isinstance(menu_state.current_menu, dict)
                        else menu_state.current_menu[int(path.strip("[]"))]
                    )

            else:
                # Exit the editor
                menu_win.clear()
                menu_win.refresh()

                break


def save_json(file_path: str, data: Dict[str, Any]) -> None:
    formatted_json = format_json_single_line_arrays(data)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(formatted_json)
    setup_colors(reinit=True)


def main(stdscr: curses.window) -> None:
    from contact.ui.ui_state import MenuState

    menu_state = MenuState()
    if len(menu_state.menu_path) == 0:
        menu_state.menu_path = ["App Settings"]  # Initialize if not set

    curses.curs_set(0)
    stdscr.keypad(True)
    setup_colors()
    json_editor(stdscr, menu_state)


if __name__ == "__main__":
    curses.wrapper(main)
