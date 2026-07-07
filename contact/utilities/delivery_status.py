from typing import Any

import contact.ui.default_config as config


ACK_TYPE_EXPLICIT = "Ack"
ACK_TYPE_IMPLICIT = "Implicit"
ACK_TYPE_IMPLICIT_DM = "ImplicitDM"
NAK_PREFIX = "Nak:"

ROUTING_ERROR_STATUS = {
    "1": "Failed to deliver to mesh",
    "2": "Failed to deliver to mesh",
    "3": "Failed to deliver to mesh",
    "4": "No radio interface",
    "5": "Failed to deliver to mesh",
    "6": "Channel/key mismatch",
    "7": "Message is too large to send",
    "8": "No app response",
    "9": "Duty cycle limit",
    "32": "Invalid request",
    "33": "Not authorized",
    "34": "Could not send encrypted message",
    "35": "Recipient needs your key",
    "36": "Admin session expired",
    "37": "Admin key not authorized",
    "38": "Rate limited",
    "39": "Recipient key unavailable",
    "NO_ROUTE": "Failed to deliver to mesh",
    "GOT_NAK": "Failed to deliver to mesh",
    "TIMEOUT": "Failed to deliver to mesh",
    "MAX_RETRANSMIT": "Failed to deliver to mesh",
    "NO_CHANNEL": "Channel/key mismatch",
    "NO_INTERFACE": "No radio interface",
    "DUTY_CYCLE_LIMIT": "Duty cycle limit",
    "RATE_LIMIT_EXCEEDED": "Rate limited",
    "TOO_LARGE": "Message is too large to send",
    "NO_RESPONSE": "No app response",
    "BAD_REQUEST": "Invalid request",
    "NOT_AUTHORIZED": "Not authorized",
    "PKI_FAILED": "Could not send encrypted message",
    "PKI_UNKNOWN_PUBKEY": "Recipient needs your key",
    "PKI_SEND_FAIL_PUBLIC_KEY": "Recipient key unavailable",
    "ADMIN_BAD_SESSION_KEY": "Admin session expired",
    "ADMIN_PUBLIC_KEY_UNAUTHORIZED": "Admin key not authorized",
}


def is_success_reason(error_reason: Any) -> bool:
    return error_reason in (0, "0", "NONE")


def routing_error_key(error_reason: Any) -> str:
    if error_reason is None:
        return ""
    if isinstance(error_reason, int):
        return str(error_reason)
    return str(error_reason).strip().upper()


def ack_type_for_success(is_implicit: bool, is_direct_message: bool) -> str:
    if not is_implicit:
        return ACK_TYPE_EXPLICIT
    if is_direct_message:
        return ACK_TYPE_IMPLICIT_DM
    return ACK_TYPE_IMPLICIT


def ack_type_for_failure(error_reason: Any) -> str:
    key = routing_error_key(error_reason)
    return f"{NAK_PREFIX}{key}" if key else "Nak"


def status_text_for_ack_type(ack_type: Any) -> str:
    if ack_type == ACK_TYPE_EXPLICIT:
        return config.ack_str
    if ack_type == ACK_TYPE_IMPLICIT:
        return config.ack_implicit_str
    if ack_type == ACK_TYPE_IMPLICIT_DM:
        return "Relayed, not confirmed by recipient"
    if isinstance(ack_type, str) and ack_type.startswith(NAK_PREFIX):
        return ROUTING_ERROR_STATUS.get(ack_type[len(NAK_PREFIX):], config.nak_str)
    if ack_type == "Nak":
        return config.nak_str
    return config.ack_unknown_str


def format_sent_prefix(status_text: str) -> str:
    return f"{config.sent_message_prefix} ({status_text}): "
