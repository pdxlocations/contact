import curses
import ipaddress

def get_user_input(prompt):
    # Calculate the dynamic height and width for the input window
    height = 7  # Fixed height for input prompt
    width = 60
    start_y = (curses.LINES - height) // 2
    start_x = (curses.COLS - width) // 2

    # Create a new window for user input
    input_win = curses.newwin(height, width, start_y, start_x)
    input_win.clear()
    input_win.border()

    # Display the prompt
    input_win.addstr(1, 2, prompt, curses.A_BOLD)
    input_win.addstr(3, 2, "Enter value: ")
    input_win.refresh()

    # Enable user input
    curses.echo()
    curses.curs_set(1)

    user_input = ""
    while True:
        key = input_win.getch(3, 15 + len(user_input))  # Adjust cursor position dynamically
        if key == 27 or key == curses.KEY_LEFT:  # ESC or Left Arrow
            curses.noecho()
            curses.curs_set(0)
            return None  # Exit without returning a value
        elif key == ord('\n'):  # Enter key
            break
        elif key == curses.KEY_BACKSPACE or key == 127:  # Backspace
            user_input = user_input[:-1]
            input_win.addstr(3, 15, " " * (len(user_input) + 1))  # Clear the line
            input_win.addstr(3, 15, user_input)
        else:
            user_input += chr(key)
            input_win.addstr(3, 15, user_input)

    curses.curs_set(0)
    curses.noecho()

    # Clear the input window
    input_win.clear()
    input_win.refresh()
    return user_input

def get_bool_selection(message, current_value):
    message = "Select True or False:" if None else message
    cvalue = current_value
    options = ["True", "False"]
    selected_index = 0 if current_value == "True" else 1

    height = 7
    width = 60
    start_y = (curses.LINES - height) // 2
    start_x = (curses.COLS - width) // 2

    bool_win = curses.newwin(height, width, start_y, start_x)
    bool_win.keypad(True)

    while True:
        bool_win.clear()
        bool_win.border()
        bool_win.addstr(1, 2, message, curses.A_BOLD)

        for idx, option in enumerate(options):
            if idx == selected_index:
                bool_win.addstr(idx + 3, 4, option, curses.A_REVERSE)
            else:
                bool_win.addstr(idx + 3, 4, option)

        bool_win.refresh()
        key = bool_win.getch()

        if key == curses.KEY_UP:
            selected_index = max(0, selected_index - 1)
        elif key == curses.KEY_DOWN:
            selected_index = min(len(options) - 1, selected_index + 1)
        elif key == ord('\n'):  # Enter key
            return options[selected_index]
        elif key == 27 or key == curses.KEY_LEFT:  # ESC or Left Arrow
            return cvalue

def get_repeated_input(current_value):
    cvalue = current_value
    height = 10
    width = 60
    start_y = (curses.LINES - height) // 2
    start_x = (curses.COLS - width) // 2

    repeated_win = curses.newwin(height, width, start_y, start_x)
    repeated_win.keypad(True)  # Enable keypad for special keys

    curses.echo()
    curses.curs_set(1)
    user_input = ""

    while True:
        repeated_win.clear()
        repeated_win.border()
        repeated_win.addstr(1, 2, "Enter comma-separated values:", curses.A_BOLD)
        repeated_win.addstr(3, 2, f"Current: {', '.join(current_value)}")
        repeated_win.addstr(5, 2, f"New value: {user_input}")
        repeated_win.refresh()

        key = repeated_win.getch()

        if key == 27 or key == curses.KEY_LEFT:  # Escape or Left Arrow
            curses.noecho()
            curses.curs_set(0)
            return cvalue  # Return the current value without changes
        elif key == ord('\n'):  # Enter key to save and return
            curses.noecho()
            curses.curs_set(0)
            return user_input.split(",")  # Split the input into a list
        elif key == curses.KEY_BACKSPACE or key == 127:  # Backspace key
            user_input = user_input[:-1]
        else:
            try:
                user_input += chr(key)  # Append valid character input
            except ValueError:
                pass  # Ignore invalid character inputs

def get_enum_input(options, current_value):
    selected_index = options.index(current_value) if current_value in options else 0

    height = min(len(options) + 4, curses.LINES - 2)
    width = 60
    start_y = (curses.LINES - height) // 2
    start_x = (curses.COLS - width) // 2

    enum_win = curses.newwin(height, width, start_y, start_x)
    enum_win.keypad(True)

    while True:
        enum_win.clear()
        enum_win.border()
        enum_win.addstr(1, 2, "Select an option:", curses.A_BOLD)

        for idx, option in enumerate(options):
            if idx == selected_index:
                enum_win.addstr(idx + 2, 4, option, curses.A_REVERSE)
            else:
                enum_win.addstr(idx + 2, 4, option)

        enum_win.refresh()
        key = enum_win.getch()

        if key == curses.KEY_UP:
            selected_index = max(0, selected_index - 1)
        elif key == curses.KEY_DOWN:
            selected_index = min(len(options) - 1, selected_index + 1)
        elif key == ord('\n'):  # Enter key
            return options[selected_index]
        elif key == 27 or key == curses.KEY_LEFT:  # ESC or Left Arrow
            return current_value
        

def get_fixed32_input(current_value):
    cvalue = current_value
    current_value = str(ipaddress.IPv4Address(current_value))
    height = 10
    width = 60
    start_y = (curses.LINES - height) // 2
    start_x = (curses.COLS - width) // 2

    fixed32_win = curses.newwin(height, width, start_y, start_x)
    fixed32_win.keypad(True)

    curses.echo()
    curses.curs_set(1)
    user_input = ""

    while True:
        fixed32_win.clear()
        fixed32_win.border()
        fixed32_win.addstr(1, 2, "Enter an IP address (xxx.xxx.xxx.xxx):", curses.A_BOLD)
        fixed32_win.addstr(3, 2, f"Current: {current_value}")
        fixed32_win.addstr(5, 2, f"New value: {user_input}")
        fixed32_win.refresh()

        key = fixed32_win.getch()

        if key == 27 or key == curses.KEY_LEFT:  # Escape or Left Arrow to cancel
            curses.noecho()
            curses.curs_set(0)
            return cvalue  # Return the current value unchanged
        elif key == ord('\n'):  # Enter key to validate and save
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