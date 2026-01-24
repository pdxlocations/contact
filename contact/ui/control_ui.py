import base64
import curses
import logging
import os
import sys
from typing import List

from contact.utilities.save_to_radio import save_changes
import contact.ui.default_config as config
from contact.utilities.config_io import config_export, config_import
from contact.utilities.control_utils import transform_menu_path
from contact.utilities.i18n import t
from contact.utilities.ini_utils import parse_ini_file
from contact.utilities.input_handlers import (
    get_repeated_input,
    get_text_input,
    get_fixed32_input,
    get_list_input,
    get_admin_key_input,
)
from contact.ui.colors import get_color
from contact.ui.dialog import dialog
from contact.ui.menus import generate_menu_from_protobuf
from contact.ui.nav_utils import move_highlight, draw_arrows, update_help_window
from contact.ui.user_config import json_editor
from contact.utilities.singleton import menu_state

# Setup Variables
MAX_MENU_WIDTH = 80  # desired max; will shrink on small terminals
save_option = "Save Changes"
max_help_lines = 0
help_win = None
sensitive_settings = ["Reboot", "Reset Node DB", "Shutdown", "Factory Reset"]


# Compute the effective menu width for the current terminal
def get_menu_width() -> int:
    # Leave at least 2 columns for borders; clamp to >= 20 for usability
    return max(20, min(MAX_MENU_WIDTH, curses.COLS - 2))


sensitive_settings = ["Reboot", "Reset Node DB", "Shutdown", "Factory Reset"]

# Get the parent directory of the script
script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.abspath(os.path.join(script_dir, os.pardir))

# Paths
# locals_dir = os.path.dirname(os.path.abspath(sys.argv[0]))  # Current script directory
translation_file = config.get_localisation_file(config.language)

# config_folder = os.path.join(locals_dir, "node-configs")
config_folder = os.path.abspath(config.node_configs_file_path)

# Load translations
field_mapping, help_text = parse_ini_file(translation_file)


def reload_translations() -> None:
    global translation_file, field_mapping, help_text
    translation_file = config.get_localisation_file(config.language)
    field_mapping, help_text = parse_ini_file(translation_file)


def get_translated_header(menu_path: List[str]) -> str:
    if not menu_path:
        return ""

    transformed_path = transform_menu_path(menu_path)
    translated_parts = []
    for idx, part in enumerate(menu_path):
        if idx == 0:
            translated_parts.append(field_mapping.get(part, part))
            continue
        full_key = ".".join(transformed_path[:idx])
        translated_parts.append(field_mapping.get(full_key, part))
    return " > ".join(translated_parts)


