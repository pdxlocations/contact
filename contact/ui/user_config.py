import os
import json
import curses
from typing import Any, List, Dict, Optional

from contact.ui.colors import get_color, setup_colors, COLOR_MAP
import contact.ui.default_config as config
from contact.ui.nav_utils import move_highlight, draw_arrows, update_help_window
from contact.utilities.ini_utils import parse_ini_file
from contact.utilities.input_handlers import get_list_input
from contact.utilities.i18n import t
from contact.utilities.singleton import menu_state


MAX_MENU_WIDTH = 80  # desired max; will shrink on small terminals
max_help_lines = 6
save_option = "Save Changes"
translation_file = config.get_localisation_file(config.language)
field_mapping, help_text = parse_ini_file(translation_file)
translation_language = config.language


def reload_translations(language: Optional[str] = None) -> None:
    global translation_file, field_mapping, help_text, translation_language
    target_language = language or config.language
    translation_file = config.get_localisation_file(target_language)
    field_mapping, help_text = parse_ini_file(translation_file)
    translation_language = target_language


def get_app_settings_key(menu_path: List[str], selected_key: str) -> str:
    parts = ["app_settings"]
    for part in menu_path:
        if part in ("Main Menu", "App Settings"):
            continue
        parts.append(part)
    parts.append(selected_key)
    return ".".join(parts)


def get_app_settings_path_parts(menu_path: List[str]) -> List[str]:
    parts = ["app_settings"]
    for part in menu_path:
        if part in ("Main Menu", "App Settings"):
            continue
        parts.append(part)
    return parts


def lookup_app_settings_label(full_key: str, fallback: str) -> str:
    label = field_mapping.get(full_key)
    if label:
        return label
    parts = full_key.split(".")
    if len(parts) >= 2 and parts[1].startswith("COLOR_CONFIG_"):
        unified_key = ".".join([parts[0], "color_config"] + parts[2:])
        return field_mapping.get(unified_key, fallback)
    return fallback


def get_app_settings_help_path_parts(menu_path: List[str]) -> List[str]:
    parts = get_app_settings_path_parts(menu_path)
    if parts and parts[-1] in ("COLOR_CONFIG_DARK", "COLOR_CONFIG_LIGHT", "COLOR_CONFIG_GREEN"):
        parts[-1] = "color_config"
    return parts


def get_app_settings_header(menu_path: List[str]) -> str:
    if not menu_path:
        return ""
    translated_parts = []
    for idx, part in enumerate(menu_path):
        if idx == 0:
            translated_parts.append(field_mapping.get(part, part))
            continue
        if part in ("Main Menu", "App Settings"):
            continue
        full_key = ".".join(get_app_settings_path_parts(menu_path[: idx + 1]))
        translated_parts.append(lookup_app_settings_label(full_key, part))
    return " > ".join(translated_parts)


# Compute an effective width that fits the current terminal
def get_effective_width() -> int:
    # Leave space for borders; ensure a sane minimum
    return max(20, min(MAX_MENU_WIDTH, curses.COLS - 2))


def edit_color_pair(key: str, display_label: str, current_value: List[str]) -> List[str]:
    """
    Allows the user to select a foreground and background color for a key.
    """
    color_list = [" "] + list(COLOR_MAP.keys())
    fg_color = get_list_input(
        t(
            "ui.prompt.select_foreground_color",
            default="Select Foreground Color for {label}",
            label=display_label,
        ),
        current_value[0],
        color_list,
    )
    bg_color = get_list_input(
        t(
            "ui.prompt.select_background_color",
            default="Select Background Color for {label}",
            label=display_label,
        ),
        current_value[1],
        color_list,
    )

    return [fg_color, bg_color]


