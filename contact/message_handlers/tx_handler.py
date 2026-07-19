import time

from typing import Any, Dict

import google.protobuf.json_format
from meshtastic import BROADCAST_NUM
from meshtastic.protobuf import mesh_pb2, portnums_pb2

from contact.utilities.db_handler import (
    save_message_to_db,
    update_ack_nak,
    get_name_from_database,
    is_chat_archived,
    update_node_info_in_db,
)
import contact.ui.default_config as config

from contact.utilities.singleton import ui_state, interface_state, app_state

from contact.utilities.utils import add_new_message

ack_naks: Dict[str, Dict[str, Any]] = {}  # requestId -> {channel, messageIndex, timestamp}


# Note "onAckNak" has special meaning to the API, thus the nonstandard naming convention
# See https://github.com/meshtastic/python/blob/master/meshtastic/mesh_interface.py#L462
def onAckNak(packet: Dict[str, Any]) -> None:
    """
    Handles incoming ACK/NAK response packets.
    """
    from contact.ui.contact_ui import request_ui_redraw

    with app_state.lock:
        request = packet["decoded"]["requestId"]
        if request not in ack_naks:
            return

        acknak = ack_naks.pop(request)
        message = ui_state.all_messages[acknak["channel"]][acknak["messageIndex"]][1]

        confirm_string = " "
        ack_type = None
        if packet["decoded"]["routing"]["errorReason"] == "NONE":
            if packet["from"] == interface_state.myNodeNum:  # Ack "from" ourself means implicit ACK
                confirm_string = config.ack_implicit_str
                ack_type = "Implicit"
            else:
                confirm_string = config.ack_str
                ack_type = "Ack"
        else:
            confirm_string = config.nak_str
            ack_type = "Nak"

        ui_state.all_messages[acknak["channel"]][acknak["messageIndex"]] = (
            time.strftime("[%H:%M:%S] ") + config.sent_message_prefix + confirm_string + ": ",
            message,
        )

        update_ack_nak(acknak["channel"], acknak["timestamp"], acknak["dbMessage"], ack_type)

        channel_number = ui_state.channel_list.index(acknak["channel"])
        if ui_state.channel_list[channel_number] == ui_state.channel_list[ui_state.selected_channel]:
            request_ui_redraw(messages=True)


