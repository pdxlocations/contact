from datetime import datetime
import google.protobuf.json_format
from meshtastic import BROADCAST_NUM
from meshtastic.protobuf import mesh_pb2, portnums_pb2

from db_handler import save_message_to_db, update_ack_nak, get_name_from_database, is_chat_archived, update_node_info_in_db
import ui.default_config as config
import globals

ack_naks = {}

# Note "onAckNak" has special meaning to the API, thus the nonstandard naming convention
# See https://github.com/meshtastic/python/blob/master/meshtastic/mesh_interface.py#L462
def onAckNak(packet):
    from ui.curses_ui import draw_messages_window
    request = packet['decoded']['requestId']
    if(request not in ack_naks):
        return

    acknak = ack_naks.pop(request)
    message = globals.all_messages[acknak['channel']][acknak['messageIndex']][1]

    confirm_string = " "
    ack_type = None
    if(packet['decoded']['routing']['errorReason'] == "NONE"):
        if(packet['from'] == globals.myNodeNum): # Ack "from" ourself means implicit ACK
            confirm_string = config.ack_implicit_str
            ack_type = "Implicit"
        else:
            confirm_string = config.ack_str
            ack_type = "Ack"
    else:
        confirm_string = config.nak_str
        ack_type = "Nak"

    globals.all_messages[acknak['channel']][acknak['messageIndex']] = (config.sent_message_prefix + confirm_string + ": ", message)

    update_ack_nak(acknak['channel'], acknak['timestamp'], message, ack_type)

    channel_number = globals.channel_list.index(acknak['channel'])
    if globals.channel_list[channel_number] == globals.channel_list[globals.selected_channel]:
        draw_messages_window()

def on_response_traceroute(packet):
    """on response for trace route"""
    from ui.curses_ui import draw_channel_list, draw_messages_window, add_notification

    refresh_channels = False
    refresh_messages = False

    UNK_SNR = -128 # Value representing unknown SNR

    route_discovery = mesh_pb2.RouteDiscovery()
    route_discovery.ParseFromString(packet["decoded"]["payload"])
    msg_dict = google.protobuf.json_format.MessageToDict(route_discovery)

    msg_str = "Traceroute to:\n"

    route_str = get_name_from_database(packet["to"], 'short') or f"{packet['to']:08x}" # Start with destination of response

    # SNR list should have one more entry than the route, as the final destination adds its SNR also
    lenTowards = 0 if "route" not in msg_dict else len(msg_dict["route"])
    snrTowardsValid = "snrTowards" in msg_dict and len(msg_dict["snrTowards"]) == lenTowards + 1
    if lenTowards > 0: # Loop through hops in route and add SNR if available
        for idx, node_num in enumerate(msg_dict["route"]):
            route_str += " --> " + (get_name_from_database(node_num, 'short') or f"{node_num:08x}") \
                     + " (" + (str(msg_dict["snrTowards"][idx] / 4) if snrTowardsValid and msg_dict["snrTowards"][idx] != UNK_SNR else "?") + "dB)"

    # End with origin of response
    route_str += " --> " + (get_name_from_database(packet["from"], 'short') or f"{packet['from']:08x}") \
             + " (" + (str(msg_dict["snrTowards"][-1] / 4) if snrTowardsValid and msg_dict["snrTowards"][-1] != UNK_SNR else "?") + "dB)"

    msg_str += route_str + "\n" # Print the route towards destination

    # Only if hopStart is set and there is an SNR entry (for the origin) it's valid, even though route might be empty (direct connection)
    lenBack = 0 if "routeBack" not in msg_dict else len(msg_dict["routeBack"])
    backValid = "hopStart" in packet and "snrBack" in msg_dict and len(msg_dict["snrBack"]) == lenBack + 1
    if backValid:
        msg_str += "Back:\n"
        route_str = get_name_from_database(packet["from"], 'short') or f"{packet['from']:08x}" # Start with origin of response

        if lenBack > 0: # Loop through hops in routeBack and add SNR if available
            for idx, node_num in enumerate(msg_dict["routeBack"]):
                route_str += " --> " + (get_name_from_database(node_num, 'short') or f"{node_num:08x}") \
                         + " (" + (str(msg_dict["snrBack"][idx] / 4) if msg_dict["snrBack"][idx] != UNK_SNR else "?") + "dB)"

        # End with destination of response (us)
        route_str += " --> " + (get_name_from_database(packet["to"], 'short') or f"{packet['to']:08x}") \
                 + " (" + (str(msg_dict["snrBack"][-1] / 4) if msg_dict["snrBack"][-1] != UNK_SNR else "?") + "dB)"

        msg_str += route_str + "\n" # Print the route back to us

    if(packet['from'] not in globals.channel_list):
        globals.channel_list.append(packet['from'])
        refresh_channels = True

    if(is_chat_archived(packet['from'])):
        update_node_info_in_db(packet['from'], chat_archived=False)

    channel_number = globals.channel_list.index(packet['from'])

    if globals.channel_list[channel_number] == globals.channel_list[globals.selected_channel]:
        refresh_messages = True
    else:
        add_notification(channel_number)
        refresh_channels = True

    message_from_string = get_name_from_database(packet['from'], type='short') + ":\n"

    if globals.channel_list[channel_number] not in globals.all_messages:
        globals.all_messages[globals.channel_list[channel_number]] = []
    globals.all_messages[globals.channel_list[channel_number]].append((f"{config.message_prefix} {message_from_string}", msg_str))

    if refresh_channels:
        draw_channel_list()
    if refresh_messages:
        draw_messages_window(True)
    save_message_to_db(globals.channel_list[channel_number], packet['from'], msg_str)


def send_message(message, destination=BROADCAST_NUM, channel=0):
    myid = globals.myNodeNum
    send_on_channel = 0
    channel_id = globals.channel_list[channel]
    if isinstance(channel_id, int):
        send_on_channel = 0
        destination = channel_id
    elif isinstance(channel_id, str):
        send_on_channel = channel

    sent_message_data = globals.interface.sendText(
        text=message,
        destinationId=destination,
        wantAck=True,
        wantResponse=False,
        onResponse=onAckNak,
        channelIndex=send_on_channel,
    )

    # Add sent message to the messages dictionary
    if channel_id not in globals.all_messages:
        globals.all_messages[channel_id] = []

    # Handle timestamp logic
    current_timestamp = int(datetime.now().timestamp())  # Get current timestamp
    current_hour = datetime.fromtimestamp(current_timestamp).strftime('%Y-%m-%d %H:00')

    # Retrieve the last timestamp if available
    channel_messages = globals.all_messages[channel_id]
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
        globals.all_messages[channel_id].append((f"-- {current_hour} --", ""))

    globals.all_messages[channel_id].append((config.sent_message_prefix + config.ack_unknown_str + ": ", message))

    timestamp = save_message_to_db(channel_id, myid, message)

    ack_naks[sent_message_data.id] = {'channel': channel_id, 'messageIndex': len(globals.all_messages[channel_id]) - 1, 'timestamp': timestamp}

def send_traceroute():
    r = mesh_pb2.RouteDiscovery()
    globals.interface.sendData(
        r,
        destinationId=globals.node_list[globals.selected_node],
        portNum=portnums_pb2.PortNum.TRACEROUTE_APP,
        wantResponse=True,
        onResponse=on_response_traceroute,
        channelIndex=0,
        hopLimit=3,
    )
