# A basic auto-responder bot that replies to specific messages when bot mode is enabled.
import logging
import threading
import time
from typing import Any, Dict

import contact.ui.default_config as config
from contact.utilities.singleton import app_state, interface_state, ui_state
from contact.message_handlers.tx_handler import send_message

BOT_RESPONSE_DELAY_SECONDS = 2.3

def _get_bot_catch_words() -> set[str]:
    """Return normalized bot trigger words from app settings."""
    raw_words = getattr(config, "ping_bot_catch_words", "ping; test")
    words = {
        word.strip().casefold()
        for word in raw_words.replace(";", ",").split(",")
        if word.strip()
    }
    return words or {"ping"}

def is_bot_message(message: str) -> bool:
    """Return True when the incoming message should trigger an automatic response."""
    return message.strip().casefold() in _get_bot_catch_words()

def bot_respond(packet: Dict[str, Any], message: str, send_channel: int) -> bool:
    """Send a basic response when bot mode is enabled."""
    if not ui_state.bot_mode_enabled:
        return False

    if not is_bot_message(message):
        """ Only respond to specific messages. """
        return False

    from_node = packet.get("from")
    if from_node is None:
        return False
    if from_node == interface_state.myNodeNum:
        return False
    snr = packet.get('rxSnr', -128)
    rssi = packet.get('rxRssi', -128)
    replyIDset = (packet.get('decoded') or {}).get('replyId', False)
    hop_start = packet.get('hopStart', 0)
    hop_limit = packet.get('hopLimit', 0)
    transport_type = packet.get('transportMechanism', None)
    hops = hop_start - hop_limit
    
    details = []
    if snr != -128:
        details.append(f"SNR: {snr}")
    if rssi != -128:
        details.append(f"RSSI: {rssi}")
    if hops != 0:
        details.append(f"Hops: {hops}")
    if replyIDset:
        details.append(f"Relay: {replyIDset}")
    transport_text = str(transport_type).upper() if transport_type is not None else ""
    for transport_name in ("UDP", "MQTT"):
        if transport_name in transport_text:
            details.append(f"Via: {transport_name}")

    response_data_string = getattr(config, "ping_bot_response_word", "Pong!")
    if details:
        response_data_string += f" {', '.join(details)}"

    def send_response_delayed() -> None:
        try:
            time.sleep(BOT_RESPONSE_DELAY_SECONDS)

            with app_state.lock:
                if not ui_state.bot_mode_enabled:
                    return

                send_message(response_data_string,channel=send_channel)

            # Import locally to avoid circular import at module import time.
            from contact.ui.contact_ui import request_ui_redraw

            request_ui_redraw(channels=True, messages=True, scroll_messages_to_bottom=True)
            logging.info("Bot response sent to %s on channel index %s", from_node, send_channel)
        except Exception:
            logging.exception("Bot response send failed for destination %s", from_node)

    threading.Thread(target=send_response_delayed, name="bot-response", daemon=True).start()

    return True
