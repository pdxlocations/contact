import os

# App Variables
app_directory = os.path.dirname(os.path.abspath(__file__))
interface = None
display_log = False
all_messages = {}
channel_list = []
notifications = set()
packet_buffer = []
node_list = []
myNodeNum = 0
selected_channel = 0
selected_message = 0
selected_node = 0
current_window = 0

# User Configurable
db_file_path = os.path.join(app_directory, "client.db")
log_file_path = os.path.join(app_directory, "client.log")
message_prefix = ">>"
sent_message_prefix = message_prefix + " Sent"
notification_symbol = "*"
ack_implicit_str = "[◌]"
ack_str = "[✓]"
nak_str = "[x]"
ack_unknown_str = "[…]"

COLOR_CONFIG = { # white, black, red, green, yellow, blue, magenta, cyan
    "default_text": {"foreground": "white", "background": "black"},
    "rx_messages": {"foreground": "green", "background": "black"},
    "tx_messages": {"foreground": "cyan", "background": "black"},
    "timestamps": {"foreground": "yellow", "background": "black"}
}