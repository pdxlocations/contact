import logging
import os
import platform
import shutil
import time
import subprocess
import threading
 # Debounce notification sounds so a burst of queued messages only plays once.
_SOUND_DEBOUNCE_SECONDS = 0.8
_sound_timer: threading.Timer | None = None
_sound_timer_lock = threading.Lock()
_last_sound_request = 0.0


def schedule_notification_sound(delay: float = _SOUND_DEBOUNCE_SECONDS) -> None:
    """Schedule a notification sound after a short quiet period.

    If more messages arrive before the delay elapses, the timer is reset.
    This prevents playing a sound for each message when a backlog flushes.
    """
    global _sound_timer, _last_sound_request

    now = time.monotonic()
    with _sound_timer_lock:
        _last_sound_request = now

        # Cancel any previously scheduled sound.
        if _sound_timer is not None:
            try:
                _sound_timer.cancel()
            except Exception:
                pass
            _sound_timer = None

        def _fire(expected_request_time: float) -> None:
            # Only play if nothing newer has been scheduled.
            with _sound_timer_lock:
                if expected_request_time != _last_sound_request:
                    return
            play_sound()

        _sound_timer = threading.Timer(delay, _fire, args=(now,))
        _sound_timer.daemon = True
        _sound_timer.start()
from typing import Any, Dict

from contact.utilities.utils import (
    refresh_node_list,
    add_new_message,
)
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

from contact.utilities.singleton import ui_state, interface_state, app_state, menu_state


def play_sound():
    try:
        system = platform.system()
        sound_path = None
        executable = None

        if system == "Darwin":  # macOS
            sound_path = "/System/Library/Sounds/Ping.aiff"
            executable = "afplay"

        elif system == "Linux":
            ogg_path = "/usr/share/sounds/freedesktop/stereo/complete.oga"
            wav_path = "/usr/share/sounds/alsa/Front_Center.wav"  # common fallback

            if shutil.which("paplay") and os.path.exists(ogg_path):
                executable = "paplay"
                sound_path = ogg_path
            elif shutil.which("ffplay") and os.path.exists(ogg_path):
                executable = "ffplay"
                sound_path = ogg_path
            elif shutil.which("aplay") and os.path.exists(wav_path):
                executable = "aplay"
                sound_path = wav_path
            else:
                logging.warning("No suitable sound player or sound file found on Linux")

        if executable and sound_path:
            cmd = [executable, sound_path]
            if executable == "ffplay":
                cmd = [executable, "-nodisp", "-autoexit", sound_path]

            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return

    except subprocess.CalledProcessError as e:
        logging.error(f"Sound playback failed: {e}")
    except Exception as e:
        logging.error(f"Unexpected error: {e}")


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

            if ui_state.current_window == 4:
                menu_state.need_redraw = True
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
                hop_start = packet.get('hopStart', 0)
                hop_limit = packet.get('hopLimit', 0)

                hops = hop_start - hop_limit


                if config.notification_sound == "True":
                    schedule_notification_sound()

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

                channel_id = ui_state.channel_list[channel_number]

                if channel_id != ui_state.channel_list[ui_state.selected_channel]:
                    add_notification(channel_number)
                    refresh_channels = True
                else:
                    refresh_messages = True

                # Add received message to the messages list
                message_from_id = packet["from"]
                message_from_string = get_name_from_database(message_from_id, type="short") + ":"

                add_new_message(channel_id, f"{config.message_prefix} [{hops}] {message_from_string} ", message_string)

                if refresh_channels:
                    draw_channel_list()
                if refresh_messages:
                    draw_messages_window(True)

                save_message_to_db(channel_id, message_from_id, message_string)

        except KeyError as e:
            logging.error(f"Error processing packet: {e}")
