import globals
import datetime
from meshtastic.protobuf import config_pb2
import default_config as config

def get_channels():
    """Retrieve channels from the node and update globals.channel_list and globals.all_messages."""
    node = globals.interface.getNode('^local')
    device_channels = node.channels

    # Clear and rebuild channel list
    # globals.channel_list = []

    for device_channel in device_channels:
        if device_channel.role:
            # Use the channel name if available, otherwise use the modem preset
            if device_channel.settings.name:
                channel_name = device_channel.settings.name
            else:
                # If channel name is blank, use the modem preset
                lora_config = node.localConfig.lora
                modem_preset_enum = lora_config.modem_preset
                modem_preset_string = config_pb2._CONFIG_LORACONFIG_MODEMPRESET.values_by_number[modem_preset_enum].name
                channel_name = convert_to_camel_case(modem_preset_string)

            # Add channel to globals.channel_list if not already present
            if channel_name not in globals.channel_list:
                globals.channel_list.append(channel_name)

            # Initialize globals.all_messages[channel_name] if it doesn't exist
            if channel_name not in globals.all_messages:
                globals.all_messages[channel_name] = []


    return globals.channel_list

def get_node_list():
    if globals.interface.nodes:
        my_node_num = globals.myNodeNum

        def node_sort(node):
            if(config.node_sort == 'lastHeard'):
                return -node['lastHeard'] if ('lastHeard' in node and isinstance(node['lastHeard'], int)) else 0
            elif(config.node_sort == "name"):
                return node['user']['longName']
            elif(config.node_sort == "hops"):
                return node['hopsAway'] if 'hopsAway' in node else 100
            else:
                return node
        sorted_nodes = sorted(globals.interface.nodes.values(), key = node_sort)
        node_list = [node['num'] for node in sorted_nodes if node['num'] != my_node_num]
        return [my_node_num] + node_list  # Ensuring your node is always first
    return []

def refresh_node_list():
    new_node_list = get_node_list()
    if new_node_list != globals.node_list:
        globals.node_list = new_node_list
        return True
    return False

def get_nodeNum():
    myinfo = globals.interface.getMyNodeInfo()
    myNodeNum = myinfo['num']
    return myNodeNum

def decimal_to_hex(decimal_number):
    return f"!{decimal_number:08x}"

def convert_to_camel_case(string):
    words = string.split('_')
    camel_case_string = ''.join(word.capitalize() for word in words)
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
    delta = datetime.timedelta(seconds = seconds)
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

