import curses
import textwrap
from utilities.utils import get_channels, get_time_ago
from settings import settings_menu
from message_handlers.tx_handler import send_message, send_traceroute
from ui.colors import setup_colors, get_color
from db_handler import get_name_from_database
import default_config as config
import ui.dialog
import globals

def refresh_all():
    for i, box in enumerate([channel_box, messages_box, nodes_box]):
        box.attrset(get_color("window_frame_selected") if globals.current_window == i else get_color("window_frame"))
        box.box()
        box.refresh()
        refresh_pad(i)

def draw_node_details():
    nodes_snapshot = list(globals.interface.nodes.values())

    node = None
    for node in nodes_snapshot:
        if globals.node_list[globals.selected_node] == node['num']:
            break

    function_win.erase()
    function_win.box()

    nodestr = ""
    width = function_win.getmaxyx()[1]
    node_details_list = [f"{node['user']['longName']}"
                           if 'user' in node and 'longName' in node['user'] else "",
                         f"({node['user']['shortName']})"
                           if 'user' in node and 'shortName' in node['user'] else "",
                         f" | {node['user']['hwModel']}"
                           if 'user' in node and 'hwModel' in node['user'] else "",
                         f" | {get_time_ago(node['lastHeard'])}" if ('lastHeard' in node and node['lastHeard']) else "",
                         f" | Hops: {node['hopsAway']}" if 'hopsAway' in node else "",
                         f" | SNR: {node['snr']}dB"
                           if ('snr' in node and 'hopsAway' in node and node['hopsAway'] == 0)
                           else "",
                         ]

    for s in node_details_list:
        if len(nodestr) + len(s) < width:
            nodestr = nodestr + s

    draw_centered_text_field(function_win, nodestr, 0, get_color("commands"))

def draw_function_win():
    cmds = ["↑→↓← = Select", "    ENTER = Send", "    ` = Settings", "    ^P = Packet Log", "    ESC = Quit"]
    function_str = ""
    for s in cmds:
        if(len(function_str) + len(s) < function_win.getmaxyx()[1]):
            function_str += s

    draw_centered_text_field(function_win, function_str, 0, get_color("commands"))

def get_msg_window_lines():
    packetlog_height = packetlog_win.getmaxyx()[0] - 1 if globals.display_log else 0
    return messages_box.getmaxyx()[0] - 2 - packetlog_height

def refresh_pad(window):
    win_height = channel_box.getmaxyx()[0]

    selected_item = globals.selected_channel
    pad = channel_pad
    box = channel_box
    lines = box.getmaxyx()[0] - 2
    start_index = max(0, selected_item - (win_height - 3))  # Leave room for borders

    if(window == 1):
        pad = messages_pad
        box = messages_box
        lines = get_msg_window_lines()
        selected_item = globals.selected_message
        start_index = globals.selected_message

        if globals.display_log:
            packetlog_win.box()
            packetlog_win.refresh()

    if(window == 2):
        pad = nodes_pad
        box = nodes_box
        lines = box.getmaxyx()[0] - 2
        selected_item = globals.selected_node
        start_index = max(0, selected_item - (win_height - 3))  # Leave room for borders


    pad.refresh(start_index, 0,
                        box.getbegyx()[0] + 1, box.getbegyx()[1] + 1,
                        box.getbegyx()[0] + lines, box.getbegyx()[1] + box.getmaxyx()[1] - 2)

def highlight_line(highlight, window, line):
    pad = channel_pad
    select_len = 0
    ch_color = get_color("channel_list")
    nd_color = get_color("node_list")

    if(window == 2):
        pad = nodes_pad
        select_len = len(get_name_from_database(globals.node_list[line], "long"))

        pad.chgat(line, 1, select_len, nd_color | curses.A_REVERSE if highlight else nd_color)

    if(window == 0):
        channel = list(globals.all_messages.keys())[line]
        win_width = channel_box.getmaxyx()[1]

        if(isinstance(channel, int)):
            channel = get_name_from_database(channel, type="long")
        select_len = min(len(channel), win_width - 4)

        if line == globals.selected_channel and highlight == False:
            ch_color = get_color("channel_selected")

        pad.chgat(line, 1, select_len, ch_color | curses.A_REVERSE if highlight else ch_color)

def add_notification(channel_number):
    globals.notifications.add(channel_number) 