def display_menu() -> tuple[object, object]:
    # if help_win:
    #     min_help_window_height = 6
    # else:
    #     min_help_window_height = 0

    min_help_window_height = 6

    num_items = len(menu_state.current_menu) + (1 if menu_state.show_save_option else 0)

    # Determine the available height for the menu
    max_menu_height = curses.LINES
    menu_height = min(max_menu_height - min_help_window_height, num_items + 5)
    w = get_menu_width()
    start_y = (curses.LINES - menu_height) // 2 - (min_help_window_height // 2)
    start_x = (curses.COLS - w) // 2

    # Calculate remaining space for help window
    global max_help_lines
    remaining_space = curses.LINES - (start_y + menu_height + 2)  # +2 for padding
    max_help_lines = max(remaining_space, 1)  # Ensure at least 1 lines for help

    menu_win = curses.newwin(menu_height, w, start_y, start_x)
    menu_win.erase()
    menu_win.bkgd(get_color("background"))
    menu_win.attrset(get_color("window_frame"))
    menu_win.border()
    menu_win.keypad(True)

    menu_pad = curses.newpad(len(menu_state.current_menu) + 1, w - 8)
    menu_pad.bkgd(get_color("background"))

    header = get_translated_header(menu_state.menu_path)
    if len(header) > w - 4:
        header = header[: w - 7] + "..."
    menu_win.addstr(1, 2, header, get_color("settings_breadcrumbs", bold=True))

    transformed_path = transform_menu_path(menu_state.menu_path)

    for idx, option in enumerate(menu_state.current_menu):
        field_info = menu_state.current_menu[option]
        current_value = field_info[1] if isinstance(field_info, tuple) else ""
        full_key = ".".join(transformed_path + [option])
        display_name = field_mapping.get(full_key, option)

        display_option = f"{display_name}"[: w // 2 - 2]
        display_value = f"{current_value}"[: w // 2 - 4]

        try:
            color = get_color(
                "settings_sensitive" if option in sensitive_settings else "settings_default",
                reverse=(idx == menu_state.selected_index),
            )
            menu_pad.addstr(idx, 0, f"{display_option:<{w // 2 - 2}} {display_value}".ljust(w - 8), color)
        except curses.error:
            pass

    if menu_state.show_save_option:
        save_position = menu_height - 2
        save_label = t("ui.save_changes", default=save_option)
        menu_win.addstr(
            save_position,
            (w - len(save_label)) // 2,
            save_label,
            get_color("settings_save", reverse=(menu_state.selected_index == len(menu_state.current_menu))),
        )

    # Draw help window with dynamically updated max_help_lines
    draw_help_window(start_y, start_x, menu_height, max_help_lines, transformed_path)

    menu_win.refresh()
    menu_pad.refresh(
        menu_state.start_index[-1],
        0,
        menu_win.getbegyx()[0] + 3,
        menu_win.getbegyx()[1] + 4,
        menu_win.getbegyx()[0] + 3 + menu_win.getmaxyx()[0] - 5 - (2 if menu_state.show_save_option else 0),
        menu_win.getbegyx()[1] + menu_win.getmaxyx()[1] - 4,
    )
    curses.curs_set(0)

    max_index = num_items + (1 if menu_state.show_save_option else 0) - 1
    visible_height = menu_win.getmaxyx()[0] - 5 - (2 if menu_state.show_save_option else 0)

    draw_arrows(menu_win, visible_height, max_index, menu_state.start_index, menu_state.show_save_option)

    return menu_win, menu_pad


def draw_help_window(
    menu_start_y: int,
    menu_start_x: int,
    menu_height: int,
    max_help_lines: int,
    transformed_path: List[str],
) -> None:
    global help_win

    if "help_win" not in globals():
        help_win = None  # Initialize if it does not exist

    selected_option = (
        list(menu_state.current_menu.keys())[menu_state.selected_index] if menu_state.current_menu else None
    )
    help_y = menu_start_y + menu_height

    # Use current terminal width for the help window width calculation
    help_win = update_help_window(
        help_win, help_text, transformed_path, selected_option, max_help_lines, get_menu_width(), help_y, menu_start_x
    )


def get_input_type_for_field(field) -> type:
    if field.type in (field.TYPE_INT32, field.TYPE_UINT32, field.TYPE_INT64):
        return int
    elif field.type in (field.TYPE_FLOAT, field.TYPE_DOUBLE):
        return float
    else:
        return str


def settings_menu(stdscr: object, interface: object) -> None:
    curses.update_lines_cols()

    menu = generate_menu_from_protobuf(interface)
    menu_state.current_menu = menu["Main Menu"]
    menu_state.menu_path = ["Main Menu"]

    modified_settings = {}

    menu_state.need_redraw = True
    menu_state.show_save_option = False
    new_value_name = None

    while True:
        if menu_state.need_redraw:
            menu_state.need_redraw = False
            options = list(menu_state.current_menu.keys())

            # Determine if save option should be shown
            path = menu_state.menu_path
            menu_state.show_save_option = (
                (len(path) > 2 and ("Radio Settings" in path or "Module Settings" in path))
                or (len(path) == 2 and "User Settings" in path)
                or (len(path) == 3 and "Channels" in path)
            )

            # Display the menu
            menu_win, menu_pad = display_menu()

        if menu_win is None:
            continue  # Skip if menu_win is not initialized

        menu_win.timeout(200)  # wait up to 200 ms for a keypress (or less if key is pressed)
        key = menu_win.getch()
        if key == -1:
            continue

        max_index = len(options) + (1 if menu_state.show_save_option else 0) - 1
        # max_help_lines = 4

        if key == curses.KEY_UP:
            old_selected_index = menu_state.selected_index
            menu_state.selected_index = max_index if menu_state.selected_index == 0 else menu_state.selected_index - 1
            move_highlight(
                old_selected_index,
                options,
                menu_win,
                menu_pad,
                menu_state=menu_state,
                help_win=help_win,
                help_text=help_text,
                max_help_lines=max_help_lines,
            )

        elif key == curses.KEY_DOWN:
            old_selected_index = menu_state.selected_index
            menu_state.selected_index = 0 if menu_state.selected_index == max_index else menu_state.selected_index + 1
            move_highlight(
                old_selected_index,
                options,
                menu_win,
                menu_pad,
                menu_state=menu_state,
                help_win=help_win,
                help_text=help_text,
                max_help_lines=max_help_lines,
            )

        elif key == curses.KEY_RESIZE:
            menu_state.need_redraw = True
            curses.update_lines_cols()

            menu_win.erase()
            if help_win:
                help_win.erase()

            menu_win.refresh()
            if help_win:
                help_win.refresh()

        elif key == ord("\t") and menu_state.show_save_option:
            old_selected_index = menu_state.selected_index
            menu_state.selected_index = max_index
            move_highlight(
                old_selected_index,
                options,
                menu_win,
                menu_pad,
                menu_state=menu_state,
                help_win=help_win,
                help_text=help_text,
                max_help_lines=max_help_lines,
            )

        elif key == curses.KEY_RIGHT or key == ord("\n"):
            menu_state.need_redraw = True
            menu_state.start_index.append(0)
            menu_win.erase()
            if help_win:
                help_win.erase()

            # draw_help_window(menu_win.getbegyx()[0], menu_win.getbegyx()[1], menu_win.getmaxyx()[0], max_help_lines, menu_state.current_menu, selected_index, transform_menu_path(menu_state.menu_path))

            menu_win.refresh()
            if help_win:
                help_win.refresh()

            if menu_state.show_save_option and menu_state.selected_index == len(options):
                save_changes(interface, modified_settings, menu_state)
                modified_settings.clear()
                logging.info("Changes Saved")

                if len(menu_state.menu_path) > 1:
                    menu_state.menu_path.pop()
                    menu_state.current_menu = menu["Main Menu"]
                    for step in menu_state.menu_path[1:]:
                        menu_state.current_menu = menu_state.current_menu.get(step, {})
                    menu_state.selected_index = 0
                continue

            selected_option = options[menu_state.selected_index]

            if selected_option == "Exit":
                break

            elif selected_option == "Export Config File":

                filename = get_text_input(
                    t("ui.prompt.config_filename", default="Enter a filename for the config file"),
                    None,
                    None,
                )
                if not filename:
                    logging.info("Export aborted: No filename provided.")
                    menu_state.start_index.pop()
                    continue  # Go back to the menu
                if not filename.lower().endswith(".yaml"):
                    filename += ".yaml"

                try:
                    config_text = config_export(interface)
                    yaml_file_path = os.path.join(config_folder, filename)

                    if os.path.exists(yaml_file_path):
                        overwrite = get_list_input(
                            t(
                                "ui.confirm.overwrite_file",
                                default="{filename} already exists. Overwrite?",
                                filename=filename,
                            ),
                            None,
                            ["Yes", "No"],
                        )
                        if overwrite == "No":
                            logging.info("Export cancelled: User chose not to overwrite.")
                            menu_state.start_index.pop()
                            continue  # Return to menu
                    os.makedirs(os.path.dirname(yaml_file_path), exist_ok=True)
                    with open(yaml_file_path, "w", encoding="utf-8") as file:
                        file.write(config_text)
                    logging.info(f"Config file saved to {yaml_file_path}")
                    dialog(t("ui.dialog.config_saved_title", default="Config File Saved:"), yaml_file_path)
                    menu_state.need_redraw = True
                    menu_state.start_index.pop()
                    continue
                except PermissionError:
                    logging.error(f"Permission denied: Unable to write to {yaml_file_path}")
                except OSError as e:
                    logging.error(f"OS error while saving config: {e}")
                except Exception as e:
                    logging.error(f"Unexpected error: {e}")
                menu_state.start_index.pop()
                continue

            elif selected_option == "Load Config File":

                # Check if folder exists and is not empty
                if not os.path.exists(config_folder) or not any(os.listdir(config_folder)):
                    dialog("", t("ui.dialog.no_config_files", default=" No config files found. Export a config first."))
                    menu_state.need_redraw = True
                    continue  # Return to menu

                file_list = [f for f in os.listdir(config_folder) if os.path.isfile(os.path.join(config_folder, f))]

                # Ensure file_list is not empty before proceeding
                if not file_list:
                    dialog("", t("ui.dialog.no_config_files", default=" No config files found. Export a config first."))
                    menu_state.need_redraw = True
                    continue

                filename = get_list_input(
                    t("ui.prompt.choose_config_file", default="Choose a config file"), None, file_list
                )
                if filename:
                    file_path = os.path.join(config_folder, filename)
                    overwrite = get_list_input(
                        t(
                            "ui.confirm.load_config_file",
                            default="Are you sure you want to load {filename}?",
                            filename=filename,
                        ),
                        None,
                        ["Yes", "No"],
                    )
                    if overwrite == "Yes":
                        config_import(interface, file_path)
                menu_state.start_index.pop()
                continue

            elif selected_option == "Config URL":
                current_value = interface.localNode.getURL()
                new_value = get_text_input(
                    t(
                        "ui.prompt.config_url_current",
                        default="Config URL is currently: {value}",
                        value=current_value,
                    ),
                    None,
                    str,
                )
                if new_value is not None:
                    current_value = new_value
                    overwrite = get_list_input(
                        t("ui.confirm.load_config_url", default="Are you sure you want to load this config?"),
                        None,
                        ["Yes", "No"],
                    )
                    if overwrite == "Yes":
                        interface.localNode.setURL(new_value)
                        logging.info(f"New Config URL sent to node")
                menu_state.start_index.pop()
                continue

            elif selected_option == "Reboot":
                confirmation = get_list_input(
                    t("ui.confirm.reboot", default="Are you sure you want to Reboot?"), None, ["Yes", "No"]
                )
                if confirmation == "Yes":
                    interface.localNode.reboot()
                    logging.info(f"Node Reboot Requested by menu")
                menu_state.start_index.pop()
                continue

            elif selected_option == "Reset Node DB":
                confirmation = get_list_input(
                    t("ui.confirm.reset_node_db", default="Are you sure you want to Reset Node DB?"),
                    None,
                    ["Yes", "No"],
                )
                if confirmation == "Yes":
                    interface.localNode.resetNodeDb()
                    logging.info(f"Node DB Reset Requested by menu")
                menu_state.start_index.pop()
                continue

            elif selected_option == "Shutdown":
                confirmation = get_list_input(
                    t("ui.confirm.shutdown", default="Are you sure you want to Shutdown?"), None, ["Yes", "No"]
                )
                if confirmation == "Yes":
                    interface.localNode.shutdown()
                    logging.info(f"Node Shutdown Requested by menu")
                menu_state.start_index.pop()
                continue

            elif selected_option == "Factory Reset":
                confirmation = get_list_input(
                    t("ui.confirm.factory_reset", default="Are you sure you want to Factory Reset?"),
                    None,
                    ["Yes", "No"],
                )
                if confirmation == "Yes":
                    interface.localNode.factoryReset()
                    logging.info(f"Factory Reset Requested by menu")
                menu_state.start_index.pop()
                continue

            elif selected_option == "App Settings":
                menu_win.clear()
                menu_win.refresh()
                menu_state.menu_path.append("App Settings")
                menu_state.menu_index.append(menu_state.selected_index)
                json_editor(stdscr, menu_state)  # Open the App Settings menu
                reload_translations()
                menu_state.current_menu = menu["Main Menu"]
                menu_state.menu_path = ["Main Menu"]
                menu_state.start_index.pop()
                menu_state.selected_index = 4
                continue

            field_info = menu_state.current_menu.get(selected_option)
            if isinstance(field_info, tuple):
                field, current_value = field_info

                # Transform the menu path to get the full key
                transformed_path = transform_menu_path(menu_state.menu_path)
                full_key = ".".join(transformed_path + [selected_option])

                # Fetch human-readable name from field_mapping
                human_readable_name = field_mapping.get(full_key, selected_option)

                if selected_option in ["longName", "shortName", "isLicensed"]:
                    if selected_option in ["longName", "shortName"]:
                        new_value = get_text_input(
                            f"{human_readable_name} is currently: {current_value}", selected_option, None
                        )
                        new_value = current_value if new_value is None else new_value
                        menu_state.current_menu[selected_option] = (field, new_value)

                    elif selected_option == "isLicensed":
                        new_value = get_list_input(
                            f"{human_readable_name} is currently: {current_value}",
                            str(current_value),
                            ["True", "False"],
                        )
                        new_value = new_value == "True"
                        menu_state.current_menu[selected_option] = (field, new_value)

                    for option, (field, value) in menu_state.current_menu.items():
                        modified_settings[option] = value

                    menu_state.start_index.pop()

                elif selected_option in ["latitude", "longitude", "altitude"]:
                    new_value = get_text_input(
                        f"{human_readable_name} is currently: {current_value}", selected_option, float
                    )
                    new_value = current_value if new_value is None else new_value
                    menu_state.current_menu[selected_option] = (field, new_value)

                    for option in ["latitude", "longitude", "altitude"]:
                        if option in menu_state.current_menu:
                            modified_settings[option] = menu_state.current_menu[option][1]

                    menu_state.start_index.pop()

                elif selected_option == "admin_key":
                    new_values = get_admin_key_input(current_value)
                    new_value = current_value if new_values is None else [base64.b64decode(key) for key in new_values]
                    menu_state.start_index.pop()

                elif field.type == 8:  # Handle boolean type
                    new_value = get_list_input(human_readable_name, str(current_value), ["True", "False"])
                    if new_value == "Not Set":
                        pass  # Leave it as-is
                    else:
                        new_value = new_value == "True" or new_value is True
                    menu_state.start_index.pop()

                elif field.label == field.LABEL_REPEATED:  # Handle repeated field - Not currently used
                    new_value = get_repeated_input(current_value)
                    new_value = current_value if new_value is None else new_value.split(", ")
                    menu_state.start_index.pop()

                elif field.enum_type:  # Enum field
                    enum_options = {v.name: v.number for v in field.enum_type.values}
                    new_value_name = get_list_input(human_readable_name, current_value, list(enum_options.keys()))
                    new_value = enum_options.get(new_value_name, current_value)
                    menu_state.start_index.pop()

                elif field.type == 7:  # Field type 7 corresponds to FIXED32
                    new_value = get_fixed32_input(current_value)
                    menu_state.start_index.pop()

                elif field.type == 13:  # Field type 13 corresponds to UINT32
                    input_type = get_input_type_for_field(field)
                    new_value = get_text_input(
                        f"{human_readable_name} is currently: {current_value}", selected_option, input_type
                    )
                    new_value = current_value if new_value is None else int(new_value)
                    menu_state.start_index.pop()

                elif field.type == 2:  # Field type 13 corresponds to INT64
                    input_type = get_input_type_for_field(field)
                    new_value = get_text_input(
                        f"{human_readable_name} is currently: {current_value}", selected_option, input_type
                    )
                    new_value = current_value if new_value is None else float(new_value)
                    menu_state.start_index.pop()

                else:  # Handle other field types
                    input_type = get_input_type_for_field(field)
                    new_value = get_text_input(
                        f"{human_readable_name} is currently: {current_value}", selected_option, input_type
                    )
                    new_value = current_value if new_value is None else new_value
                    menu_state.start_index.pop()

                for key in menu_state.menu_path[3:]:  # Skip "Main Menu"
                    modified_settings = modified_settings.setdefault(key, {})

                # For comparison, normalize enum numbers to names
                compare_value = new_value
                if field and field.enum_type and isinstance(new_value, int):
                    enum_value_descriptor = field.enum_type.values_by_number.get(new_value)
                    if enum_value_descriptor:
                        compare_value = enum_value_descriptor.name

                if compare_value != current_value:
                    # Save the raw protobuf number, not the name
                    modified_settings[selected_option] = new_value

                # Convert enum string to int
                if field and field.enum_type:
                    enum_value_descriptor = field.enum_type.values_by_number.get(new_value)
                    new_value = enum_value_descriptor.name if enum_value_descriptor else new_value

                menu_state.current_menu[selected_option] = (field, new_value)
            else:
                menu_state.current_menu = menu_state.current_menu[selected_option]
                menu_state.menu_path.append(selected_option)
                menu_state.menu_index.append(menu_state.selected_index)
                menu_state.selected_index = 0

        elif key == curses.KEY_LEFT:

            # If we are at the main menu and there are unsaved changes, prompt to save
            if len(menu_state.menu_path) == 3 and modified_settings:

                current_section = menu_state.menu_path[-1]
                save_prompt = get_list_input(
                    t(
                        "ui.confirm.save_before_exit_section",
                        default="You have unsaved changes in {section}. Save before exiting?",
                        section=current_section,
                    ),
                    None,
                    ["Yes", "No", "Cancel"],
                    mandatory=True,
                )
                if save_prompt == "Cancel":
                    continue  # Stay in the menu without doing anything
                elif save_prompt == "Yes":
                    save_changes(interface, modified_settings, menu_state)
                    logging.info("Changes Saved")

                modified_settings.clear()
                menu = rebuild_menu_at_current_path(interface, menu_state)
                pass

            menu_state.need_redraw = True

            menu_win.erase()
            if help_win:
                help_win.erase()

            # max_help_lines = 4
            # draw_help_window(menu_win.getbegyx()[0], menu_win.getbegyx()[1], menu_win.getmaxyx()[0], max_help_lines, menu_state.current_menu, selected_index, transform_menu_path(menu_state.menu_path))

            menu_win.refresh()
            if help_win:
                help_win.refresh()

            # if len(menu_state.menu_path) < 2:
            #     modified_settings.clear()

            # Navigate back to the previous menu
            if len(menu_state.menu_path) > 1:
                menu_state.menu_path.pop()
                menu_state.current_menu = menu["Main Menu"]
                for step in menu_state.menu_path[1:]:
                    menu_state.current_menu = menu_state.current_menu.get(step, {})
                menu_state.selected_index = menu_state.menu_index.pop()
                menu_state.start_index.pop()

        elif key == 27:  # Escape key
            menu_win.erase()
            menu_win.refresh()
            break


def rebuild_menu_at_current_path(interface, menu_state):
    """Rebuild menus from the device and re-point current_menu to the same path."""
    new_menu = generate_menu_from_protobuf(interface)
    cur = new_menu["Main Menu"]
    for step in menu_state.menu_path[1:]:
        cur = cur.get(step, {})
    menu_state.current_menu = cur
    return new_menu


def set_region(interface: object) -> None:
    node = interface.getNode("^local")
    device_config = node.localConfig
    lora_descriptor = device_config.lora.DESCRIPTOR

    # Get the enum mapping of region names to their numerical values
    region_enum = lora_descriptor.fields_by_name["region"].enum_type
    region_name_to_number = {v.name: v.number for v in region_enum.values}

    regions = list(region_name_to_number.keys())

    new_region_name = get_list_input(
        t("ui.prompt.select_region", default="Select your region:"), "UNSET", regions
    )

    # Convert region name to corresponding enum number
    new_region_number = region_name_to_number.get(new_region_name, 0)  # Default to 0 if not found

    node.localConfig.lora.region = new_region_number
    node.writeConfig("lora")
