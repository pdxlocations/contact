from datetime import datetime
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

from contact.utilities.singleton import ui_state, interface_state

ack_naks: Dict[str, Dict[str, Any]] = {}  # requestId -> {channel, messageIndex, timestamp}


# Note "onAckNak" has special meaning to the API, thus the nonstandard naming convention
# See https://github.com/meshtastic/python/blob/master/meshtastic/mesh_interface.py#L462
def onAckNak(packet: Dict[str, Any]) -> None:
    """
    Handles incoming ACK/NAK response packets.
    """
    from contact.ui.contact_ui import draw_messages_window

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
        config.sent_message_prefix + confirm_string + ": ",
        message,
    )

    update_ack_nak(acknak["channel"], acknak["timestamp"], message, ack_type)

    channel_number = ui_state.channel_list.index(acknak["channel"])
    if ui_state.channel_list[channel_number] == ui_state.channel_list[ui_state.selected_channel]:
        draw_messages_window()


def on_response_traceroute(packet: Dict[str, Any]) -> None:
    """
    Handle traceroute response packets and render the route visually in the UI.
    """
    from contact.ui.contact_ui import draw_channel_list, draw_messages_window, add_notification

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

    # SNR list should have one more entry than the route, as the final destination adds its SNR also
    lenTowards = 0 if "route" not in msg_dict else len(msg_dict["route"])
    snrTowardsValid = "snrTowards" in msg_dict and len(msg_dict["snrTowards"]) == lenTowards + 1
    if lenTowards > 0:  # Loop through hops in route and add SNR if available
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

    # End with origin of response
    route_str += (
        " --> "
        + (get_name_from_database(packet["from"], "short") or f"{packet['from']:08x}")
        + " ("
        + (str(msg_dict["snrTowards"][-1] / 4) if snrTowardsValid and msg_dict["snrTowards"][-1] != UNK_SNR else "?")
        + "dB)"
    )

    msg_str += route_str + "\n"  # Print the route towards destination

    # Only if hopStart is set and there is an SNR entry (for the origin) it's valid, even though route might be empty (direct connection)
    lenBack = 0 if "routeBack" not in msg_dict else len(msg_dict["routeBack"])
    backValid = "hopStart" in packet and "snrBack" in msg_dict and len(msg_dict["snrBack"]) == lenBack + 1
    if backValid:
        msg_str += "Back:\n"
        route_str = (
            get_name_from_database(packet["from"], "short") or f"{packet['from']:08x}"
        )  # Start with origin of response

        if lenBack > 0:  # Loop through hops in routeBack and add SNR if available
            for idx, node_num in enumerate(msg_dict["routeBack"]):
                route_str += (
                    " --> "
                    + (get_name_from_database(node_num, "short") or f"{node_num:08x}")
                    + " ("
                    + (str(msg_dict["snrBack"][idx] / 4) if msg_dict["snrBack"][idx] != UNK_SNR else "?")
                    + "dB)"
                )

        # End with destination of response (us)
        route_str += (
            " --> "
            + (get_name_from_database(packet["to"], "short") or f"{packet['to']:08x}")
            + " ("
            + (str(msg_dict["snrBack"][-1] / 4) if msg_dict["snrBack"][-1] != UNK_SNR else "?")
            + "dB)"
        )

        msg_str += route_str + "\n"  # Print the route back to us

    if packet["from"] not in ui_state.channel_list:
        ui_state.channel_list.append(packet["from"])
        refresh_channels = True

    if is_chat_archived(packet["from"]):
        update_node_info_in_db(packet["from"], chat_archived=False)

    channel_number = ui_state.channel_list.index(packet["from"])

    if ui_state.channel_list[channel_number] == ui_state.channel_list[ui_state.selected_channel]:
        refresh_messages = True
    else:
        add_notification(channel_number)
        refresh_channels = True

    message_from_string = get_name_from_database(packet["from"], type="short") + ":\n"

    if ui_state.channel_list[channel_number] not in ui_state.all_messages:
        ui_state.all_messages[ui_state.channel_list[channel_number]] = []
    ui_state.all_messages[ui_state.channel_list[channel_number]].append(
        (f"{config.message_prefix} {message_from_string}", msg_str)
    )

    if refresh_channels:
        draw_channel_list()
    if refresh_messages:
        draw_messages_window(True)
    save_message_to_db(ui_state.channel_list[channel_number], packet["from"], msg_str)


def send_message(message: str, destination: int = BROADCAST_NUM, channel: int = 0) -> None:
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

    sent_message_data = interface_state.interface.sendText(
        text=message,
        destinationId=destination,
        wantAck=True,
        wantResponse=False,
        onResponse=onAckNak,
        channelIndex=send_on_channel,
    )

    # Add sent message to the messages dictionary
    if channel_id not in ui_state.all_messages:
        ui_state.all_messages[channel_id] = []

    # Handle timestamp logic
    current_timestamp = int(datetime.now().timestamp())  # Get current timestamp
    current_hour = datetime.fromtimestamp(current_timestamp).strftime("%Y-%m-%d %H:00")

    # Retrieve the last timestamp if available
    channel_messages = ui_state.all_messages[channel_id]
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
        ui_state.all_messages[channel_id].append((f"-- {current_hour} --", ""))

    ui_state.all_messages[channel_id].append((config.sent_message_prefix + config.ack_unknown_str + ": ", message))

    timestamp = save_message_to_db(channel_id, myid, message)

    ack_naks[sent_message_data.id] = {
        "channel": channel_id,
        "messageIndex": len(ui_state.all_messages[channel_id]) - 1,
        "timestamp": timestamp,
    }


def send_traceroute() -> None:
    """
    Sends a RouteDiscovery protobuf to the selected node.
    """
    r = mesh_pb2.RouteDiscovery()
    interface_state.interface.sendData(
        r,
        destinationId=ui_state.node_list[ui_state.selected_node],
        portNum=portnums_pb2.PortNum.TRACEROUTE_APP,
        wantResponse=True,
        onResponse=on_response_traceroute,
        channelIndex=0,
        hopLimit=3,
    )
