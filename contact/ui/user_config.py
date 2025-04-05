import os
import json
import curses
from contact.ui.colors import get_color, setup_colors, COLOR_MAP
from contact.ui.default_config import format_json_single_line_arrays, loaded_config
from contact.utilities.input_handlers import get_list_input


width = 80
save_option = "Save Changes"
sensitive_settings = []


def edit_color_pair(key, current_value):

    """
    Allows the user to select a foreground and background color for a key.
    """
    color_list = [" "] + list(COLOR_MAP.keys())
    fg_color = get_list_input(f"Select Foreground Color for {key}", current_value[0], color_list)
    bg_color = get_list_input(f"Select Background Color for {key}", current_value[1], color_list)

    return [fg_color, bg_color]

def edit_value(key, current_value, state):

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
    wrapped_lines = [current_value[i:i+wrap_width] for i in range(0, len(current_value), wrap_width)]

    for i, line in enumerate(wrapped_lines[:4]):  # Limit display to fit the window height
        edit_win.addstr(4 + i, 2, line, get_color("settings_default"))

    edit_win.refresh()

    # Handle theme selection dynamically
    if key == "theme":
        # Load theme names dynamically from the JSON
        theme_options = [k.split("_", 2)[2].lower() for k in loaded_config.keys() if k.startswith("COLOR_CONFIG")]
        return get_list_input("Select Theme", current_value, theme_options)
    elif key == "node_sort":
        sort_options = ['lastHeard', 'name', 'hops']
        return get_list_input("Sort By", current_value, sort_options)

    # Standard Input Mode (Scrollable)
    edit_win.addstr(7, 2, "New Value: ", get_color("settings_default"))
    curses.curs_set(1)

    scroll_offset = 0  # Determines which part of the text is visible
    user_input = ""
    input_position = (7, 13)  # Tuple for row and column
    row, col = input_position  # Unpack tuple
    while True:
        visible_text = user_input[scroll_offset:scroll_offset + input_width]  # Only show what fits
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


