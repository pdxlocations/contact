import datetime
import time
from typing import Optional, Union
from google.protobuf.message import DecodeError

from meshtastic import protocols
from meshtastic.protobuf import config_pb2, mesh_pb2, portnums_pb2
import contact.ui.default_config as config
from contact.utilities.singleton import ui_state, interface_state


def get_channels():
    """Retrieve channels from the node and update ui_state.channel_list and ui_state.all_messages."""
    node = interface_state.interface.getNode("^local")
    device_channels = node.channels

    # Clear and rebuild channel list
    # ui_state.channel_list = []

    for device_channel in device_channels:
        if device_channel.role:
            # Use the channel name if available, otherwise use the modem preset
            if device_channel.settings.name:
                channel_name = device_channel.settings.name
            else:
                # If channel name is blank, use the modem preset
                lora_config = node.localConfig.lora
                modem_preset_enum = lora_config.modem_preset
                modem_preset_string = config_pb2._CONFIG_LORACONFIG_MODEMPRESET.values_by_number[
                    modem_preset_enum
                ].name
                channel_name = convert_to_camel_case(modem_preset_string)

            # Add channel to ui_state.channel_list if not already present
            if channel_name not in ui_state.channel_list:
                ui_state.channel_list.append(channel_name)

            # Initialize ui_state.all_messages[channel_name] if it doesn't exist
            if channel_name not in ui_state.all_messages:
                ui_state.all_messages[channel_name] = []

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


def add_new_message(channel_id, prefix, message):
    if channel_id not in ui_state.all_messages:
        ui_state.all_messages[channel_id] = []

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

    # Add the message
    ui_state.all_messages[channel_id].append((prefix, message))


def parse_protobuf(packet: dict) -> Union[str, dict]:
    """Attempt to parse a decoded payload using the registered protobuf handler."""
    try:
        decoded = packet.get("decoded") or {}
        portnum = decoded.get("portnum")
        payload = decoded.get("payload")

        if isinstance(payload, str):
            return payload

        handler = protocols.get(portnums_pb2.PortNum.Value(portnum)) if portnum is not None else None
        if handler is not None and handler.protobufFactory is not None:
            try:
                pb = handler.protobufFactory()
                pb.ParseFromString(bytes(payload))
                return str(pb).replace("\n", " ").replace("\r", " ").strip()
            except DecodeError:
                return payload

        return payload

    except Exception:
        return payload
