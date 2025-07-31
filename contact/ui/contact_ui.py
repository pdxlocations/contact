import curses
import logging
import time
import traceback
from typing import Union

from contact.utilities.utils import get_channels, get_readable_duration, get_time_ago, refresh_node_list
from contact.settings import settings_menu
from contact.message_handlers.tx_handler import send_message, send_traceroute
from contact.ui.colors import get_color
from contact.utilities.db_handler import get_name_from_database, update_node_info_in_db, is_chat_archived
from contact.utilities.input_handlers import get_list_input
import contact.ui.default_config as config
import contact.ui.dialog
from contact.ui.nav_utils import move_main_highlight, draw_main_arrows, get_msg_window_lines, wrap_text
from contact.utilities.singleton import ui_state, interface_state, menu_state


def handle_resize(stdscr: curses.window, firstrun: bool) -> None:
    """Handle terminal resize events and redraw the UI accordingly."""
    global messages_pad, messages_win, nodes_pad, nodes_win, channel_pad, channel_win, function_win, packetlog_win, entry_win

    # Calculate window max dimensions
    height, width = stdscr.getmaxyx()

    # Define window dimensions and positions
    channel_width = int(config.channel_list_16ths) * (width // 16)
    nodes_width = int(config.node_list_16ths) * (width // 16)
    messages_width = width - channel_width - nodes_width

    entry_height = 3
    function_height = 3
    y_pad = entry_height + function_height
    packet_log_height = int(height / 3)

    if firstrun:
        entry_win = curses.newwin(entry_height, width, 0, 0)
        channel_win = curses.newwin(height - y_pad, channel_width, entry_height, 0)
        messages_win = curses.newwin(height - y_pad, messages_width, entry_height, channel_width)
        nodes_win = curses.newwin(height - y_pad, nodes_width, entry_height, channel_width + messages_width)
        function_win = curses.newwin(function_height, width, height - function_height, 0)
        packetlog_win = curses.newwin(
            packet_log_height, messages_width, height - packet_log_height - function_height, channel_width
        )

        # Will be resized to what we need when drawn
        messages_pad = curses.newpad(1, 1)
        nodes_pad = curses.newpad(1, 1)
        channel_pad = curses.newpad(1, 1)

        # Set background colors for windows
        for win in [entry_win, channel_win, messages_win, nodes_win, function_win, packetlog_win]:
            win.bkgd(get_color("background"))

        # Set background colors for pads
        for pad in [messages_pad, nodes_pad, channel_pad]:
            pad.bkgd(get_color("background"))

        # Set colors for window frames
        for win in [channel_win, entry_win, nodes_win, messages_win, function_win]:
            win.attrset(get_color("window_frame"))

    else:
        for win in [entry_win, channel_win, messages_win, nodes_win, function_win, packetlog_win]:
            win.erase()

        entry_win.resize(3, width)

        channel_win.resize(height - y_pad, channel_width)

        messages_win.resize(height - y_pad, messages_width)
        messages_win.mvwin(3, channel_width)

        nodes_win.resize(height - y_pad, nodes_width)
        nodes_win.mvwin(entry_height, channel_width + messages_width)

        function_win.resize(3, width)
        function_win.mvwin(height - function_height, 0)

        packetlog_win.resize(packet_log_height, messages_width)
        packetlog_win.mvwin(height - packet_log_height - function_height, channel_width)

    # Draw window borders
    for win in [channel_win, entry_win, nodes_win, messages_win, function_win]:
        win.box()
        win.refresh()

    entry_win.keypad(True)
    curses.curs_set(1)

    try:
        draw_function_win()
        draw_channel_list()
        draw_messages_window(True)
        draw_node_list()

    except:
        # Resize events can come faster than we can re-draw, which can cause a curses error.
        # In this case we'll see another curses.KEY_RESIZE in our key handler and draw again later.
        pass


def main_ui(stdscr: curses.window) -> None:
    """Main UI loop for the curses interface."""
    global input_text
    input_text = ""
    stdscr.keypad(True)
    get_channels()
    handle_resize(stdscr, True)

    while True:
        draw_text_field(entry_win, f"Input: {(input_text or '')[-(stdscr.getmaxyx()[1] - 10):]}", get_color("input"))

        # Get user input from entry window
        char = entry_win.get_wch()

        # draw_debug(f"Keypress: {char}")

        if char == curses.KEY_UP:
            handle_up()

        elif char == curses.KEY_DOWN:
            handle_down()

        elif char == curses.KEY_HOME:
            handle_home()

        elif char == curses.KEY_END:
            handle_end()

        elif char == curses.KEY_PPAGE:
            handle_pageup()

        elif char == curses.KEY_NPAGE:
            handle_pagedown()

        elif char == curses.KEY_LEFT or char == curses.KEY_RIGHT:
            handle_leftright(char)

        elif char in (chr(curses.KEY_ENTER), chr(10), chr(13)):
            input_text = handle_enter(input_text)

        elif char == chr(20):  # Ctrl + t for Traceroute
            handle_ctrl_t(stdscr)

        elif char in (curses.KEY_BACKSPACE, chr(127)):
            input_text = handle_backspace(entry_win, input_text)

        elif char == "`":  # ` Launch the settings interface
            handle_backtick(stdscr)

        elif char == chr(16):  # Ctrl + P for Packet Log
            handle_ctrl_p()

        elif char == curses.KEY_RESIZE:
            input_text = ""
            handle_resize(stdscr, False)

        elif char == chr(4):  # Ctrl + D to delete current channel or node
            handle_ctrl_d()

        elif char == chr(31):  # Ctrl + / to search
            handle_ctrl_fslash()

        elif char == chr(6):  # Ctrl + F to toggle favorite
            handle_ctrl_f(stdscr)

        elif char == chr(7):  # Ctrl + G to toggle ignored
            handle_ctlr_g(stdscr)

        elif char == chr(27):  # Escape to exit
            break

        else:
            # Append typed character to input text
            if isinstance(char, str):
                input_text += char
            else:
                input_text += chr(char)


def handle_up() -> None:
    """Handle key up events to scroll the current window."""
    if ui_state.current_window == 0:
        scroll_channels(-1)
    elif ui_state.current_window == 1:
        scroll_messages(-1)
    elif ui_state.current_window == 2:
        scroll_nodes(-1)


def handle_down() -> None:
    """Handle key down events to scroll the current window."""
    if ui_state.current_window == 0:
        scroll_channels(1)
    elif ui_state.current_window == 1:
        scroll_messages(1)
    elif ui_state.current_window == 2:
        scroll_nodes(1)


def handle_home() -> None:
    """Handle home key events to select the first item in the current window."""
    if ui_state.current_window == 0:
        select_channel(0)
    elif ui_state.current_window == 1:
        ui_state.selected_message = 0
        refresh_pad(1)
    elif ui_state.current_window == 2:
        select_node(0)


def handle_end() -> None:
    """Handle end key events to select the last item in the current window."""
    if ui_state.current_window == 0:
        select_channel(len(ui_state.channel_list) - 1)
    elif ui_state.current_window == 1:
        msg_line_count = messages_pad.getmaxyx()[0]
        ui_state.selected_message = max(msg_line_count - get_msg_window_lines(messages_win, packetlog_win), 0)
        refresh_pad(1)
    elif ui_state.current_window == 2:
        select_node(len(ui_state.node_list) - 1)


def handle_pageup() -> None:
    """Handle page up key events to scroll the current window by a page."""
    if ui_state.current_window == 0:
        select_channel(
            ui_state.selected_channel - (channel_win.getmaxyx()[0] - 2)
        )  # select_channel will bounds check for us
    elif ui_state.current_window == 1:
        ui_state.selected_message = max(
            ui_state.selected_message - get_msg_window_lines(messages_win, packetlog_win), 0
        )
        refresh_pad(1)
    elif ui_state.current_window == 2:
        select_node(ui_state.selected_node - (nodes_win.getmaxyx()[0] - 2))  # select_node will bounds check for us


def handle_pagedown() -> None:
    """Handle page down key events to scroll the current window down."""
    if ui_state.current_window == 0:
        select_channel(
            ui_state.selected_channel + (channel_win.getmaxyx()[0] - 2)
        )  # select_channel will bounds check for us
    elif ui_state.current_window == 1:
        msg_line_count = messages_pad.getmaxyx()[0]
        ui_state.selected_message = min(
            ui_state.selected_message + get_msg_window_lines(messages_win, packetlog_win),
            msg_line_count - get_msg_window_lines(messages_win, packetlog_win),
        )
        refresh_pad(1)
    elif ui_state.current_window == 2:
        select_node(ui_state.selected_node + (nodes_win.getmaxyx()[0] - 2))  # select_node will bounds check for us


def handle_leftright(char: int) -> None:
    """Handle left/right key events to switch between windows."""
    delta = -1 if char == curses.KEY_LEFT else 1
    old_window = ui_state.current_window
    ui_state.current_window = (ui_state.current_window + delta) % 3

    if old_window == 0:
        channel_win.attrset(get_color("window_frame"))
        channel_win.box()
        channel_win.refresh()
        refresh_pad(0)
    if old_window == 1:
        messages_win.attrset(get_color("window_frame"))
        messages_win.box()
        messages_win.refresh()
        refresh_pad(1)
    elif old_window == 2:
        draw_function_win()
        nodes_win.attrset(get_color("window_frame"))
        nodes_win.box()
        nodes_win.refresh()
        refresh_pad(2)

    if ui_state.current_window == 0:
        channel_win.attrset(get_color("window_frame_selected"))
        channel_win.box()
        channel_win.attrset(get_color("window_frame"))
        channel_win.refresh()
        refresh_pad(0)
    elif ui_state.current_window == 1:
        messages_win.attrset(get_color("window_frame_selected"))
        messages_win.box()
        messages_win.attrset(get_color("window_frame"))
        messages_win.refresh()
        refresh_pad(1)
    elif ui_state.current_window == 2:
        draw_function_win()
        nodes_win.attrset(get_color("window_frame_selected"))
        nodes_win.box()
        nodes_win.attrset(get_color("window_frame"))
        nodes_win.refresh()
        refresh_pad(2)


def handle_enter(input_text: str) -> str:
    """Handle Enter key events to send messages or select channels."""
    if ui_state.current_window == 2:
        node_list = ui_state.node_list
        if node_list[ui_state.selected_node] not in ui_state.channel_list:
            ui_state.channel_list.append(node_list[ui_state.selected_node])
        if node_list[ui_state.selected_node] not in ui_state.all_messages:
            ui_state.all_messages[node_list[ui_state.selected_node]] = []

        ui_state.selected_channel = ui_state.channel_list.index(node_list[ui_state.selected_node])

        if is_chat_archived(ui_state.channel_list[ui_state.selected_channel]):
            update_node_info_in_db(ui_state.channel_list[ui_state.selected_channel], chat_archived=False)

        ui_state.selected_node = 0
        ui_state.current_window = 0

        draw_node_list()
        draw_channel_list()
        draw_messages_window(True)
        return input_text

    elif len(input_text) > 0:
        # TODO: This is a hack to prevent sending messages too quickly. Let's get errors from the node.
        now = time.monotonic()
        if now - ui_state.last_sent_time < 2.5:
            contact.ui.dialog.dialog("Slow down", "Please wait 2 seconds between messages.")
            return input_text
        # Enter key pressed, send user input as message
        send_message(input_text, channel=ui_state.selected_channel)
        draw_messages_window(True)
        ui_state.last_sent_time = now
        # Clear entry window and reset input text
        entry_win.erase()
        return ""
    return input_text


def handle_ctrl_t(stdscr: curses.window) -> None:
    """Handle Ctrl + T key events to send a traceroute."""
    send_traceroute()
    curses.curs_set(0)  # Hide cursor
    contact.ui.dialog.dialog(
        f"Traceroute Sent To: {get_name_from_database(ui_state.node_list[ui_state.selected_node])}",
        "Results will appear in messages window.\nNote: Traceroute is limited to once every 30 seconds.",
    )
    curses.curs_set(1)  # Show cursor again
    handle_resize(stdscr, False)


def handle_backspace(entry_win: curses.window, input_text: str) -> str:
    """Handle backspace key events to remove the last character from input text."""
    if input_text:
        input_text = input_text[:-1]
        y, x = entry_win.getyx()
        entry_win.move(y, x - 1)
        entry_win.addch(" ")  #
        entry_win.move(y, x - 1)
    entry_win.refresh()
    return input_text


def handle_backtick(stdscr: curses.window) -> None:
    """Handle backtick key events to open the settings menu."""
    curses.curs_set(0)
    previous_window = ui_state.current_window
    ui_state.current_window = 4
    settings_menu(stdscr, interface_state.interface)
    ui_state.current_window = previous_window
    curses.curs_set(1)
    refresh_node_list()
    handle_resize(stdscr, False)


def handle_ctrl_p() -> None:
    """Handle Ctrl + P key events to toggle the packet log display."""
    # Display packet log
    if ui_state.display_log is False:
        ui_state.display_log = True
        draw_messages_window(True)
    else:
        ui_state.display_log = False
        packetlog_win.erase()
        draw_messages_window(True)


def handle_ctrl_d() -> None:
    if ui_state.current_window == 0:
        if isinstance(ui_state.channel_list[ui_state.selected_channel], int):
            update_node_info_in_db(ui_state.channel_list[ui_state.selected_channel], chat_archived=True)

            # Shift notifications up to account for deleted item
            for i in range(len(ui_state.notifications)):
                if ui_state.notifications[i] > ui_state.selected_channel:
                    ui_state.notifications[i] -= 1

            del ui_state.channel_list[ui_state.selected_channel]
            ui_state.selected_channel = min(ui_state.selected_channel, len(ui_state.channel_list) - 1)
            select_channel(ui_state.selected_channel)
            draw_channel_list()
            draw_messages_window()

    if ui_state.current_window == 2:
        curses.curs_set(0)
        confirmation = get_list_input(
            f"Remove {get_name_from_database(ui_state.node_list[ui_state.selected_node])} from nodedb?",
            "No",
            ["Yes", "No"],
        )
        if confirmation == "Yes":
            interface_state.interface.localNode.removeNode(ui_state.node_list[ui_state.selected_node])

            # Directly modifying the interface from client code - good? Bad? If it's stupid but it works, it's not supid?
            del interface_state.interface.nodesByNum[ui_state.node_list[ui_state.selected_node]]

            # Convert to "!hex" representation that interface.nodes uses
            hexid = f"!{hex(ui_state.node_list[ui_state.selected_node])[2:]}"
            del interface_state.interface.nodes[hexid]

            ui_state.node_list.pop(ui_state.selected_node)

            draw_messages_window()
            draw_node_list()
        else:
            draw_messages_window()
        curses.curs_set(1)


def handle_ctrl_fslash() -> None:
    """Handle Ctrl + / key events to search in the current window."""
    if ui_state.current_window == 2 or ui_state.current_window == 0:
        search(ui_state.current_window)


def handle_ctrl_f(stdscr: curses.window) -> None:
    """Handle Ctrl + F key events to toggle favorite status of the selected node."""
    if ui_state.current_window == 2:
        selectedNode = interface_state.interface.nodesByNum[ui_state.node_list[ui_state.selected_node]]

        curses.curs_set(0)

        if "isFavorite" not in selectedNode or selectedNode["isFavorite"] == False:
            confirmation = get_list_input(
                f"Set {get_name_from_database(ui_state.node_list[ui_state.selected_node])} as Favorite?",
                None,
                ["Yes", "No"],
            )
            if confirmation == "Yes":
                interface_state.interface.localNode.setFavorite(ui_state.node_list[ui_state.selected_node])
                # Maybe we shouldn't be modifying the nodedb, but maybe it should update itself
                interface_state.interface.nodesByNum[ui_state.node_list[ui_state.selected_node]]["isFavorite"] = True

                refresh_node_list()

        else:
            confirmation = get_list_input(
                f"Remove {get_name_from_database(ui_state.node_list[ui_state.selected_node])} from Favorites?",
                None,
                ["Yes", "No"],
            )
            if confirmation == "Yes":
                interface_state.interface.localNode.removeFavorite(ui_state.node_list[ui_state.selected_node])
                # Maybe we shouldn't be modifying the nodedb, but maybe it should update itself
                interface_state.interface.nodesByNum[ui_state.node_list[ui_state.selected_node]]["isFavorite"] = False

                refresh_node_list()

        handle_resize(stdscr, False)


def handle_ctlr_g(stdscr: curses.window) -> None:
    """Handle Ctrl + G key events to toggle ignored status of the selected node."""
    if ui_state.current_window == 2:
        selectedNode = interface_state.interface.nodesByNum[ui_state.node_list[ui_state.selected_node]]

        curses.curs_set(0)

        if "isIgnored" not in selectedNode or selectedNode["isIgnored"] == False:
            confirmation = get_list_input(
                f"Set {get_name_from_database(ui_state.node_list[ui_state.selected_node])} as Ignored?",
                "No",
                ["Yes", "No"],
            )
            if confirmation == "Yes":
                interface_state.interface.localNode.setIgnored(ui_state.node_list[ui_state.selected_node])
                interface_state.interface.nodesByNum[ui_state.node_list[ui_state.selected_node]]["isIgnored"] = True
        else:
            confirmation = get_list_input(
                f"Remove {get_name_from_database(ui_state.node_list[ui_state.selected_node])} from Ignored?",
                "No",
                ["Yes", "No"],
            )
            if confirmation == "Yes":
                interface_state.interface.localNode.removeIgnored(ui_state.node_list[ui_state.selected_node])
                interface_state.interface.nodesByNum[ui_state.node_list[ui_state.selected_node]]["isIgnored"] = False

        handle_resize(stdscr, False)


def draw_channel_list() -> None:
    """Update the channel list window and pad based on the current state."""
    channel_pad.erase()
    win_width = channel_win.getmaxyx()[1]

    channel_pad.resize(len(ui_state.all_messages), channel_win.getmaxyx()[1])

    idx = 0
    for channel in ui_state.channel_list:
        # Convert node number to long name if it's an integer
        if isinstance(channel, int):
            if is_chat_archived(channel):
                continue
            channel_name = get_name_from_database(channel, type="long")
            if channel_name is None:
                continue
            channel = channel_name

        # Determine whether to add the notification
        notification = " " + config.notification_symbol if idx in ui_state.notifications else ""

        # Truncate the channel name if it's too long to fit in the window
        truncated_channel = (
            (channel[: win_width - 5] + "-" if len(channel) > win_width - 5 else channel) + notification
        ).ljust(win_width - 3)

        color = get_color("channel_list")
        if idx == ui_state.selected_channel:
            if ui_state.current_window == 0:
                color = get_color("channel_list", reverse=True)
                remove_notification(ui_state.selected_channel)
            else:
                color = get_color("channel_selected")
        channel_pad.addstr(idx, 1, truncated_channel, color)
        idx += 1

    channel_win.attrset(
        get_color("window_frame_selected") if ui_state.current_window == 0 else get_color("window_frame")
    )
    channel_win.box()
    channel_win.attrset((get_color("window_frame")))

    draw_main_arrows(channel_win, len(ui_state.channel_list), window=0)
    channel_win.refresh()

    refresh_pad(0)


def draw_messages_window(scroll_to_bottom: bool = False) -> None:
    """Update the messages window based on the selected channel and scroll position."""
    messages_pad.erase()

    channel = ui_state.channel_list[ui_state.selected_channel]

    if channel in ui_state.all_messages:
        messages = ui_state.all_messages[channel]

        msg_line_count = 0

        row = 0
        for prefix, message in messages:
            full_message = f"{prefix}{message}"
            wrapped_lines = wrap_text(full_message, messages_win.getmaxyx()[1] - 2)
            msg_line_count += len(wrapped_lines)
            messages_pad.resize(msg_line_count, messages_win.getmaxyx()[1])

            for line in wrapped_lines:
                if prefix.startswith("--"):
                    color = get_color("timestamps")
                elif prefix.startswith(config.sent_message_prefix):
                    color = get_color("tx_messages")
                else:
                    color = get_color("rx_messages")

                messages_pad.addstr(row, 1, line, color)
                row += 1

    messages_win.attrset(
        get_color("window_frame_selected") if ui_state.current_window == 1 else get_color("window_frame")
    )
    messages_win.box()
    messages_win.attrset(get_color("window_frame"))
    messages_win.refresh()

    visible_lines = get_msg_window_lines(messages_win, packetlog_win)

    if scroll_to_bottom:
        ui_state.selected_message = max(msg_line_count - visible_lines, 0)
        ui_state.start_index[1] = max(msg_line_count - visible_lines, 0)
        pass
    else:
        ui_state.selected_message = max(min(ui_state.selected_message, msg_line_count - visible_lines), 0)

    draw_main_arrows(
        messages_win,
        msg_line_count,
        window=1,
        log_height=packetlog_win.getmaxyx()[0],
    )
    messages_win.refresh()

    refresh_pad(1)

    draw_packetlog_win()
    if ui_state.current_window == 4:
        menu_state.need_redraw = True


def draw_node_list() -> None:
    """Update the nodes list window and pad based on the current state."""
    global nodes_pad

    # This didn't work, for some reason an error is thown on startup, so we just create the pad every time
    # if nodes_pad is None:
    # nodes_pad = curses.newpad(1, 1)
    nodes_pad = curses.newpad(1, 1)

    try:
        nodes_pad.erase()
        box_width = nodes_win.getmaxyx()[1]
        nodes_pad.resize(len(ui_state.node_list) + 1, box_width)
    except Exception as e:
        logging.error(f"Error Drawing Nodes List: {e}")
        logging.error("Traceback: %s", traceback.format_exc())

    for i, node_num in enumerate(ui_state.node_list):
        node = interface_state.interface.nodesByNum[node_num]
        secure = "user" in node and "publicKey" in node["user"] and node["user"]["publicKey"]
        node_str = f"{'🔐' if secure else '🔓'} {get_name_from_database(node_num, 'long')}".ljust(box_width - 2)[
            : box_width - 2
        ]
        color = "node_list"
        if "isFavorite" in node and node["isFavorite"]:
            color = "node_favorite"
        if "isIgnored" in node and node["isIgnored"]:
            color = "node_ignored"
        nodes_pad.addstr(
            i, 1, node_str, get_color(color, reverse=ui_state.selected_node == i and ui_state.current_window == 2)
        )

    nodes_win.attrset(
        get_color("window_frame_selected") if ui_state.current_window == 2 else get_color("window_frame")
    )
    nodes_win.box()
    nodes_win.attrset(get_color("window_frame"))

    draw_main_arrows(nodes_win, len(ui_state.node_list), window=2)
    nodes_win.refresh()

    refresh_pad(2)

    # Restore cursor to input field
    entry_win.keypad(True)
    curses.curs_set(1)
    entry_win.refresh()


def select_channel(idx: int) -> None:
    """Select a channel by index and update the UI state accordingly."""
    old_selected_channel = ui_state.selected_channel
    ui_state.selected_channel = max(0, min(idx, len(ui_state.channel_list) - 1))
    draw_messages_window(True)

    # For now just re-draw channel list when clearing notifications, we can probably make this more efficient
    if ui_state.selected_channel in ui_state.notifications:
        remove_notification(ui_state.selected_channel)
        draw_channel_list()
        return

    move_main_highlight(
        old_idx=old_selected_channel,
        new_idx=ui_state.selected_channel,
        options=ui_state.channel_list,
        menu_win=channel_win,
        menu_pad=channel_pad,
        ui_state=ui_state,
    )


def scroll_channels(direction: int) -> None:
    """Scroll through the channel list by a given direction."""
    new_selected_channel = ui_state.selected_channel + direction

    if new_selected_channel < 0:
        new_selected_channel = len(ui_state.channel_list) - 1
    elif new_selected_channel >= len(ui_state.channel_list):
        new_selected_channel = 0

    select_channel(new_selected_channel)


def scroll_messages(direction: int) -> None:
    """Scroll through the messages in the current channel by a given direction."""
    ui_state.selected_message += direction

    msg_line_count = messages_pad.getmaxyx()[0]
    ui_state.selected_message = max(
        0, min(ui_state.selected_message, msg_line_count - get_msg_window_lines(messages_win, packetlog_win))
    )

    max_index = msg_line_count - 1
    visible_height = get_msg_window_lines(messages_win, packetlog_win)

    if ui_state.selected_message < ui_state.start_index[ui_state.current_window]:  # Moving above the visible area
        ui_state.start_index[ui_state.current_window] = ui_state.selected_message
    elif ui_state.selected_message >= ui_state.start_index[ui_state.current_window]:  # Moving below the visible area
        ui_state.start_index[ui_state.current_window] = ui_state.selected_message

    # Ensure start_index is within bounds
    ui_state.start_index[ui_state.current_window] = max(
        0, min(ui_state.start_index[ui_state.current_window], max_index - visible_height + 1)
    )

    draw_main_arrows(
        messages_win,
        msg_line_count,
        ui_state.current_window,
        log_height=packetlog_win.getmaxyx()[0],
    )
    messages_win.refresh()

    refresh_pad(1)


def select_node(idx: int) -> None:
    """Select a node by index and update the UI state accordingly."""
    old_selected_node = ui_state.selected_node
    ui_state.selected_node = max(0, min(idx, len(ui_state.node_list) - 1))

    move_main_highlight(
        old_idx=old_selected_node,
        new_idx=ui_state.selected_node,
        options=ui_state.node_list,
        menu_win=nodes_win,
        menu_pad=nodes_pad,
        ui_state=ui_state,
    )

    draw_function_win()


def scroll_nodes(direction: int) -> None:
    """Scroll through the node list by a given direction."""
    new_selected_node = ui_state.selected_node + direction

    if new_selected_node < 0:
        new_selected_node = len(ui_state.node_list) - 1
    elif new_selected_node >= len(ui_state.node_list):
        new_selected_node = 0

    select_node(new_selected_node)


def draw_packetlog_win() -> None:
    """Draw the packet log window with the latest packets."""
    columns = [10, 10, 15, 30]
    span = 0

    if ui_state.display_log:
        packetlog_win.erase()
        height, width = packetlog_win.getmaxyx()

        for column in columns[:-1]:
            span += column

        # Add headers
        headers = f"{'From':<{columns[0]}} {'To':<{columns[1]}} {'Port':<{columns[2]}} {'Payload':<{width-span}}"
        packetlog_win.addstr(
            1, 1, headers[: width - 2], get_color("log_header", underline=True)
        )  # Truncate headers if they exceed window width

        for i, packet in enumerate(reversed(ui_state.packet_buffer)):
            if i >= height - 3:  # Skip if exceeds the window height
                break

            # Format each field
            from_id = get_name_from_database(packet["from"], "short").ljust(columns[0])
            to_id = (
                "BROADCAST".ljust(columns[1])
                if str(packet["to"]) == "4294967295"
                else get_name_from_database(packet["to"], "short").ljust(columns[1])
            )
            if "decoded" in packet:
                port = packet["decoded"]["portnum"].ljust(columns[2])
                payload = (packet["decoded"]["payload"]).ljust(columns[3])
            else:
                port = "NO KEY".ljust(columns[2])
                payload = "NO KEY".ljust(columns[3])

            # Combine and truncate if necessary
            logString = f"{from_id} {to_id} {port} {payload}"
            logString = logString[: width - 3]

            # Add to the window
            packetlog_win.addstr(i + 2, 1, logString, get_color("log"))

        packetlog_win.attrset(get_color("window_frame"))
        packetlog_win.box()
        packetlog_win.refresh()

    # Restore cursor to input field
    entry_win.keypad(True)
    curses.curs_set(1)
    entry_win.refresh()


def search(win: int) -> None:
    """Search for a node or channel based on user input."""
    start_idx = ui_state.selected_node
    select_func = select_node

    if win == 0:
        start_idx = ui_state.selected_channel
        select_func = select_channel

    search_text = ""
    entry_win.erase()

    while True:
        draw_centered_text_field(entry_win, f"Search: {search_text}", 0, get_color("input"))
        char = entry_win.get_wch()

        if char in (chr(27), chr(curses.KEY_ENTER), chr(10), chr(13)):
            break
        elif char == "\t":
            start_idx = ui_state.selected_node + 1 if win == 2 else ui_state.selected_channel + 1
        elif char in (curses.KEY_BACKSPACE, chr(127)):
            if search_text:
                search_text = search_text[:-1]
                y, x = entry_win.getyx()
                entry_win.move(y, x - 1)
                entry_win.addch(" ")  #
                entry_win.move(y, x - 1)
                entry_win.erase()
                entry_win.refresh()
        elif isinstance(char, str):
            search_text += char

        search_text_caseless = search_text.casefold()

        l = ui_state.node_list if win == 2 else ui_state.channel_list
        for i, n in enumerate(l[start_idx:] + l[:start_idx]):
            if (
                isinstance(n, int)
                and search_text_caseless in get_name_from_database(n, "long").casefold()
                or isinstance(n, int)
                and search_text_caseless in get_name_from_database(n, "short").casefold()
                or search_text_caseless in str(n).casefold()
            ):
                select_func((i + start_idx) % len(l))
                break

    entry_win.erase()


def draw_node_details() -> None:
    """Draw the details of the selected node in the function window."""
    node = None
    try:
        node = interface_state.interface.nodesByNum[ui_state.node_list[ui_state.selected_node]]
    except KeyError:
        return

    function_win.erase()
    function_win.box()

    nodestr = ""
    width = function_win.getmaxyx()[1]

    node_details_list = [
        f"{node['user']['longName']} " if "user" in node and "longName" in node["user"] else "",
        f"({node['user']['shortName']})" if "user" in node and "shortName" in node["user"] else "",
        f" | {node['user']['hwModel']}" if "user" in node and "hwModel" in node["user"] else "",
        f" | {node['user']['role']}" if "user" in node and "role" in node["user"] else "",
    ]

    if ui_state.node_list[ui_state.selected_node] == interface_state.myNodeNum:
        node_details_list.extend(
            [
                (
                    f" | Bat: {node['deviceMetrics']['batteryLevel']}% ({node['deviceMetrics']['voltage']}v)"
                    if "deviceMetrics" in node
                    and "batteryLevel" in node["deviceMetrics"]
                    and "voltage" in node["deviceMetrics"]
                    else ""
                ),
                (
                    f" | Up: {get_readable_duration(node['deviceMetrics']['uptimeSeconds'])}"
                    if "deviceMetrics" in node and "uptimeSeconds" in node["deviceMetrics"]
                    else ""
                ),
                (
                    f" | ChUtil: {node['deviceMetrics']['channelUtilization']:.2f}%"
                    if "deviceMetrics" in node and "channelUtilization" in node["deviceMetrics"]
                    else ""
                ),
                (
                    f" | AirUtilTX: {node['deviceMetrics']['airUtilTx']:.2f}%"
                    if "deviceMetrics" in node and "airUtilTx" in node["deviceMetrics"]
                    else ""
                ),
            ]
        )
    else:
        node_details_list.extend(
            [
                f" | {get_time_ago(node['lastHeard'])}" if ("lastHeard" in node and node["lastHeard"]) else "",
                f" | Hops: {node['hopsAway']}" if "hopsAway" in node else "",
                f" | SNR: {node['snr']}dB" if ("snr" in node and "hopsAway" in node and node["hopsAway"] == 0) else "",
            ]
        )

    for s in node_details_list:
        if len(nodestr) + len(s) < width - 2:
            nodestr = nodestr + s

    draw_centered_text_field(function_win, nodestr, 0, get_color("commands"))


def draw_help() -> None:
    """Draw the help text in the function window."""
    cmds = [
        "↑→↓← = Select",
        "   ENTER = Send",
        "   ` = Settings",
        "   ESC = Quit",
        "   ^P = Packet Log",
        "   ^t = Traceroute",
        "   ^d = Archive Chat",
        "   ^f = Favorite",
        "   ^g = Ignore",
        "   ^/ = Search",
    ]
    function_str = ""
    for s in cmds:
        if len(function_str) + len(s) < function_win.getmaxyx()[1] - 2:
            function_str += s

    draw_centered_text_field(function_win, function_str, 0, get_color("commands"))


def draw_function_win() -> None:
    if ui_state.current_window == 2:
        draw_node_details()
    else:
        draw_help()


def refresh_pad(window: int) -> None:

    win_height = channel_win.getmaxyx()[0]

    if window == 1:
        pad = messages_pad
        box = messages_win
        lines = get_msg_window_lines(messages_win, packetlog_win)
        selected_item = ui_state.selected_message
        start_index = ui_state.selected_message

        if ui_state.display_log:
            packetlog_win.box()
            packetlog_win.refresh()

    elif window == 2:
        pad = nodes_pad
        box = nodes_win
        lines = box.getmaxyx()[0] - 2
        selected_item = ui_state.selected_node
        start_index = max(0, selected_item - (win_height - 3))  # Leave room for borders

    else:
        pad = channel_pad
        box = channel_win
        lines = box.getmaxyx()[0] - 2
        selected_item = ui_state.selected_channel
        start_index = max(0, selected_item - (win_height - 3))  # Leave room for borders

    pad.refresh(
        start_index,
        0,
        box.getbegyx()[0] + 1,
        box.getbegyx()[1] + 1,
        box.getbegyx()[0] + lines,
        box.getbegyx()[1] + box.getmaxyx()[1] - 3,
    )


def add_notification(channel_number: int) -> None:
    if channel_number not in ui_state.notifications:
        ui_state.notifications.append(channel_number)


def remove_notification(channel_number: int) -> None:
    if channel_number in ui_state.notifications:
        ui_state.notifications.remove(channel_number)


def draw_text_field(win: curses.window, text: str, color: int) -> None:
    win.border()
    win.addstr(1, 1, text, color)


def draw_centered_text_field(win: curses.window, text: str, y_offset: int, color: int) -> None:
    height, width = win.getmaxyx()
    x = (width - len(text)) // 2
    y = (height // 2) + y_offset
    win.addstr(y, x, text, color)
    win.refresh()


def draw_debug(value: Union[str, int]) -> None:
    function_win.addstr(1, 1, f"debug: {value}    ")
    function_win.refresh()
