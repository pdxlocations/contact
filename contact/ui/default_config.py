import json
import logging
import os
from typing import Dict

# Get the parent directory of the script
script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.abspath(os.path.join(script_dir, os.pardir))

# Paths
json_file_path = os.path.join(parent_dir, "config.json")
log_file_path = os.path.join(parent_dir, "client.log")
db_file_path = os.path.join(parent_dir, "client.db")


def format_json_single_line_arrays(data: Dict[str, object], indent: int = 4) -> str:
    """
    Formats JSON with arrays on a single line while keeping other elements properly indented.
    """

    def format_value(value: object, current_indent: int) -> str:
        if isinstance(value, dict):
            items = []
            for key, val in value.items():
                items.append(f'{" " * current_indent}"{key}": {format_value(val, current_indent + indent)}')
            return "{\n" + ",\n".join(items) + f"\n{' ' * (current_indent - indent)}}}"
        elif isinstance(value, list):
            return f"[{', '.join(json.dumps(el, ensure_ascii=False) for el in value)}]"
        else:
            return json.dumps(value, ensure_ascii=False)

    return format_value(data, indent)


# Recursive function to check and update nested dictionaries
def update_dict(default: Dict[str, object], actual: Dict[str, object]) -> bool:
    updated = False
    for key, value in default.items():
        if key not in actual:
            actual[key] = value
            updated = True
        elif isinstance(value, dict):
            # Recursively check nested dictionaries
            updated = update_dict(value, actual[key]) or updated
    return updated


def initialize_config() -> Dict[str, object]:
    COLOR_CONFIG_DARK = {
        "default": ["white", "black"],
        "background": [" ", "black"],
        "splash_logo": ["green", "black"],
        "splash_text": ["white", "black"],
        "input": ["white", "black"],
        "node_list": ["white", "black"],
        "channel_list": ["white", "black"],
        "channel_selected": ["green", "black"],
        "rx_messages": ["cyan", "black"],
        "tx_messages": ["green", "black"],
        "timestamps": ["white", "black"],
        "commands": ["white", "black"],
        "window_frame": ["white", "black"],
        "window_frame_selected": ["green", "black"],
        "log_header": ["blue", "black"],
        "log": ["green", "black"],
        "settings_default": ["white", "black"],
        "settings_sensitive": ["red", "black"],
        "settings_save": ["green", "black"],
        "settings_breadcrumbs": ["white", "black"],
        "settings_warning": ["red", "black"],
        "settings_note": ["green", "black"],
        "node_favorite": ["green", "black"],
        "node_ignored": ["red", "black"],
    }
    COLOR_CONFIG_LIGHT = {
        "default": ["black", "white"],
        "background": [" ", "white"],
        "splash_logo": ["green", "white"],
        "splash_text": ["black", "white"],
        "input": ["black", "white"],
        "node_list": ["black", "white"],
        "channel_list": ["black", "white"],
        "channel_selected": ["green", "white"],
        "rx_messages": ["cyan", "white"],
        "tx_messages": ["green", "white"],
        "timestamps": ["black", "white"],
        "commands": ["black", "white"],
        "window_frame": ["black", "white"],
        "window_frame_selected": ["green", "white"],
        "log_header": ["black", "white"],
        "log": ["blue", "white"],
        "settings_default": ["black", "white"],
        "settings_sensitive": ["red", "white"],
        "settings_save": ["green", "white"],
        "settings_breadcrumbs": ["black", "white"],
        "settings_warning": ["red", "white"],
        "settings_note": ["green", "white"],
        "node_favorite": ["green", "white"],
        "node_ignored": ["red", "white"],
    }
    COLOR_CONFIG_GREEN = {
        "default": ["green", "black"],
        "background": [" ", "black"],
        "splash_logo": ["green", "black"],
        "splash_text": ["green", "black"],
        "input": ["green", "black"],
        "node_list": ["green", "black"],
        "channel_list": ["green", "black"],
        "channel_selected": ["cyan", "black"],
        "rx_messages": ["green", "black"],
        "tx_messages": ["green", "black"],
        "timestamps": ["green", "black"],
        "commands": ["green", "black"],
        "window_frame": ["green", "black"],
        "window_frame_selected": ["cyan", "black"],
        "log_header": ["green", "black"],
        "log": ["green", "black"],
        "settings_default": ["green", "black"],
        "settings_sensitive": ["green", "black"],
        "settings_save": ["green", "black"],
        "settings_breadcrumbs": ["green", "black"],
        "settings_save": ["green", "black"],
        "settings_breadcrumbs": ["green", "black"],
        "settings_warning": ["green", "black"],
        "settings_note": ["green", "black"],
        "node_favorite": ["cyan", "green"],
        "node_ignored": ["red", "black"],
    }
    default_config_variables = {
        "channel_list_16ths": "3",
        "node_list_16ths": "5",
        "db_file_path": db_file_path,
        "log_file_path": log_file_path,
        "message_prefix": ">>",
        "sent_message_prefix": ">> Sent",
        "notification_symbol": "*",
        "notification_sound": "True",
        "ack_implicit_str": "[◌]",
        "ack_str": "[✓]",
        "nak_str": "[x]",
        "ack_unknown_str": "[…]",
        "node_sort": "lastHeard",
        "theme": "dark",
        "COLOR_CONFIG_DARK": COLOR_CONFIG_DARK,
        "COLOR_CONFIG_LIGHT": COLOR_CONFIG_LIGHT,
        "COLOR_CONFIG_GREEN": COLOR_CONFIG_GREEN,
    }

    if not os.path.exists(json_file_path):
        with open(json_file_path, "w", encoding="utf-8") as json_file:
            formatted_json = format_json_single_line_arrays(default_config_variables)
            json_file.write(formatted_json)

    # Ensure all default variables exist in the JSON file
    with open(json_file_path, "r", encoding="utf-8") as json_file:
        loaded_config = json.load(json_file)

    # Check and add missing variables
    updated = update_dict(default_config_variables, loaded_config)

    # Update the JSON file if any variables were missing
    if updated:
        formatted_json = format_json_single_line_arrays(loaded_config)
        with open(json_file_path, "w", encoding="utf-8") as json_file:
            json_file.write(formatted_json)
        logging.info(f"JSON file updated with missing default variables and COLOR_CONFIG items.")

    return loaded_config