def remove_notification(channel_number):
    globals.notifications.discard(channel_number) 

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
    win_height, win_width = channel_box.getmaxyx()
    start_index = max(0, globals.selected_channel - (win_height - 3))  # Leave room for borders

    channel_pad.resize(len(globals.all_messages), channel_box.getmaxyx()[1])

    for i, channel in enumerate(list(globals.all_messages.keys())):
        # Convert node number to long name if it's an integer
        if isinstance(channel, int):
            channel = get_name_from_database(channel, type='long')

        # Determine whether to add the notification
        notification = " " + config.notification_symbol if i in globals.notifications else ""

        # Truncate the channel name if it's too long to fit in the window
        truncated_channel = channel[:win_width - 5] + '-' if len(channel) > win_width - 5 else channel
        if i == globals.selected_channel:
            if globals.current_window == 0:
                channel_pad.addstr(i, 1, truncated_channel + notification, get_color("channel_list", reverse=True))
                remove_notification(globals.selected_channel)
            else:
                channel_pad.addstr(i, 1, truncated_channel + notification, get_color("channel_selected"))
        else:
            channel_pad.addstr(i, 1, truncated_channel + notification, get_color("channel_list"))

    channel_box.attrset(get_color("window_frame_selected") if globals.current_window == 0 else get_color("window_frame"))
    channel_box.box()
    channel_box.attrset((get_color("window_frame")))
    channel_box.refresh()

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
            wrapped_lines = textwrap.wrap(full_message, messages_box.getmaxyx()[1] - 2)
            msg_line_count += len(wrapped_lines)
            messages_pad.resize(msg_line_count, messages_box.getmaxyx()[1])

            for line in wrapped_lines:
                if prefix.startswith("--"):
                    color = get_color("timestamps")
                elif prefix.startswith(config.sent_message_prefix):
                    color = get_color("tx_messages") 
                else:
                    color = get_color("rx_messages") 
                    
                messages_pad.addstr(row, 1, line, color)
                row += 1

    messages_box.attrset(get_color("window_frame_selected") if globals.current_window == 1 else get_color("window_frame"))
    messages_box.box()
    messages_box.attrset(get_color("window_frame"))
    messages_box.refresh()

    if(scroll_to_bottom):
        globals.selected_message = max(msg_line_count - get_msg_window_lines(), 0)
    else:
        globals.selected_message = max(min(globals.selected_message, msg_line_count - get_msg_window_lines()), 0)

    refresh_pad(1)

    draw_packetlog_win()

def draw_node_list():
    nodes_pad.erase()
    nodes_pad.resize(len(globals.node_list), nodes_box.getmaxyx()[1])

    for i, node in enumerate(globals.node_list):
        if globals.selected_node == i and globals.current_window == 2:
            nodes_pad.addstr(i, 1, get_name_from_database(node, "long"), get_color("node_list", reverse=True))
        else:
            nodes_pad.addstr(i, 1, get_name_from_database(node, "long"), get_color("node_list"))

    nodes_box.attrset(get_color("window_frame_selected") if globals.current_window == 2 else get_color("window_frame"))
    nodes_box.box()
    nodes_box.attrset(get_color("window_frame"))
    nodes_box.refresh()

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

    draw_node_details()

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