def edit_value(key: str, display_label: str, current_value: str) -> str:

    w = get_effective_width()
    height = 10
    input_width = w - 16  # Allow space for "New Value: "
    start_y = (curses.LINES - height) // 2
    start_x = max(0, (curses.COLS - w) // 2)

    # Create a centered window
    edit_win = curses.newwin(height, w, start_y, start_x)
    edit_win.bkgd(get_color("background"))
    edit_win.attrset(get_color("window_frame"))
    edit_win.border()

    # Display instructions
    edit_win.addstr(
        1,
        2,
        t("ui.label.editing", default="Editing {label}", label=display_label),
        get_color("settings_default", bold=True),
    )
    edit_win.addstr(3, 2, t("ui.label.current_value", default="Current Value:"), get_color("settings_default"))

    wrap_width = w - 4  # Account for border and padding
    wrapped_lines = [current_value[i : i + wrap_width] for i in range(0, len(current_value), wrap_width)]

    for i, line in enumerate(wrapped_lines[:4]):  # Limit display to fit the window height
        edit_win.addstr(4 + i, 2, line, get_color("settings_default"))

    edit_win.refresh()

    # Handle theme selection dynamically
    if key == "theme":
        # Load theme names dynamically from the JSON
        theme_options = [
            k.split("_", 2)[2].lower() for k in config.loaded_config.keys() if k.startswith("COLOR_CONFIG")
        ]
        return get_list_input(
            t("ui.prompt.select_value", default="Select {label}", label=display_label),
            current_value,
            theme_options,
        )

    elif key == "language":
        language_options = config.get_localisation_options()
        if not language_options:
            return current_value
        return get_list_input(
            t("ui.prompt.select_value", default="Select {label}", label=display_label),
            current_value,
            language_options,
        )

    elif key == "node_sort":
        sort_options = ["lastHeard", "name", "hops"]
        return get_list_input(display_label, current_value, sort_options)

    elif key == "notification_sound":
        sound_options = ["True", "False"]
        return get_list_input(display_label, current_value, sound_options)

    elif key == "single_pane_mode":
        sound_options = ["True", "False"]
        return get_list_input(display_label, current_value, sound_options)

    # Standard Input Mode (Scrollable)
    edit_win.addstr(7, 2, t("ui.label.new_value", default="New Value: "), get_color("settings_default"))
    curses.curs_set(1)

    scroll_offset = 0  # Determines which part of the text is visible
    user_input = ""
    input_position = (7, 13)  # Tuple for row and column
    row, col = input_position  # Unpack tuple

    while True:
        if menu_state.need_redraw:
            curses.update_lines_cols()
            menu_state.need_redraw = False

            # Re-create the window to fully reset state
            edit_win = curses.newwin(height, w, start_y, start_x)
            edit_win.timeout(200)
            edit_win.bkgd(get_color("background"))
            edit_win.attrset(get_color("window_frame"))
            edit_win.border()

            # Redraw static content
            edit_win.addstr(
                1,
                2,
                t("ui.label.editing", default="Editing {label}", label=display_label),
                get_color("settings_default", bold=True),
            )
            edit_win.addstr(
                3, 2, t("ui.label.current_value", default="Current Value:"), get_color("settings_default")
            )
            for i, line in enumerate(wrapped_lines[:4]):
                edit_win.addstr(4 + i, 2, line, get_color("settings_default"))
            edit_win.addstr(
                7, 2, t("ui.label.new_value", default="New Value: "), get_color("settings_default")
            )

        visible_text = user_input[scroll_offset : scroll_offset + input_width]
        edit_win.addstr(row, col, " " * input_width, get_color("settings_default"))
        edit_win.addstr(row, col, visible_text, get_color("settings_default"))
        edit_win.refresh()

        edit_win.move(row, col + min(len(user_input) - scroll_offset, input_width))

        try:
            key = edit_win.get_wch()
        except curses.error:
            continue  # window not ready — skip this loop

        if key in (chr(27), curses.KEY_LEFT):
            curses.curs_set(0)
            return current_value

        elif key in (chr(curses.KEY_ENTER), chr(10), chr(13)):
            break

        elif key in (curses.KEY_BACKSPACE, chr(127)):
            if user_input:
                user_input = user_input[:-1]
                if scroll_offset > 0 and len(user_input) < scroll_offset + input_width:
                    scroll_offset -= 1
        else:
            if isinstance(key, str):
                user_input += key
            else:
                user_input += chr(key)

            if len(user_input) > input_width:
                scroll_offset += 1

    curses.curs_set(0)
    return user_input if user_input else current_value


def display_menu() -> tuple[Any, Any, List[str]]:
    """
    Render the configuration menu with a Save button directly added to the window.
    """
    if translation_language != config.language:
        reload_translations()

    num_items = len(menu_state.current_menu) + (1 if menu_state.show_save_option else 0)

    # Determine menu items based on the type of current_menu
    if isinstance(menu_state.current_menu, dict):
        options = list(menu_state.current_menu.keys())
    elif isinstance(menu_state.current_menu, list):
        options = [f"[{i}]" for i in range(len(menu_state.current_menu))]
    else:
        options = []  # Fallback in case of unexpected data types

    # Calculate dynamic dimensions for the menu
    min_help_window_height = 6
    max_menu_height = curses.LINES
    menu_height = min(max_menu_height - min_help_window_height, num_items + 5)
    num_items = len(options)
    w = get_effective_width()
    start_y = (curses.LINES - menu_height) // 2 - (min_help_window_height // 2)
    start_x = max(0, (curses.COLS - w) // 2)

    # Create the window
    menu_win = curses.newwin(menu_height, w, start_y, start_x)
    menu_win.erase()
    menu_win.bkgd(get_color("background"))
    menu_win.attrset(get_color("window_frame"))
    menu_win.border()
    menu_win.keypad(True)

    # Create the pad for scrolling
    menu_pad = curses.newpad(num_items + 1, w - 8)
    menu_pad.bkgd(get_color("background"))

    # Display the menu path
    header = get_app_settings_header(menu_state.menu_path)
    if len(header) > w - 4:
        header = header[: w - 7] + "..."
    menu_win.addstr(1, 2, header, get_color("settings_breadcrumbs", bold=True))

    # Populate the pad with menu options
    for idx, key in enumerate(options):
        value = (
            menu_state.current_menu[key]
            if isinstance(menu_state.current_menu, dict)
            else menu_state.current_menu[int(key.strip("[]"))]
        )
        if isinstance(menu_state.current_menu, dict):
            full_key = get_app_settings_key(menu_state.menu_path, key)
            display_key = lookup_app_settings_label(full_key, key)
        else:
            display_key = key
        display_key = f"{display_key}"[: w // 2 - 2]
        display_value = f"{value}"[: w // 2 - 8]

        color = get_color("settings_default", reverse=(idx == menu_state.selected_index))
        menu_pad.addstr(idx, 0, f"{display_key:<{w // 2 - 2}} {display_value}".ljust(w - 8), color)

    # Add Save button to the main window
    if menu_state.show_save_option:
        save_position = menu_height - 2
        save_label = t("ui.save_changes", default=save_option)
        menu_win.addstr(
            save_position,
            (w - len(save_label)) // 2,
            save_label,
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

    # Draw help window below the menu
    global max_help_lines
    remaining_space = curses.LINES - (start_y + menu_height + 2)
    max_help_lines = max(remaining_space, 1)
    transformed_path = get_app_settings_help_path_parts(menu_state.menu_path)
    selected_option = (
        options[min(menu_state.selected_index, len(options) - 1)] if options and menu_state.selected_index >= 0 else None
    )
    help_y = menu_win.getbegyx()[0] + menu_win.getmaxyx()[0]
    menu_state.help_win = update_help_window(
        menu_state.help_win,
        help_text,
        transformed_path,
        selected_option,
        max_help_lines,
        w,
        help_y,
        menu_win.getbegyx()[1],
    )

    return menu_win, menu_pad, options


def update_app_settings_help(menu_win: curses.window, options: List[str]) -> None:
    transformed_path = get_app_settings_help_path_parts(menu_state.menu_path)
    selected_option = options[menu_state.selected_index] if menu_state.selected_index < len(options) else None
    help_y = menu_win.getbegyx()[0] + menu_win.getmaxyx()[0]
    menu_state.help_win = update_help_window(
        menu_state.help_win,
        help_text,
        transformed_path,
        selected_option,
        max_help_lines,
        menu_win.getmaxyx()[1],
        help_y,
        menu_win.getbegyx()[1],
    )


def json_editor(stdscr: curses.window, menu_state: Any) -> None:

    menu_state.selected_index = 0  # Track the selected option
    made_changes = False  # Track if any changes were made

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
    menu_win, menu_pad, options = display_menu()
    update_app_settings_help(menu_win, options)
    menu_state.need_redraw = True

    while True:
        if menu_state.need_redraw:
            menu_state.need_redraw = False
            menu_win, menu_pad, options = display_menu()
            menu_win.refresh()
            update_app_settings_help(menu_win, options)

        max_index = len(options) + (1 if menu_state.show_save_option else 0) - 1

        menu_win.timeout(200)
        key = menu_win.getch()

        if key == curses.KEY_UP:

            old_selected_index = menu_state.selected_index
            menu_state.selected_index = max_index if menu_state.selected_index == 0 else menu_state.selected_index - 1
            menu_state.help_win = move_highlight(
                old_selected_index, options, menu_win, menu_pad, menu_state=menu_state, max_help_lines=max_help_lines
            )
            update_app_settings_help(menu_win, options)

        elif key == curses.KEY_DOWN:

            old_selected_index = menu_state.selected_index
            menu_state.selected_index = 0 if menu_state.selected_index == max_index else menu_state.selected_index + 1
            menu_state.help_win = move_highlight(
                old_selected_index, options, menu_win, menu_pad, menu_state=menu_state, max_help_lines=max_help_lines
            )
            update_app_settings_help(menu_win, options)

        elif key == ord("\t") and menu_state.show_save_option:
            old_selected_index = menu_state.selected_index
            menu_state.selected_index = max_index
            menu_state.help_win = move_highlight(
                old_selected_index, options, menu_win, menu_pad, menu_state=menu_state, max_help_lines=max_help_lines
            )
            update_app_settings_help(menu_win, options)

        elif key in (curses.KEY_RIGHT, 10, 13):  # 10 = \n, 13 = carriage return

            menu_state.need_redraw = True
            menu_win.erase()
            menu_win.refresh()
            if menu_state.help_win:
                menu_state.help_win.erase()
                menu_state.help_win.refresh()

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

                display_label = selected_key
                if isinstance(menu_state.current_menu, dict):
                    path_for_label = (
                        menu_state.menu_path[:-1]
                        if menu_state.menu_path and menu_state.menu_path[-1] == str(selected_key)
                        else menu_state.menu_path
                    )
                    full_key = get_app_settings_key(path_for_label, selected_key)
                    display_label = lookup_app_settings_label(full_key, selected_key)

                if isinstance(selected_data, list) and len(selected_data) == 2:
                    # Edit color pair
                    old = selected_data
                    new_value = edit_color_pair(selected_key, display_label, selected_data)
                    menu_state.menu_path.pop()
                    menu_state.start_index.pop()
                    menu_state.menu_index.pop()
                    menu_state.current_menu[selected_key] = new_value
                    if new_value != old:
                        made_changes = True

                elif isinstance(selected_data, (dict, list)):
                    # Navigate into nested data
                    menu_state.current_menu = selected_data
                    menu_state.selected_index = 0  # Reset the selected index

                else:
                    # General value editing
                    old = selected_data
                    new_value = edit_value(selected_key, display_label, selected_data)
                    menu_state.menu_path.pop()
                    menu_state.menu_index.pop()
                    menu_state.start_index.pop()
                    menu_state.current_menu[selected_key] = new_value
                    menu_state.need_redraw = True
                    if new_value != old:
                        made_changes = True

            else:
                # Save button selected
                save_json(file_path, data)
                made_changes = False
                stdscr.refresh()
                # config.reload()  # This isn't refreshing the file paths as expected
                break

        elif key in (27, curses.KEY_LEFT):  # Escape or Left Arrow

            menu_state.need_redraw = True
            menu_win.erase()
            menu_win.refresh()
            if menu_state.help_win:
                menu_state.help_win.erase()
                menu_state.help_win.refresh()

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
                if made_changes:
                    save_prompt = get_list_input(
                        t("ui.confirm.save_before_exit", default="You have unsaved changes. Save before exiting?"),
                        None,
                        ["Yes", "No", "Cancel"],
                        mandatory=True,
                    )
                    if save_prompt == "Cancel":
                        continue  # Stay in the menu without doing anything
                    elif save_prompt == "Yes":
                        save_json(file_path, data)
                        made_changes = False

                menu_win.clear()
                menu_win.refresh()

                break


def save_json(file_path: str, data: Dict[str, Any]) -> None:
    formatted_json = config.format_json_single_line_arrays(data)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(formatted_json)
    setup_colors(reinit=True)
    reload_translations(data.get("language"))


def main(stdscr: curses.window) -> None:
    from contact.ui.ui_state import MenuState

    if len(menu_state.menu_path) == 0:
        menu_state.menu_path = ["App Settings"]  # Initialize if not set

    curses.curs_set(0)
    stdscr.keypad(True)
    setup_colors()
    json_editor(stdscr, menu_state)


if __name__ == "__main__":
    curses.wrapper(main)