def on_response_traceroute(packet: Dict[str, Any]) -> None:
    """
    Handle traceroute response packets and render the route visually in the UI.
    """
    from contact.ui.contact_ui import add_notification, request_ui_redraw

    with app_state.lock:
        refresh_channels = False
        refresh_messages = False

        UNK_SNR = -128  # Value representing unknown SNR

        route_discovery = mesh_pb2.RouteDiscovery()
        route_discovery.ParseFromString(packet["decoded"]["payload"])
        msg_dict = google.protobuf.json_format.MessageToDict(route_discovery)

        msg_str = "Traceroute to:\n"

        route_str = (
            get_name_from_database(packet["to"], "short") or f"{packet['to']:08x}"
        )  # Start with destination of response

        lenTowards = 0 if "route" not in msg_dict else len(msg_dict["route"])
        snrTowardsValid = "snrTowards" in msg_dict and len(msg_dict["snrTowards"]) == lenTowards + 1
        if lenTowards > 0:
            for idx, node_num in enumerate(msg_dict["route"]):
                route_str += (
                    " --> "
                    + (get_name_from_database(node_num, "short") or f"{node_num:08x}")
                    + " ("
                    + (
                        str(msg_dict["snrTowards"][idx] / 4)
                        if snrTowardsValid and msg_dict["snrTowards"][idx] != UNK_SNR
                        else "?"
                    )
                    + "dB)"
                )

        route_str += (
            " --> "
            + (get_name_from_database(packet["from"], "short") or f"{packet['from']:08x}")
            + " ("
            + (str(msg_dict["snrTowards"][-1] / 4) if snrTowardsValid and msg_dict["snrTowards"][-1] != UNK_SNR else "?")
            + "dB)"
        )

        msg_str += route_str + "\n"

        lenBack = 0 if "routeBack" not in msg_dict else len(msg_dict["routeBack"])
        backValid = "hopStart" in packet and "snrBack" in msg_dict and len(msg_dict["snrBack"]) == lenBack + 1
        if backValid:
            msg_str += "Back:\n"
            route_str = get_name_from_database(packet["from"], "short") or f"{packet['from']:08x}"

            if lenBack > 0:
                for idx, node_num in enumerate(msg_dict["routeBack"]):
                    route_str += (
                        " --> "
                        + (get_name_from_database(node_num, "short") or f"{node_num:08x}")
                        + " ("
                        + (str(msg_dict["snrBack"][idx] / 4) if msg_dict["snrBack"][idx] != UNK_SNR else "?")
                        + "dB)"
                    )

            route_str += (
                " --> "
                + (get_name_from_database(packet["to"], "short") or f"{packet['to']:08x}")
                + " ("
                + (str(msg_dict["snrBack"][-1] / 4) if msg_dict["snrBack"][-1] != UNK_SNR else "?")
                + "dB)"
            )

            msg_str += route_str + "\n"

        if packet["from"] not in ui_state.channel_list:
            ui_state.channel_list.append(packet["from"])
            refresh_channels = True

        if is_chat_archived(packet["from"]):
            update_node_info_in_db(packet["from"], chat_archived=False)

        channel_number = ui_state.channel_list.index(packet["from"])
        channel_id = ui_state.channel_list[channel_number]

        if channel_id == ui_state.channel_list[ui_state.selected_channel]:
            refresh_messages = True
        else:
            add_notification(channel_number)
            refresh_channels = True

        message_from_string = get_name_from_database(packet["from"], type="short") + ":\n"

        add_new_message(channel_id, f"{config.message_prefix} {message_from_string}", msg_str)

        if refresh_channels:
            request_ui_redraw(channels=True)
        if refresh_messages:
            request_ui_redraw(messages=True, scroll_messages_to_bottom=True)

        save_message_to_db(channel_id, packet["from"], msg_str)

def send_message(
    message: str,
    destination: int = BROADCAST_NUM,
    channel: int = 0,
    reply_id: int | None = None,
    reply_context: str = "",
) -> None:
    """
    Sends a chat message using the selected channel.
    """
    myid = interface_state.myNodeNum
    send_on_channel = 0
    channel_id = ui_state.channel_list[channel]
    if isinstance(channel_id, int):
        send_on_channel = 0
        destination = channel_id
    elif isinstance(channel_id, str):
        send_on_channel = channel

    send_kwargs = {
        "text": message,
        "destinationId": destination,
        "wantAck": True,
        "wantResponse": False,
        "onResponse": onAckNak,
        "channelIndex": send_on_channel,
    }
    if reply_id is not None:
        send_kwargs["replyId"] = reply_id
    sent_message_data = interface_state.interface.sendText(**send_kwargs)

    add_new_message(
        channel_id,
        config.sent_message_prefix + config.ack_unknown_str + ": ",
        f"{reply_context}{message}",
        packet_id=sent_message_data.id,
    )

    timestamp = save_message_to_db(channel_id, myid, message, packet_id=sent_message_data.id, reply_id=reply_id)

    ack_naks[sent_message_data.id] = {
        "channel": channel_id,
        "messageIndex": len(ui_state.all_messages[channel_id]) - 1,
        "timestamp": timestamp,
        "dbMessage": message,
    }


def send_traceroute() -> None:
    """
    Sends a RouteDiscovery protobuf to the selected node.
    """

    channel_id = ui_state.node_list[ui_state.selected_node]
    add_new_message(channel_id, f"{config.message_prefix} Sent Traceroute", "")

    r = mesh_pb2.RouteDiscovery()
    interface_state.interface.sendData(
        r,
        destinationId=channel_id,
        portNum=portnums_pb2.PortNum.TRACEROUTE_APP,
        wantResponse=True,
        onResponse=on_response_traceroute,
        channelIndex=0,
        hopLimit=3,
    )