def handle_resize(stdscr, firstrun):
    global messages_pad, messages_box, nodes_pad, nodes_box, channel_pad, channel_box, function_win, packetlog_win, entry_win

    # Calculate window max dimensions
    height, width = stdscr.getmaxyx()

    # Define window dimensions and positions
    channel_width = 3 * (width // 16)
    nodes_width = 5 * (width // 16)
    messages_width = width - channel_width - nodes_width

    if firstrun:
        entry_win = curses.newwin(3, width, 0, 0)
        channel_box = curses.newwin(height - 6, channel_width, 3, 0)
        messages_box = curses.newwin(height - 6, messages_width, 3, channel_width)
        nodes_box = curses.newwin(height - 6, nodes_width, 3, channel_width + messages_width)
        function_win = curses.newwin(3, width, height - 3, 0)
        packetlog_win = curses.newwin(int(height / 3), messages_width, height - int(height / 3) - 3, channel_width)

        # Will be resized to what we need when drawn
        messages_pad = curses.newpad(1, 1)
        nodes_pad = curses.newpad(1,1)
        channel_pad = curses.newpad(1,1)

        entry_win.bkgd(get_color("background"))
        channel_box.bkgd(get_color("background"))
        messages_box.bkgd(get_color("background"))
        nodes_box.bkgd(get_color("background"))

        messages_pad.bkgd(get_color("background"))
        nodes_pad.bkgd(get_color("background"))
        channel_pad.bkgd(get_color("background"))

        function_win.bkgd(get_color("background"))
        packetlog_win.bkgd(get_color("background"))

        channel_box.attrset(get_color("window_frame"))
        entry_win.attrset(get_color("window_frame"))
        nodes_box.attrset(get_color("window_frame"))
        messages_box.attrset(get_color("window_frame"))
        function_win.attrset(get_color("window_frame"))

    else:
        entry_win.erase()
        channel_box.erase()
        messages_box.erase()
        nodes_box.erase()
        function_win.erase()
        packetlog_win.erase()
        entry_win.resize(3, width)
        channel_box.resize(height - 6, channel_width)
        messages_box.resize(height - 6, messages_width)
        messages_box.mvwin(3, channel_width)
        nodes_box.resize(height - 6, nodes_width)
        nodes_box.mvwin(3, channel_width + messages_width)
        function_win.resize(3, width)
        function_win.mvwin(height - 3, 0)
        packetlog_win.resize(int(height / 3), messages_width)
        packetlog_win.mvwin(height - int(height / 3) - 3, channel_width)

    draw_function_win()

    channel_box.box()
    entry_win.box()
    nodes_box.box()
    messages_box.box()

    function_win.box()

    # Refresh all windows
    entry_win.refresh()
    channel_box.refresh()
    function_win.refresh()
    nodes_box.refresh()
    messages_box.refresh()

    entry_win.keypad(True)
    curses.curs_set(1)

    draw_channel_list()
    draw_node_list()
    draw_messages_window(True)

def main_ui(stdscr):
    global messages_pad, messages_box, nodes_pad, nodes_box, channel_pad, channel_box, function_win, packetlog_win, entry_win
    messages_pad = messages_box = nodes_pad = nodes_box = channel_pad = channel_box = function_win = packetlog_win = entry_win = None

    stdscr.keypad(True)
    get_channels()

    input_text = ""

    handle_resize(stdscr, True)

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

        elif char == curses.KEY_RESIZE:
            input_text = ""
            handle_resize(stdscr, False)

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
                select_channel(globals.selected_channel - (channel_box.getmaxyx()[0] - 2)) # select_channel will bounds check for us
            elif globals.current_window == 1:
                globals.selected_message = max(globals.selected_message - get_msg_window_lines(), 0)
                refresh_pad(1)
            elif globals.current_window == 2:
                select_node(globals.selected_node - (nodes_box.getmaxyx()[0] - 2)) # select_node will bounds check for us

        elif char == curses.KEY_NPAGE:
            if globals.current_window == 0:
                select_channel(globals.selected_channel + (channel_box.getmaxyx()[0] - 2)) # select_channel will bounds check for us
            elif globals.current_window == 1:
                msg_line_count = messages_pad.getmaxyx()[0]
                globals.selected_message = min(globals.selected_message + get_msg_window_lines(), msg_line_count - get_msg_window_lines())
                refresh_pad(1)
            elif globals.current_window == 2:
                select_node(globals.selected_node + (nodes_box.getmaxyx()[0] - 2)) # select_node will bounds check for us

        elif char == curses.KEY_LEFT or char == curses.KEY_RIGHT:
            delta = -1 if char == curses.KEY_LEFT else 1

            old_window = globals.current_window
            globals.current_window = (globals.current_window + delta) % 3

            if old_window == 0:
                channel_box.attrset(get_color("window_frame"))
                channel_box.box()
                channel_box.refresh()
                highlight_line(False, 0, globals.selected_channel)
                refresh_pad(0)
            if old_window == 1:
                messages_box.attrset(get_color("window_frame"))
                messages_box.box()
                messages_box.refresh()
                refresh_pad(1)
            elif old_window == 2:
                draw_function_win()
                nodes_box.attrset(get_color("window_frame"))
                nodes_box.box()
                nodes_box.refresh()
                highlight_line(False, 2, globals.selected_node)
                refresh_pad(2)

            if globals.current_window == 0:
                channel_box.attrset(get_color("window_frame_selected"))
                channel_box.box()
                channel_box.attrset(get_color("window_frame"))
                channel_box.refresh()
                highlight_line(True, 0, globals.selected_channel)
                refresh_pad(0)
            elif globals.current_window == 1:
                messages_box.attrset(get_color("window_frame_selected"))
                messages_box.box()
                messages_box.attrset(get_color("window_frame"))
                messages_box.refresh()
                refresh_pad(1)
            elif globals.current_window == 2:
                draw_node_details()
                nodes_box.attrset(get_color("window_frame_selected"))
                nodes_box.box()
                nodes_box.attrset(get_color("window_frame"))
                nodes_box.refresh()
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
            refresh_all()

        elif char in (chr(curses.KEY_ENTER), chr(10), chr(13)):
            if globals.current_window == 2:
                node_list = globals.node_list
                if node_list[globals.selected_node] not in globals.channel_list:
                    globals.channel_list.append(node_list[globals.selected_node])
                    globals.all_messages[node_list[globals.selected_node]] = []

                globals.selected_channel = globals.channel_list.index(node_list[globals.selected_node])
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
            refresh_all()
        
        elif char == chr(16):
            # Display packet log
            if globals.display_log is False:
                globals.display_log = True
                draw_messages_window(True)
            else:
                globals.display_log = False
                packetlog_win.erase()
                draw_messages_window(True)
        else:
            # Append typed character to input text
            if(isinstance(char, str)):
                input_text += char
            else:
                input_text += chr(char)


