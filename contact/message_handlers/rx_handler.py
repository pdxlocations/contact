import logging
import os
import platform
import shutil
import subprocess
import threading
import time
from typing import Any, Dict

import contact.ui.default_config as config
from contact.utilities.db_handler import (
    get_name_from_database,
    maybe_store_nodeinfo_in_db,
    save_message_to_db,
    update_node_info_in_db,
)
from contact.utilities.singleton import app_state, interface_state, menu_state, ui_state
from contact.utilities.utils import add_new_message, refresh_node_list

# Debounce notification sounds so a burst of queued messages only plays once.
_SOUND_DEBOUNCE_SECONDS = 0.8
_sound_timer: threading.Timer | None = None
_sound_timer_lock = threading.Lock()
_last_sound_request = 0.0


def schedule_notification_sound(delay: float = _SOUND_DEBOUNCE_SECONDS) -> None:
    """Schedule a notification sound after a short quiet period."""
    global _sound_timer, _last_sound_request

    now = time.monotonic()
    with _sound_timer_lock:
        _last_sound_request = now

        if _sound_timer is not None:
            try:
                _sound_timer.cancel()
            except Exception:
                pass
            _sound_timer = None

        def _fire(expected_request_time: float) -> None:
            with _sound_timer_lock:
                if expected_request_time != _last_sound_request:
                    return
            play_sound()

        _sound_timer = threading.Timer(delay, _fire, args=(now,))
        _sound_timer.daemon = True
        _sound_timer.start()


def play_sound() -> None:
    try:
        system = platform.system()
        sound_path = None
        executable = None

        if system == "Darwin":
            sound_path = "/System/Library/Sounds/Ping.aiff"
            executable = "afplay"
        elif system == "Linux":
            ogg_path = "/usr/share/sounds/freedesktop/stereo/complete.oga"
            wav_path = "/usr/share/sounds/alsa/Front_Center.wav"
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
    except subprocess.CalledProcessError as exc:
        logging.error("Sound playback failed: %s", exc)
    except Exception as exc:
        logging.error("Unexpected error while playing sound: %s", exc)


def _decode_message_payload(payload: Any) -> str:
    if isinstance(payload, bytes):
        return payload.decode("utf-8", errors="replace")
    if isinstance(payload, str):
        return payload
    return str(payload)


def process_receive_event(packet: Dict[str, Any]) -> None:
    """Process a queued packet on the UI thread and perform all UI updates."""
    # Local import prevents module-level circular import.
    from contact.ui.contact_ui import (
        add_notification,
        draw_channel_list,
        draw_messages_window,
        draw_node_list,
        draw_packetlog_win,
    )

    # Update packet log
    ui_state.packet_buffer.append(packet)
    if len(ui_state.packet_buffer) > 20:
        ui_state.packet_buffer = ui_state.packet_buffer[-20:]

    if ui_state.display_log:
        draw_packetlog_win()
        if ui_state.current_window == 4:
            menu_state.need_redraw = True

    decoded = packet.get("decoded")
    if not isinstance(decoded, dict):
        return

    changed = refresh_node_list()
    if changed:
        draw_node_list()

    portnum = decoded.get("portnum")
    if portnum == "NODEINFO_APP":
        user = decoded.get("user")
        if isinstance(user, dict) and "longName" in user:
            maybe_store_nodeinfo_in_db(packet)
        return

    if portnum != "TEXT_MESSAGE_APP":
        return

    hop_start = packet.get("hopStart", 0)
    hop_limit = packet.get("hopLimit", 0)
    hops = hop_start - hop_limit

    if config.notification_sound == "True":
        schedule_notification_sound()

    message_string = _decode_message_payload(decoded.get("payload"))

    if not ui_state.channel_list:
        return

    refresh_channels = False
    refresh_messages = False

    channel_number = packet.get("channel", 0)
    if not isinstance(channel_number, int):
        channel_number = 0
    if channel_number < 0:
        channel_number = 0

    packet_from = packet.get("from")
    if packet.get("to") == interface_state.myNodeNum and packet_from is not None:
        if packet_from not in ui_state.channel_list:
            ui_state.channel_list.append(packet_from)
            if packet_from not in ui_state.all_messages:
                ui_state.all_messages[packet_from] = []
            update_node_info_in_db(packet_from, chat_archived=False)
            refresh_channels = True
        channel_number = ui_state.channel_list.index(packet_from)

    if channel_number >= len(ui_state.channel_list):
        channel_number = 0

    channel_id = ui_state.channel_list[channel_number]

    if ui_state.selected_channel >= len(ui_state.channel_list):
        ui_state.selected_channel = 0

    if channel_id != ui_state.channel_list[ui_state.selected_channel]:
        add_notification(channel_number)
        refresh_channels = True
    else:
        refresh_messages = True

    if packet_from is None:
        logging.debug("Skipping TEXT_MESSAGE_APP packet with missing 'from' field")
        return

    message_from_string = get_name_from_database(packet_from, type="short") + ":"
    add_new_message(channel_id, f"{config.message_prefix} [{hops}] {message_from_string} ", message_string)

    if refresh_channels:
        draw_channel_list()
    if refresh_messages:
        draw_messages_window(True)

    save_message_to_db(channel_id, packet_from, message_string)


def on_receive(packet: Dict[str, Any], interface: Any) -> None:
    """Enqueue packet to be processed on the main curses thread."""
    if app_state.ui_shutdown:
        return
    if not isinstance(packet, dict):
        return
    try:
        app_state.rx_queue.put(packet)
    except Exception:
        logging.exception("Failed to enqueue packet for UI processing")
