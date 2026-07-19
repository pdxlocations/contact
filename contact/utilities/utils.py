import datetime
import re
import time
from typing import Optional, Union
from google.protobuf.message import DecodeError

from meshtastic import protocols
from meshtastic.protobuf import config_pb2, mesh_pb2, portnums_pb2
import contact.ui.default_config as config
from contact.utilities.singleton import ui_state, interface_state
import contact.utilities.telemetry_beautifier as tb


def _get_channel_name(device_channel, node):
    if device_channel.settings.name:
        return device_channel.settings.name

    lora_config = node.localConfig.lora
    modem_preset_enum = lora_config.modem_preset
    modem_preset_string = config_pb2._CONFIG_LORACONFIG_MODEMPRESET.values_by_number[modem_preset_enum].name
    return convert_to_camel_case(modem_preset_string)


def get_channels():
    """Retrieve channels from the node and rebuild named channel state."""
    node = interface_state.interface.getNode("^local")
    device_channels = node.channels
    previous_channel_list = list(ui_state.channel_list)
    previous_messages = dict(ui_state.all_messages)

    named_channels = []

    for device_channel in device_channels:
        if device_channel.role:
            named_channels.append(_get_channel_name(device_channel, node))

    previous_named_channels = [channel for channel in previous_channel_list if isinstance(channel, str)]
    preserved_direct_channels = [channel for channel in previous_channel_list if isinstance(channel, int)]
    rebuilt_messages = {}

    for index, channel_name in enumerate(named_channels):
        previous_name = previous_named_channels[index] if index < len(previous_named_channels) else channel_name
        if previous_name in previous_messages:
            rebuilt_messages[channel_name] = previous_messages[previous_name]
        elif channel_name in previous_messages:
            rebuilt_messages[channel_name] = previous_messages[channel_name]
        else:
            rebuilt_messages[channel_name] = []

    for channel in preserved_direct_channels:
        if channel in previous_messages:
            rebuilt_messages[channel] = previous_messages[channel]

    ui_state.channel_list = named_channels + preserved_direct_channels
    ui_state.all_messages = rebuilt_messages
    if ui_state.channel_list:
        ui_state.selected_channel = max(0, min(ui_state.selected_channel, len(ui_state.channel_list) - 1))

    return ui_state.channel_list


def get_node_list():
    if interface_state.interface.nodes:
        my_node_num = interface_state.myNodeNum

        def node_sort(node):
            if config.node_sort == "lastHeard":
                return -node["lastHeard"] if ("lastHeard" in node and isinstance(node["lastHeard"], int)) else 0
            elif config.node_sort == "name":
                return node["user"]["longName"]
            elif config.node_sort == "hops":
                return node["hopsAway"] if "hopsAway" in node else 100
            else:
                return node

        sorted_nodes = sorted(interface_state.interface.nodes.values(), key=node_sort)

        # Move favorite nodes to the beginning
        sorted_nodes = sorted(
            sorted_nodes, key=lambda node: node["isFavorite"] if "isFavorite" in node else False, reverse=True
        )

        # Move ignored nodes to the end
        sorted_nodes = sorted(sorted_nodes, key=lambda node: node["isIgnored"] if "isIgnored" in node else False)

        node_list = [node["num"] for node in sorted_nodes if node["num"] != my_node_num]
        return [my_node_num] + node_list  # Ensuring your node is always first
    return []


def refresh_node_list():
    new_node_list = get_node_list()
    if new_node_list != ui_state.node_list:
        ui_state.node_list = new_node_list
        return True
    return False


def get_nodeNum():
    myinfo = interface_state.interface.getMyNodeInfo()
    myNodeNum = myinfo["num"]
    return myNodeNum


def decimal_to_hex(decimal_number):
    return f"!{decimal_number:08x}"


def convert_to_camel_case(string):
    words = string.split("_")
    camel_case_string = "".join(word.capitalize() for word in words)
    return camel_case_string


def get_time_val_units(time_delta):
    value = 0
    unit = ""

    if time_delta.days > 365:
        value = time_delta.days // 365
        unit = "y"
    elif time_delta.days > 30:
        value = time_delta.days // 30
        unit = "mon"
    elif time_delta.days > 7:
        value = time_delta.days // 7
        unit = "w"
    elif time_delta.days > 0:
        value = time_delta.days
        unit = "d"
    elif time_delta.seconds > 3600:
        value = time_delta.seconds // 3600
        unit = "h"
    elif time_delta.seconds > 60:
        value = time_delta.seconds // 60
        unit = "min"
    else:
        value = time_delta.seconds
        unit = "s"
    return (value, unit)


