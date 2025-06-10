import logging
import os
import platform
import shutil
import subprocess
import time
from datetime import datetime
from typing import Any, Dict

from contact.utilities.utils import refresh_node_list
from contact.ui.contact_ui import (
    draw_packetlog_win,
    draw_node_list,
    draw_messages_window,
    draw_channel_list,
    add_notification,
)
from contact.utilities.db_handler import (
    save_message_to_db,
    maybe_store_nodeinfo_in_db,
    get_name_from_database,
    update_node_info_in_db,
)
import contact.ui.default_config as config

from contact.utilities.singleton import ui_state, interface_state, app_state


def play_sound():
    try:
        system = platform.system()

        if system == "Darwin":  # macOS
            sound_path = "/System/Library/Sounds/Ping.aiff"
            if os.path.exists(sound_path):
                subprocess.run(["afplay", sound_path], check=True)
                return
            else:
                logging.warning(f"macOS sound file not found: {sound_path}")

        elif system == "Linux":
            sound_path = "/usr/share/sounds/freedesktop/stereo/complete.oga"
            if os.path.exists(sound_path):
                if shutil.which("paplay"):
                    subprocess.run(["paplay", sound_path], check=True)
                    return
                elif shutil.which("aplay"):
                    subprocess.run(["aplay", sound_path], check=True)
                    return
                else:
                    logging.warning("No sound player found (paplay/aplay)")
            else:
                logging.warning(f"Linux sound file not found: {sound_path}")

    except subprocess.CalledProcessError as e:
        logging.error(f"Sound playback failed: {e}")
    except Exception as e:
        logging.error(f"Unexpected error: {e}")

    # Final fallback: terminal beep
    print("\a")


def on_receive(packet: Dict[str, Any], interface: Any) -> None:
    """
    Handles an incoming packet from a Meshtastic interface.

    Args:
        packet: The received Meshtastic packet as a dictionary.
        interface: The Meshtastic interface instance that received the packet.
    """
    with app_state.lock:
        # Update packet log
        ui_state.packet_buffer.append(packet)
        if len(ui_state.packet_buffer) > 20:
            # Trim buffer to 20 packets
            ui_state.packet_buffer = ui_state.packet_buffer[-20:]

        if ui_state.display_log:
            draw_packetlog_win()
        try:
            if "decoded" not in packet:
                return

            # Assume any incoming packet could update the last seen time for a node
            changed = refresh_node_list()
            if changed:
                draw_node_list()

            if packet["decoded"]["portnum"] == "NODEINFO_APP":
                if "user" in packet["decoded"] and "longName" in packet["decoded"]["user"]:
                    maybe_store_nodeinfo_in_db(packet)

            elif packet["decoded"]["portnum"] == "TEXT_MESSAGE_APP":

                if config.notification_sound == "True":
                    play_sound()

                message_bytes = packet["decoded"]["payload"]
                message_string = message_bytes.decode("utf-8")

                refresh_channels = False
                refresh_messages = False

                if packet.get("channel"):
                    channel_number = packet["channel"]
                else:
                    channel_number = 0

                if packet["to"] == interface_state.myNodeNum:
                    if packet["from"] in ui_state.channel_list:
                        pass
                    else:
                        ui_state.channel_list.append(packet["from"])
                        if packet["from"] not in ui_state.all_messages:
                            ui_state.all_messages[packet["from"]] = []
                        update_node_info_in_db(packet["from"], chat_archived=False)
                        refresh_channels = True

                    channel_number = ui_state.channel_list.index(packet["from"])

                if ui_state.channel_list[channel_number] != ui_state.channel_list[ui_state.selected_channel]:
                    add_notification(channel_number)
                    refresh_channels = True
                else:
                    refresh_messages = True

                # Add received message to the messages list
                message_from_id = packet["from"]
                message_from_string = get_name_from_database(message_from_id, type="short") + ":"

                if ui_state.channel_list[channel_number] not in ui_state.all_messages:
                    ui_state.all_messages[ui_state.channel_list[channel_number]] = []

                # Timestamp handling
                current_timestamp = time.time()
                current_hour = datetime.fromtimestamp(current_timestamp).strftime("%Y-%m-%d %H:00")

                # Retrieve the last timestamp if available
                channel_messages = ui_state.all_messages[ui_state.channel_list[channel_number]]
                if channel_messages:
                    # Check the last entry for a timestamp
                    for entry in reversed(channel_messages):
                        if entry[0].startswith("--"):
                            last_hour = entry[0].strip("- ").strip()
                            break
                    else:
                        last_hour = None
                else:
                    last_hour = None

                # Add a new timestamp if it's a new hour
                if last_hour != current_hour:
                    ui_state.all_messages[ui_state.channel_list[channel_number]].append((f"-- {current_hour} --", ""))

                ui_state.all_messages[ui_state.channel_list[channel_number]].append(
                    (f"{config.message_prefix} {message_from_string} ", message_string)
                )

                if refresh_channels:
                    draw_channel_list()
                if refresh_messages:
                    draw_messages_window(True)

                save_message_to_db(ui_state.channel_list[channel_number], message_from_id, message_string)

        except KeyError as e:
            logging.error(f"Error processing packet: {e}")