def assign_config_variables(loaded_config: Dict[str, object]) -> None:
    # Assign values to local variables

    global db_file_path, log_file_path, message_prefix, sent_message_prefix
    global notification_symbol, ack_implicit_str, ack_str, nak_str, ack_unknown_str
    global node_list_16ths, channel_list_16ths
    global theme, COLOR_CONFIG
    global node_sort, notification_sound

    channel_list_16ths = loaded_config["channel_list_16ths"]
    node_list_16ths = loaded_config["node_list_16ths"]
    db_file_path = loaded_config["db_file_path"]
    log_file_path = loaded_config["log_file_path"]
    message_prefix = loaded_config["message_prefix"]
    sent_message_prefix = loaded_config["sent_message_prefix"]
    notification_symbol = loaded_config["notification_symbol"]
    notification_sound = loaded_config["notification_sound"]
    ack_implicit_str = loaded_config["ack_implicit_str"]
    ack_str = loaded_config["ack_str"]
    nak_str = loaded_config["nak_str"]
    ack_unknown_str = loaded_config["ack_unknown_str"]
    node_sort = loaded_config["node_sort"]
    theme = loaded_config["theme"]
    if theme == "dark":
        COLOR_CONFIG = loaded_config["COLOR_CONFIG_DARK"]
    elif theme == "light":
        COLOR_CONFIG = loaded_config["COLOR_CONFIG_LIGHT"]
    elif theme == "green":
        COLOR_CONFIG = loaded_config["COLOR_CONFIG_GREEN"]


# Call the function when the script is imported
loaded_config = initialize_config()
assign_config_variables(loaded_config)

if __name__ == "__main__":
    logging.basicConfig(
        filename="default_config.log",
        level=logging.INFO,  # DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format="%(asctime)s - %(levelname)s - %(message)s",
    )
    print("\nLoaded Configuration:")
    print(f"Database File Path: {db_file_path}")
    print(f"Log File Path: {log_file_path}")
    print(f"Message Prefix: {message_prefix}")
    print(f"Sent Message Prefix: {sent_message_prefix}")
    print(f"Notification Symbol: {notification_symbol}")
    print(f"ACK Implicit String: {ack_implicit_str}")
    print(f"ACK String: {ack_str}")
    print(f"NAK String: {nak_str}")
    print(f"ACK Unknown String: {ack_unknown_str}")
    print(f"Color Config: {COLOR_CONFIG}")
