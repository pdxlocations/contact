from collections import OrderedDict
from meshtastic.protobuf import config_pb2, module_config_pb2, channel_pb2
import logging
import base64


FIELD_EXCLUSION_MAP = {
    "global": {"sessionkey"},
    "channel": {"channel_num", "id"},
    "radio": {"ignore_incoming"},
    "module": None
}

def extract_fields(message_instance, current_config=None, parent_context=None, exclusion_map=None):
    if isinstance(current_config, dict):  # Handle dictionaries
        return {key: (None, current_config.get(key, "Not Set")) for key in current_config}
    
    if not hasattr(message_instance, "DESCRIPTOR"):
        return {}

    if exclusion_map is None:
        exclusion_map = FIELD_EXCLUSION_MAP  # Use default if not provided

    # Combine global exclusions with context-specific exclusions
    global_exclusions = exclusion_map.get("global", set())
    context_exclusions = exclusion_map.get(parent_context, set())
    total_exclusions = global_exclusions.union(context_exclusions)

    menu = {}
    fields = message_instance.DESCRIPTOR.fields

    for field in fields:
        if field.name in total_exclusions:
            continue

        if field.message_type:  # Nested message
            nested_instance = getattr(message_instance, field.name)
            nested_config = getattr(current_config, field.name, None) if current_config else None
            menu[field.name] = extract_fields(
                nested_instance,
                nested_config,
                parent_context=parent_context,
                exclusion_map=exclusion_map
            )
        elif field.enum_type:  # Handle enum fields
            current_value = getattr(current_config, field.name, "Not Set") if current_config else "Not Set"
            if isinstance(current_value, int):  # Map enum number to name
                enum_value = field.enum_type.values_by_number.get(current_value)
                current_value_name = f"{enum_value.name}" if enum_value else f"Unknown ({current_value})"
                menu[field.name] = (field, current_value_name)
            else:
                menu[field.name] = (field, current_value)
        else:  # Other field types
            current_value = getattr(current_config, field.name, "Not Set") if current_config else "Not Set"
            menu[field.name] = (field, current_value)

    return menu


def generate_menu_from_protobuf(interface):
# Function to generate the menu structure from protobuf messages
    menu_structure = {"Main Menu": {}}

    # Add User Settings
    current_node_info = interface.getMyNodeInfo() if interface else None

    if current_node_info:

        current_user_config = current_node_info.get("user", None)
        if current_user_config and isinstance(current_user_config, dict):

            menu_structure["Main Menu"]["User Settings"] = {
                "longName": (None, current_user_config.get("longName", "Not Set")),
                "shortName": (None, current_user_config.get("shortName", "Not Set")),
                "isLicensed": (None, current_user_config.get("isLicensed", "False"))
            }
        else:
            logging.info("User settings not found in Node Info")
            menu_structure["Main Menu"]["User Settings"] = "No user settings available"
    else:
        logging.info("Node Info not available")
        menu_structure["Main Menu"]["User Settings"] = "Node Info not available"

    # Add Channels
    channel = channel_pb2.ChannelSettings()
    menu_structure["Main Menu"]["Channels"] = {}
    if interface:
        for i in range(8):
            current_channel = interface.localNode.getChannelByChannelIndex(i)
            if current_channel:
                # Apply 'channel' context here
                channel_config = extract_fields(
                    channel,
                    current_channel.settings,
                    parent_context="channel",  # Dynamic context
                    exclusion_map=FIELD_EXCLUSION_MAP  # Pass exclusion map
                )
                # Convert 'psk' to Base64
                channel_config["psk"] = (
                    channel_config["psk"][0],
                    base64.b64encode(channel_config["psk"][1]).decode('utf-8')
                )
                menu_structure["Main Menu"]["Channels"][f"Channel {i + 1}"] = channel_config

    # Add Radio Settings
    radio = config_pb2.Config()
    current_radio_config = interface.localNode.localConfig if interface else None
    menu_structure["Main Menu"]["Radio Settings"] = extract_fields(radio, current_radio_config)

    # Add Lat/Lon/Alt
    position_data = {
        "latitude": (None, current_node_info["position"].get("latitude", 0.0)),
        "longitude": (None, current_node_info["position"].get("longitude", 0.0)),
        "altitude": (None, current_node_info["position"].get("altitude", 0))
    }

    # Get existing position menu items
    existing_position_menu = menu_structure["Main Menu"]["Radio Settings"].get("position", {})

    # Create an ordered position menu with Lat/Lon/Alt inserted in the middle
    ordered_position_menu = OrderedDict()

    for key, value in existing_position_menu.items():
        if key == "fixed_position":  # Insert before or after a specific key
            ordered_position_menu[key] = value
            ordered_position_menu.update(position_data)  # Insert Lat/Lon/Alt **right here**
        else:
            ordered_position_menu[key] = value

    # Update the menu with the new order
    menu_structure["Main Menu"]["Radio Settings"] = extract_fields(
        radio,
        current_radio_config,
        parent_context="radio",
        exclusion_map=FIELD_EXCLUSION_MAP
    )

    # Add Module Settings
    module = module_config_pb2.ModuleConfig()
    current_module_config = interface.localNode.moduleConfig if interface else None

    menu_structure["Main Menu"]["Module Settings"] = extract_fields(
        module,
        current_module_config,
        parent_context="module",  # Apply 'module' context
        exclusion_map=FIELD_EXCLUSION_MAP
)
    # Add App Settings
    menu_structure["Main Menu"]["App Settings"] = {"Open": "app_settings"}

    # Add additional settings options
    menu_structure["Main Menu"]["Export Config"] = None
    menu_structure["Main Menu"]["Load Config"] = None
    menu_structure["Main Menu"]["Reboot"] = None
    menu_structure["Main Menu"]["Reset Node DB"] = None
    menu_structure["Main Menu"]["Shutdown"] = None
    menu_structure["Main Menu"]["Factory Reset"] = None

    # Add Exit option
    menu_structure["Main Menu"]["Exit"] = None

    return menu_structure