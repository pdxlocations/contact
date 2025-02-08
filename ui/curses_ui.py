import curses
import textwrap
import logging
import traceback
from utilities.utils import get_channels, get_readable_duration, get_time_ago, refresh_node_list
from settings import settings_menu
from message_handlers.tx_handler import send_message, send_traceroute
from ui.colors import setup_colors, get_color
from db_handler import get_name_from_database, update_node_info_in_db, is_chat_archived
import default_config as config
import ui.dialog
import globals

def handle_resize(stdscr, firstrun):
    global messages_pad, messages_win, nodes_pad, nodes_win, channel_pad, channel_win, function_win, packetlog_win, entry_win

    # Calculate window max dimensions
    height, width = stdscr.getmaxyx()

    # Define window dimensions and positions
    channel_width = 3 * (width // 16)
    nodes_width = 5 * (width // 16)
    messages_width = width - channel_width - nodes_width

    if firstrun:
        entry_win = curses.newwin(3, width, 0, 0)
        channel_win = curses.newwin(height - 6, channel_width, 3, 0)
        messages_win = curses.newwin(height - 6, messages_width, 3, channel_width)
        nodes_win = curses.newwin(height - 6, nodes_width, 3, channel_width + messages_width)
        function_win = curses.newwin(3, width, height - 3, 0)
        packetlog_win = curses.newwin(int(height / 3), messages_width, height - int(height / 3) - 3, channel_width)

        # Will be resized to what we need when drawn
        messages_pad = curses.newpad(1,1)
        nodes_pad = curses.newpad(1,1)
        channel_pad = curses.newpad(1,1)

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
        # Ensure all windows are initialized before using them
        if entry_win is None:
            entry_win = curses.newwin(3, width, 0, 0)
        if channel_win is None:
            channel_win = curses.newwin(height - 6, channel_width, 3, 0)
        if messages_win is None:
            messages_win = curses.newwin(height - 6, messages_width, 3, channel_width)
        if nodes_win is None:
            nodes_win = curses.newwin(height - 6, nodes_width, 3, channel_width + messages_width)
        if function_win is None:
            function_win = curses.newwin(3, width, height - 3, 0)
        if packetlog_win is None:
            packetlog_win = curses.newwin(int(height / 3), messages_width, height - int(height / 3) - 3, channel_width)

        # Ensure pads are initialized
        if messages_pad is None:
            messages_pad = curses.newpad(1,1)
        if nodes_pad is None:
            nodes_pad = curses.newpad(1,1)
        if channel_pad is None:
            channel_pad = curses.newpad(1,1)


        for win in [entry_win, channel_win, messages_win, nodes_win, function_win, packetlog_win]:
            win.erase()

        entry_win.resize(3, width)
        channel_win.resize(height - 6, channel_width)
        messages_win.resize(height - 6, messages_width)
        messages_win.mvwin(3, channel_width)
        nodes_win.resize(height - 6, nodes_width)
        nodes_win.mvwin(3, channel_width + messages_width)
        function_win.resize(3, width)
        function_win.mvwin(height - 3, 0)
        packetlog_win.resize(int(height / 3), messages_width)
        packetlog_win.mvwin(height - int(height / 3) - 3, channel_width)


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


def main_ui(stdscr):

    stdscr.keypad(True)
    get_channels()
    
    handle_resize(stdscr, True)

    input_text = ""
    while True:
        draw_text_field(entry_win, f"Input: {input_text[-(stdscr.getmaxyx()[1] - 10):]}", get_color("input"))

        # Get user input from entry window
        char = entry_win.get_wch()

        # draw_debug(f"Keypress: {char}")

        if char == curses.KEY_UP:
            if globals.current_window == 0:
                scroll_channels(-1)
            elif globals.current_window == 1:
                scroll_messages(-1)
            elif globals.current_window == 2:
                scroll_nodes(-1)

        elif char == curses.KEY_DOWN:
            if globals.current_window == 0:
                scroll_channels(1)
            elif globals.current_window == 1:
                scroll_messages(1)
            elif globals.current_window == 2:
                scroll_nodes(1)

        elif char == curses.KEY_HOME:
            if globals.current_window == 0:
                select_channel(0)
            elif globals.current_window == 1:
                globals.selected_message = 0
                refresh_pad(1)
            elif globals.current_window == 2:
                select_node(0)

        elif char == curses.KEY_END:
            if globals.current_window == 0:
                select_channel(len(globals.channel_list) - 1)
            elif globals.current_window == 1:
                msg_line_count = messages_pad.getmaxyx()[0]
                globals.selected_message = max(msg_line_count - get_msg_window_lines(), 0)
                refresh_pad(1)
            elif globals.current_window == 2:
                select_node(len(globals.node_list) - 1)

        elif char == curses.KEY_PPAGE:
            if globals.current_window == 0:
                select_channel(globals.selected_channel - (channel_win.getmaxyx()[0] - 2)) # select_channel will bounds check for us
            elif globals.current_window == 1:
                globals.selected_message = max(globals.selected_message - get_msg_window_lines(), 0)
                refresh_pad(1)
            elif globals.current_window == 2:
                select_node(globals.selected_node - (nodes_win.getmaxyx()[0] - 2)) # select_node will bounds check for us

        elif char == curses.KEY_NPAGE:
            if globals.current_window == 0:
                select_channel(globals.selected_channel + (channel_win.getmaxyx()[0] - 2)) # select_channel will bounds check for us
            elif globals.current_window == 1:
                msg_line_count = messages_pad.getmaxyx()[0]
                globals.selected_message = min(globals.selected_message + get_msg_window_lines(), msg_line_count - get_msg_window_lines())
                refresh_pad(1)
            elif globals.current_window == 2:
                select_node(globals.selected_node + (nodes_win.getmaxyx()[0] - 2)) # select_node will bounds check for us

        elif char == curses.KEY_LEFT or char == curses.KEY_RIGHT:
            delta = -1 if char == curses.KEY_LEFT else 1

            old_window = globals.current_window
            globals.current_window = (globals.current_window + delta) % 3

            if old_window == 0:
                channel_win.attrset(get_color("window_frame"))
                channel_win.box()
                channel_win.refresh()
                highlight_line(False, 0, globals.selected_channel)
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
                highlight_line(False, 2, globals.selected_node)
                refresh_pad(2)

            if globals.current_window == 0:
                channel_win.attrset(get_color("window_frame_selected"))
                channel_win.box()
                channel_win.attrset(get_color("window_frame"))
                channel_win.refresh()
                highlight_line(True, 0, globals.selected_channel)
                refresh_pad(0)
            elif globals.current_window == 1:
                messages_win.attrset(get_color("window_frame_selected"))
                messages_win.box()
                messages_win.attrset(get_color("window_frame"))
                messages_win.refresh()
                refresh_pad(1)
            elif globals.current_window == 2:
                draw_function_win()
                nodes_win.attrset(get_color("window_frame_selected"))
                nodes_win.box()
                nodes_win.attrset(get_color("window_frame"))
                nodes_win.refresh()
                highlight_line(True, 2, globals.selected_node)
                refresh_pad(2)

        # Check for Esc
        elif char == chr(27):
            break

        # Check for Ctrl + t
        elif char == chr(20):
            send_traceroute()
            curses.curs_set(0)  # Hide cursor
            ui.dialog.dialog(stdscr, "Traceroute Sent", "Results will appear in messages window.\nNote: Traceroute is limited to once every 30 seconds.")
            curses.curs_set(1)  # Show cursor again
            handle_resize(stdscr, False)

        elif char in (chr(curses.KEY_ENTER), chr(10), chr(13)):
            if globals.current_window == 2:
                node_list = globals.node_list
                if node_list[globals.selected_node] not in globals.channel_list:
                    globals.channel_list.append(node_list[globals.selected_node])
                if(node_list[globals.selected_node] not in globals.all_messages):
                    globals.all_messages[node_list[globals.selected_node]] = []


                globals.selected_channel = globals.channel_list.index(node_list[globals.selected_node])

                if(is_chat_archived(globals.channel_list[globals.selected_channel])):
                    update_node_info_in_db(globals.channel_list[globals.selected_channel], chat_archived=False)

                globals.selected_node = 0
                globals.current_window = 0

                draw_node_list()
                draw_channel_list()
                draw_messages_window(True)

            elif len(input_text) > 0:
                # Enter key pressed, send user input as message
                send_message(input_text, channel=globals.selected_channel)
                draw_messages_window(True)

                # Clear entry window and reset input text
                input_text = ""
                entry_win.erase()

        elif char in (curses.KEY_BACKSPACE, chr(127)):
            if input_text:
                input_text = input_text[:-1]
                y, x = entry_win.getyx()
                entry_win.move(y, x - 1)
                entry_win.addch(' ')  #
                entry_win.move(y, x - 1)
            entry_win.refresh()
            
        elif char == "`": # ` Launch the settings interface
            curses.curs_set(0)
            settings_menu(stdscr, globals.interface)
            curses.curs_set(1)
            refresh_node_list()
            handle_resize(stdscr, False)
        
        elif char == chr(16):
            # Display packet log
            if globals.display_log is False:
                globals.display_log = True
                draw_messages_window(True)
            else:
                globals.display_log = False
                packetlog_win.erase()
                draw_messages_window(True)

        elif char == curses.KEY_RESIZE:
            input_text = ""
            handle_resize(stdscr, False)

        # ^D
        elif char == chr(4):
            if(globals.current_window == 0):
                if(isinstance(globals.channel_list[globals.selected_channel], int)):
                    update_node_info_in_db(globals.channel_list[globals.selected_channel], chat_archived=True)

                    # Shift notifications up to account for deleted item
                    for i in range(len(globals.notifications)):
                        if globals.notifications[i] > globals.selected_channel:
                            globals.notifications[i] -= 1

                    del globals.channel_list[globals.selected_channel]
                    globals.selected_channel = min(globals.selected_channel, len(globals.channel_list) - 1)
                    select_channel(globals.selected_channel)
                    draw_channel_list()
                    draw_messages_window()

        elif char == chr(31):
            if(globals.current_window == 2 or globals.current_window == 0):
                search(globals.current_window)

        else:
            # Append typed character to input text
            if(isinstance(char, str)):
                input_text += char
            else:
                input_text += chr(char)

def draw_splash(stdscr):
    setup_colors()
    curses.curs_set(0)

    stdscr.clear()
    stdscr.bkgd(get_color("background"))

    height, width = stdscr.getmaxyx()
    message_1 = "/ Λ"
    message_2 = "/ / \\"
    message_3 = "P W R D"
    message_4 = "connecting..."

    start_x = width // 2 - len(message_1) // 2
    start_x2 = width // 2 - len(message_4) // 2
    start_y = height // 2 - 1
    stdscr.addstr(start_y, start_x, message_1, get_color("splash_logo", bold=True))
    stdscr.addstr(start_y+1, start_x-1, message_2, get_color("splash_logo", bold=True))
    stdscr.addstr(start_y+2, start_x-2, message_3, get_color("splash_logo", bold=True))
    stdscr.addstr(start_y+4, start_x2, message_4, get_color("splash_text"))

    stdscr.attrset(get_color("window_frame"))
    stdscr.box()
    stdscr.refresh()
    curses.napms(500)


def draw_channel_list():
    channel_pad.erase()
    win_height, win_width = channel_win.getmaxyx()
    start_index = max(0, globals.selected_channel - (win_height - 3))  # Leave room for borders

    channel_pad.resize(len(globals.all_messages), channel_win.getmaxyx()[1])

    idx = 0
    for channel in globals.channel_list:
        # Convert node number to long name if it's an integer
        if isinstance(channel, int):
            if is_chat_archived(channel):
                continue
            channel = get_name_from_database(channel, type='long')

        # Determine whether to add the notification
        notification = " " + config.notification_symbol if idx in globals.notifications else ""

        # Truncate the channel name if it's too long to fit in the window
        truncated_channel = ((channel[:win_width - 5] + '-' if len(channel) > win_width - 5 else channel) + notification).ljust(win_width - 3)

        color = get_color("channel_list")
        if idx == globals.selected_channel:
            if globals.current_window == 0:
                color = get_color("channel_list", reverse=True)
                remove_notification(globals.selected_channel)
            else:
                color = get_color("channel_selected")
        channel_pad.addstr(idx, 1, truncated_channel, color)
        idx += 1

    channel_win.attrset(get_color("window_frame_selected") if globals.current_window == 0 else get_color("window_frame"))
    channel_win.box()
    channel_win.attrset((get_color("window_frame")))
    channel_win.refresh()

    refresh_pad(0)

def draw_messages_window(scroll_to_bottom = False):
    """Update the messages window based on the selected channel and scroll position."""
    messages_pad.erase()

    channel = globals.channel_list[globals.selected_channel]

    if channel in globals.all_messages:
        messages = globals.all_messages[channel]

        msg_line_count = 0

        row = 0
        for (prefix, message) in messages:
            full_message = f"{prefix}{message}"
            wrapped_lines = textwrap.wrap(full_message, messages_win.getmaxyx()[1] - 2)
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

    messages_win.attrset(get_color("window_frame_selected") if globals.current_window == 1 else get_color("window_frame"))
    messages_win.box()
    messages_win.attrset(get_color("window_frame"))
    messages_win.refresh()

    if(scroll_to_bottom):
        globals.selected_message = max(msg_line_count - get_msg_window_lines(), 0)
    else:
        globals.selected_message = max(min(globals.selected_message, msg_line_count - get_msg_window_lines()), 0)

    refresh_pad(1)

    draw_packetlog_win()

def draw_node_list():
    # global nodes_pad
    # if nodes_pad is None:
    #     nodes_pad = curses.newpad(1, 1)

    try:
        nodes_pad.erase()
        box_width = nodes_win.getmaxyx()[1]
        nodes_pad.resize(len(globals.node_list) + 1, box_width)
    except Exception as e: 
        logging.error(f"Error Drawing Nodes List: {e}")
        logging.error("Traceback: %s", traceback.format_exc())

    for i, node_num in enumerate(globals.node_list):
        node = globals.interface.nodesByNum[node_num]
        secure = 'user' in node and 'publicKey' in node['user'] and node['user']['publicKey']
        node_str = f"{'🔐' if secure else '🔓'} {get_name_from_database(node_num, 'long')}".ljust(box_width - 2)[:box_width - 2]
        nodes_pad.addstr(i, 1, node_str, get_color("node_list", reverse=globals.selected_node == i and globals.current_window == 2))

    nodes_win.attrset(get_color("window_frame_selected") if globals.current_window == 2 else get_color("window_frame"))
    nodes_win.box()
    nodes_win.attrset(get_color("window_frame"))
    nodes_win.refresh()

    refresh_pad(2)

def select_channel(idx):
    old_selected_channel = globals.selected_channel
    globals.selected_channel = max(0, min(idx, len(globals.channel_list) - 1))
    draw_messages_window(True)

    # For now just re-draw channel list when clearing notifications, we can probably make this more efficient
    if globals.selected_channel in globals.notifications:
        remove_notification(globals.selected_channel)
        draw_channel_list()
        return
    highlight_line(False, 0, old_selected_channel)
    highlight_line(True, 0, globals.selected_channel)
    refresh_pad(0)

def scroll_channels(direction):
    new_selected_channel = globals.selected_channel + direction

    if new_selected_channel < 0:
        new_selected_channel = len(globals.channel_list) - 1
    elif new_selected_channel >= len(globals.channel_list):
        new_selected_channel = 0

    select_channel(new_selected_channel)

def scroll_messages(direction):
    globals.selected_message += direction

    msg_line_count = messages_pad.getmaxyx()[0]
    globals.selected_message = max(0, min(globals.selected_message, msg_line_count - get_msg_window_lines()))

    refresh_pad(1)

def select_node(idx):
    old_selected_node = globals.selected_node
    globals.selected_node = max(0, min(idx, len(globals.node_list) - 1))

    highlight_line(False, 2, old_selected_node)
    highlight_line(True, 2, globals.selected_node)
    refresh_pad(2)

    draw_function_win()

def scroll_nodes(direction):
    new_selected_node = globals.selected_node + direction

    if new_selected_node < 0:
        new_selected_node = len(globals.node_list) - 1
    elif new_selected_node >= len(globals.node_list):
        new_selected_node = 0

    select_node(new_selected_node)

def draw_packetlog_win():

    columns = [10,10,15,30]
    span = 0

    if globals.display_log:
        packetlog_win.erase()
        height, width = packetlog_win.getmaxyx()
        
        for column in columns[:-1]:
            span += column

        # Add headers
        headers = f"{'From':<{columns[0]}} {'To':<{columns[1]}} {'Port':<{columns[2]}} {'Payload':<{width-span}}"
        packetlog_win.addstr(1, 1, headers[:width - 2],get_color("log_header", underline=True))  # Truncate headers if they exceed window width

        for i, packet in enumerate(reversed(globals.packet_buffer)):
            if i >= height - 3:  # Skip if exceeds the window height
                break
            
            # Format each field
            from_id = get_name_from_database(packet['from'], 'short').ljust(columns[0])
            to_id = (
                "BROADCAST".ljust(columns[1]) if str(packet['to']) == "4294967295"
                else get_name_from_database(packet['to'], 'short').ljust(columns[1])
            )
            if 'decoded' in packet:
                port = packet['decoded']['portnum'].ljust(columns[2])
                payload = (packet['decoded']['payload']).ljust(columns[3])
            else:
                port = "NO KEY".ljust(columns[2])
                payload = "NO KEY".ljust(columns[3])

            # Combine and truncate if necessary
            logString = f"{from_id} {to_id} {port} {payload}"
            logString = logString[:width - 3]

            # Add to the window
            packetlog_win.addstr(i + 2, 1, logString, get_color("log"))
            
        packetlog_win.attrset(get_color("window_frame"))
        packetlog_win.box()
        packetlog_win.refresh()

def search(win):
    start_idx = globals.selected_node
    select_func = select_node

    if win == 0:
        start_idx = globals.selected_channel
        select_func = select_channel

    search_text = ""
    entry_win.erase()

    while True:
        draw_centered_text_field(entry_win, f"Search: {search_text}", 0, get_color("input"))
        char = entry_win.get_wch()

        if char in (chr(27), chr(curses.KEY_ENTER), chr(10), chr(13)):
            break
        elif char == "\t":
            start_idx = globals.selected_node + 1 if win == 2 else globals.selected_channel + 1
        elif char in (curses.KEY_BACKSPACE, chr(127)):
            if search_text:
                search_text = search_text[:-1]
                y, x = entry_win.getyx()
                entry_win.move(y, x - 1)
                entry_win.addch(' ')  #
                entry_win.move(y, x - 1)
                entry_win.erase()
                entry_win.refresh()
        elif isinstance(char, str):
            search_text += char

        search_text_caseless = search_text.casefold()

        l = globals.node_list if win == 2 else globals.channel_list
        for i, n in enumerate(l[start_idx:] + l[:start_idx]):
            if isinstance(n, int) and search_text_caseless in get_name_from_database(n, 'long').casefold() \
              or isinstance(n, int) and search_text_caseless in get_name_from_database(n, 'short').casefold() \
              or search_text_caseless in str(n).casefold():
                select_func((i + start_idx) % len(l))
                break

    entry_win.erase()

def draw_node_details():
    node = None
    try:
        node = globals.interface.nodesByNum[globals.node_list[globals.selected_node]]
    except KeyError:
        return

    function_win.erase()
    function_win.box()

    nodestr = ""
    width = function_win.getmaxyx()[1]

    node_details_list = [f"{node['user']['longName']} "
                           if 'user' in node and 'longName' in node['user'] else "",
                         f"({node['user']['shortName']})"
                           if 'user' in node and 'shortName' in node['user'] else "",
                         f" | {node['user']['hwModel']}"
                           if 'user' in node and 'hwModel' in node['user'] else "",
                         f" | {node['user']['role']}"
                           if 'user' in node and 'role' in node['user'] else ""]

    if globals.node_list[globals.selected_node] == globals.myNodeNum:
        node_details_list.extend([f" | Bat: {node['deviceMetrics']['batteryLevel']}% ({node['deviceMetrics']['voltage']}v)"
                                    if 'deviceMetrics' in node
                                        and 'batteryLevel' in node['deviceMetrics']
                                        and 'voltage' in node['deviceMetrics'] else "",
                                  f" | Up: {get_readable_duration(node['deviceMetrics']['uptimeSeconds'])}" if 'deviceMetrics' in node
                                        and 'uptimeSeconds' in node['deviceMetrics'] else "",
                                  f" | ChUtil: {node['deviceMetrics']['channelUtilization']:.2f}%" if 'deviceMetrics' in node
                                        and 'channelUtilization' in node['deviceMetrics'] else "",
                                  f" | AirUtilTX: {node['deviceMetrics']['airUtilTx']:.2f}%" if 'deviceMetrics' in node
                                        and 'airUtilTx' in node['deviceMetrics'] else "",
                                  ])
    else:
        node_details_list.extend([f" | {get_time_ago(node['lastHeard'])}" if ('lastHeard' in node and node['lastHeard']) else "",
                                 f" | Hops: {node['hopsAway']}" if 'hopsAway' in node else "",
                                 f" | SNR: {node['snr']}dB"
                                   if ('snr' in node and 'hopsAway' in node and node['hopsAway'] == 0)
                                   else "",
                                 ])

    for s in node_details_list:
        if len(nodestr) + len(s) < width - 2:
            nodestr = nodestr + s

    draw_centered_text_field(function_win, nodestr, 0, get_color("commands"))

def draw_help():
    cmds = ["↑→↓← = Select", "    ENTER = Send", "    ` = Settings", "    ^P = Packet Log", "    ESC = Quit", "    ^t = Traceroute", "    ^d = Archive Chat"]
    function_str = ""
    for s in cmds:
        if(len(function_str) + len(s) < function_win.getmaxyx()[1] - 2):
            function_str += s

    draw_centered_text_field(function_win, function_str, 0, get_color("commands"))

def draw_function_win():
    if(globals.current_window == 2):
        draw_node_details()
    else:
        draw_help()

def get_msg_window_lines():
    packetlog_height = packetlog_win.getmaxyx()[0] - 1 if globals.display_log else 0
    return messages_win.getmaxyx()[0] - 2 - packetlog_height

def refresh_pad(window):
    win_height = channel_win.getmaxyx()[0]

    if(window == 1):
        pad = messages_pad
        box = messages_win
        lines = get_msg_window_lines()
        selected_item = globals.selected_message
        start_index = globals.selected_message

        if globals.display_log:
            packetlog_win.box()
            packetlog_win.refresh()

    elif(window == 2):
        pad = nodes_pad
        box = nodes_win
        lines = box.getmaxyx()[0] - 2
        selected_item = globals.selected_node
        start_index = max(0, selected_item - (win_height - 3))  # Leave room for borders

    else:
        pad = channel_pad
        box = channel_win
        lines = box.getmaxyx()[0] - 2
        selected_item = globals.selected_channel
        start_index = max(0, selected_item - (win_height - 3))  # Leave room for borders

    pad.refresh(start_index, 0,
                        box.getbegyx()[0] + 1, box.getbegyx()[1] + 1,
                        box.getbegyx()[0] + lines, box.getbegyx()[1] + box.getmaxyx()[1] - 2)

def highlight_line(highlight, window, line):
    pad = nodes_pad
    color = get_color("node_list")
    select_len = nodes_win.getmaxyx()[1] - 2

    if(window == 0):
        pad = channel_pad
        color = get_color("channel_selected" if (line == globals.selected_channel and highlight == False) else "channel_list")
        select_len = channel_win.getmaxyx()[1] - 2

    pad.chgat(line, 1, select_len, color | curses.A_REVERSE if highlight else color)

def add_notification(channel_number):
    if channel_number not in globals.notifications:
        globals.notifications.append(channel_number)

def remove_notification(channel_number):
    if channel_number in globals.notifications:
        globals.notifications.remove(channel_number)

def draw_text_field(win, text, color):
    win.border()
    win.addstr(1, 1, text, color)

def draw_centered_text_field(win, text, y_offset, color):
    height, width = win.getmaxyx()
    x = (width - len(text)) // 2
    y = (height // 2) + y_offset
    win.addstr(y, x, text, color)
    win.refresh()

def draw_debug(value):
    function_win.addstr(1, 1, f"debug: {value}    ")
    function_win.refresh()