def display_menu(current_menu, selected_index, show_save_option, state):
    """
    Render the configuration menu with a Save button directly added to the window.
    """
    num_items = len(current_menu) + (1 if show_save_option else 0)

    # Determine menu items based on the type of current_menu
    if isinstance(current_menu, dict):
        options = list(current_menu.keys())
    elif isinstance(current_menu, list):
        options = [f"[{i}]" for i in range(len(current_menu))]
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
    header = " > ".join(state.menu_path)
    if len(header) > width - 4:
        header = header[:width - 7] + "..."
    menu_win.addstr(1, 2, header, get_color("settings_breadcrumbs", bold=True))

    # Populate the pad with menu options
    for idx, key in enumerate(options):
        value = current_menu[key] if isinstance(current_menu, dict) else current_menu[int(key.strip("[]"))]
        display_key = f"{key}"[:width // 2 - 2]
        display_value = (
            f"{value}"[:width // 2 - 8]
        )

        color = get_color("settings_default", reverse=(idx == selected_index))
        menu_pad.addstr(idx, 0, f"{display_key:<{width // 2 - 2}} {display_value}".ljust(width - 8), color)

    # Add Save button to the main window
    if show_save_option:
        save_position = menu_height - 2
        menu_win.addstr(save_position, (width - len(save_option)) // 2, save_option, get_color("settings_save", reverse=(selected_index == len(current_menu))))


    menu_win.refresh()
    menu_pad.refresh(
        state.start_index[-1], 0,
        menu_win.getbegyx()[0] + 3, menu_win.getbegyx()[1] + 4,
        menu_win.getbegyx()[0] + 3 + menu_win.getmaxyx()[0] - 5 - (2 if show_save_option else 0),
        menu_win.getbegyx()[1] + menu_win.getmaxyx()[1] - 4
    )

    max_index = num_items + (1 if show_save_option else 0) - 1
    visible_height = menu_win.getmaxyx()[0] - 5 - (2 if show_save_option else 0)

    draw_arrows(menu_win, visible_height, max_index, state, show_save_option)

    return menu_win, menu_pad, options


def move_highlight(old_idx, new_idx, options, show_save_option, menu_win, menu_pad, state):
    if old_idx == new_idx:  # No-op
        return

    max_index = len(options) + (1 if show_save_option else 0) - 1
    visible_height = menu_win.getmaxyx()[0] - 5 - (2 if show_save_option else 0)

    # Adjust state.start_index only when moving out of visible range
    if new_idx == max_index and show_save_option:
        pass
    elif new_idx < state.start_index[-1]:  # Moving above the visible area
        state.start_index[-1] = new_idx
    elif new_idx >= state.start_index[-1] + visible_height:  # Moving below the visible area
        state.start_index[-1] = new_idx - visible_height
    pass

    # Ensure state.start_index is within bounds
    state.start_index[-1] = max(0, min(state.start_index[-1], max_index - visible_height + 1))

    # Clear old selection
    if show_save_option and old_idx == max_index:
        menu_win.chgat(menu_win.getmaxyx()[0] - 2, (width - len(save_option)) // 2, len(save_option), get_color("settings_save"))
    else:
        menu_pad.chgat(old_idx, 0, menu_pad.getmaxyx()[1], get_color("settings_sensitive") if options[old_idx] in sensitive_settings else get_color("settings_default"))

    # Highlight new selection
    if show_save_option and new_idx == max_index:
        menu_win.chgat(menu_win.getmaxyx()[0] - 2, (width - len(save_option)) // 2, len(save_option), get_color("settings_save", reverse=True))
    else:
        menu_pad.chgat(new_idx, 0, menu_pad.getmaxyx()[1], get_color("settings_sensitive", reverse=True) if options[new_idx] in sensitive_settings else get_color("settings_default", reverse=True))

    menu_win.refresh()
    
    # Refresh pad only if scrolling is needed
    menu_pad.refresh(state.start_index[-1], 0,
                     menu_win.getbegyx()[0] + 3, menu_win.getbegyx()[1] + 4,
                     menu_win.getbegyx()[0] + 3 + visible_height, 
                     menu_win.getbegyx()[1] + menu_win.getmaxyx()[1] - 4)


    draw_arrows(menu_win, visible_height, max_index, state, show_save_option)


def draw_arrows(win, visible_height, max_index, state, show_save_option):

    # vh = visible_height + (1 if show_save_option else 0)
    mi = max_index - (2 if show_save_option else 0) 

    if visible_height < mi:
        if state.start_index[-1] > 0:
            win.addstr(3, 2, "▲", get_color("settings_default"))
        else:
            win.addstr(3, 2, " ", get_color("settings_default"))

        if mi - state.start_index[-1] >= visible_height + (0 if show_save_option else 1) :
            win.addstr(visible_height + 3, 2, "▼", get_color("settings_default"))
        else:
            win.addstr(visible_height + 3, 2, " ", get_color("settings_default"))


def json_editor(stdscr, state):
    
    selected_index = 0  # Track the selected option

    script_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.abspath(os.path.join(script_dir, os.pardir))
    file_path = os.path.join(parent_dir, "config.json")

    show_save_option = True  # Always show the Save button
    menu_index = []

    # Ensure the file exists
    if not os.path.exists(file_path):
        with open(file_path, "w") as f:
            json.dump({}, f)

    # Load JSON data
    with open(file_path, "r") as f:
        original_data = json.load(f)

    data = original_data  # Reference to the original data
    current_menu = data  # Track the current level of the menu

    # Render the menu
    menu_win, menu_pad, options = display_menu(current_menu, selected_index, show_save_option, state)
    need_redraw = True

    while True:
        if(need_redraw):
            menu_win, menu_pad, options = display_menu(current_menu, selected_index, show_save_option, state)
            menu_win.refresh()
            need_redraw = False
            
        max_index = len(options) + (1 if show_save_option else 0) - 1
        key = menu_win.getch()


        if key == curses.KEY_UP:

            old_selected_index = selected_index
            selected_index = max_index if selected_index == 0 else selected_index - 1
            move_highlight(old_selected_index, selected_index, options, show_save_option, menu_win, menu_pad,state)

        elif key == curses.KEY_DOWN:

            old_selected_index = selected_index
            selected_index = 0 if selected_index == max_index else selected_index + 1
            move_highlight(old_selected_index, selected_index, options, show_save_option, menu_win, menu_pad, state)

        elif key == ord("\t") and show_save_option:
            old_selected_index = selected_index
            selected_index = max_index
            move_highlight(old_selected_index, selected_index, options, show_save_option, menu_win, menu_pad, state)

        elif key in (curses.KEY_RIGHT, 10, 13):  # 10 = \n, 13 = carriage return

            need_redraw = True


            menu_win.erase()
            menu_win.refresh()


            if selected_index < len(options):  # Handle selection of a menu item

                selected_key = options[selected_index]
                state.menu_path.append(str(selected_key))
                state.start_index.append(0)
                menu_index.append(selected_index)
                

                # Handle nested data
                if isinstance(current_menu, dict):
                    if selected_key in current_menu:
                        selected_data = current_menu[selected_key]
                    else:
                        continue  # Skip invalid key
                elif isinstance(current_menu, list):
                    selected_data = current_menu[int(selected_key.strip("[]"))]

                if isinstance(selected_data, list) and len(selected_data) == 2:
                    # Edit color pair
                    


                    new_value = edit_color_pair(selected_key, selected_data)
                    state.menu_path.pop()
                    state.start_index.pop()
                    menu_index.pop()
                    current_menu[selected_key] = new_value

                elif isinstance(selected_data, (dict, list)):
                    # Navigate into nested data

                    current_menu = selected_data
                    selected_index = 0  # Reset the selected index

                else:
                    # General value editing

                    new_value = edit_value(selected_key, selected_data, state)
                    state.menu_path.pop()
                    state.start_index.pop()
                    current_menu[selected_key] = new_value
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



            # Navigate back in the menu

            if len(state.menu_path) > 2:
                selected_index = menu_index.pop()
                state.menu_path.pop()
                state.start_index.pop()


                current_menu = data
                for path in state.menu_path[2:]:
                    current_menu = current_menu[path] if isinstance(current_menu, dict) else current_menu[int(path.strip("[]"))]

                


            else:
                # Exit the editor
                menu_win.clear()
                menu_win.refresh()

                break


def save_json(file_path, data):
    formatted_json = format_json_single_line_arrays(data)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(formatted_json)
    setup_colors(reinit=True)

def main(stdscr):
    from contact.ui.ui_state import UIState

    state = UIState()
    if len(state.menu_path) == 0:
        state.menu_path = ["App Settings"]  # Initialize if not set

    curses.curs_set(0)
    stdscr.keypad(True)
    setup_colors()
    json_editor(stdscr, state)

if __name__ == "__main__":
    curses.wrapper(main)