def get_readable_duration(seconds):
    delta = datetime.timedelta(seconds=seconds)
    val, units = get_time_val_units(delta)
    return f"{val} {units}"


def get_time_ago(timestamp):
    now = datetime.datetime.now()
    dt = datetime.datetime.fromtimestamp(timestamp)
    delta = now - dt

    value, unit = get_time_val_units(delta)
    if unit != "s":
        return f"{value} {unit} ago"
    return "now"


REPLY_EXCERPT_LENGTH = 5


def build_reply_prefix(prefix: str, message: str) -> str:
    """Create Contact's local display marker for a native Meshtastic reply."""
    sender_text = re.sub(r"^\[[^]]+\]\s*", "", prefix).strip()
    sender_text = re.sub(r"^(?:>>|<<)\s*(?:\[[^]]+\]\s*)?", "", sender_text)
    sender_match = re.search(r"(.+?)\s*:\s*$", sender_text)
    sender = sender_match.group(1).strip() if sender_match else "me"
    excerpt = " ".join(message.replace("\x00", "").split())[:REPLY_EXCERPT_LENGTH]
    return f"<Re: {sender}: {excerpt}> "


def get_reply_context(reply_id):
    """Find the locally displayed message referred to by a Meshtastic reply ID."""
    for channel, packet_ids in ui_state.message_packet_ids.items():
        for index, packet_id in enumerate(packet_ids):
            if packet_id == reply_id and index < len(ui_state.all_messages.get(channel, [])):
                prefix, message = ui_state.all_messages[channel][index]
                return build_reply_prefix(prefix, message)
    return ""


def add_new_message(channel_id, prefix, message, packet_id=None):
    if channel_id not in ui_state.all_messages:
        ui_state.all_messages[channel_id] = []

    packet_ids = ui_state.message_packet_ids.setdefault(channel_id, [])
    while len(packet_ids) < len(ui_state.all_messages[channel_id]):
        packet_ids.append(None)

    # Timestamp handling
    current_timestamp = time.time()
    current_hour = datetime.datetime.fromtimestamp(current_timestamp).strftime("%Y-%m-%d %H:00")

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
        packet_ids.append(None)

    # Add the message
    ts_str = time.strftime("[%H:%M:%S] ")
    ui_state.all_messages[channel_id].append((f"{ts_str}{prefix}", message))
    packet_ids.append(packet_id)


def parse_protobuf(packet: dict) -> Union[str, dict]:
    """Attempt to parse a decoded payload using the registered protobuf handler."""
    try:
        decoded = packet.get("decoded") or {}
        portnum = decoded.get("portnum")
        payload = decoded.get("payload")

        if isinstance(payload, str):
            return payload

        # These portnumbers carry information visible elswhere in the app, so we just note them in the logs
        if portnum == "TEXT_MESSAGE_APP":
            return "✉️"
        elif portnum == "NODEINFO_APP":
            return "Name identification payload"
        elif portnum == "TRACEROUTE_APP":
            return "Traceroute payload"

        handler = protocols.get(portnums_pb2.PortNum.Value(portnum)) if portnum is not None else None
        if handler is not None and handler.protobufFactory is not None:
            try:
                pb = handler.protobufFactory()
                pb.ParseFromString(bytes(payload))

                # If we have position payload
                if portnum == "POSITION_APP":
                    return tb.get_chunks(str(pb))

                # Part of TELEMETRY_APP portnum
                if hasattr(pb, "device_metrics") and pb.HasField("device_metrics"):
                    return tb.get_chunks(str(pb.device_metrics))

                # Part of TELEMETRY_APP portnum
                if hasattr(pb, "environment_metrics") and pb.HasField("environment_metrics"):
                    return tb.get_chunks(str(pb.environment_metrics))

                # For other data, without implemented beautification, fallback to just printing the object
                return str(pb).replace("\n", " ").replace("\r", " ").strip()

            except DecodeError:
                return payload

        # return payload

    except Exception:
        return payload
