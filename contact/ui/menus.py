import base64
import logging
import os
from collections import OrderedDict

from typing import Any, Union, Dict

from google.protobuf.message import Message
from meshtastic.protobuf import channel_pb2, config_pb2, module_config_pb2


locals_dir = os.path.dirname(os.path.abspath(__file__))
translation_file = os.path.join(locals_dir, "localisations", "en.ini")


def encode_if_bytes(value: Any) -> str:
    """Encode byte values to base64 string."""
    if isinstance(value, bytes):
        return base64.b64encode(value).decode("utf-8")
    return value


def extract_fields(
    message_instance: Message, current_config: Union[Message, Dict[str, Any], None] = None
) -> Dict[str, Any]:
    if isinstance(current_config, dict):  # Handle dictionaries
        return {key: (None, encode_if_bytes(current_config.get(key, "Not Set"))) for key in current_config}

    if not hasattr(message_instance, "DESCRIPTOR"):
        return {}

    menu = {}
    fields = message_instance.DESCRIPTOR.fields
    for field in fields:
        skip_fields = [
            "sessionkey",
            "ChannelSettings.channel_num",
            "ChannelSettings.id",
            "LoRaConfig.ignore_incoming",
            "DeviceUIConfig.version",
        ]
        if any(skip_field in field.full_name for skip_field in skip_fields):
            continue

        if field.message_type:  # Nested message
            nested_instance = getattr(message_instance, field.name)
            nested_config = getattr(current_config, field.name, None) if current_config else None
            menu[field.name] = extract_fields(nested_instance, nested_config)
        elif field.enum_type:  # Handle enum fields
            current_value = getattr(current_config, field.name, "Not Set") if current_config else "Not Set"
            if isinstance(current_value, int):  # If the value is a number, map it to its name
                enum_value = field.enum_type.values_by_number.get(current_value)
                if enum_value:  # Check if the enum value exists
                    current_value_name = f"{enum_value.name}"
                else:
                    current_value_name = f"Unknown ({current_value})"
                menu[field.name] = (field, current_value_name)
            else:
                menu[field.name] = (field, current_value)  # Non-integer values
        else:  # Handle other field types
            current_value = getattr(current_config, field.name, "Not Set") if current_config else "Not Set"
            menu[field.name] = (field, encode_if_bytes(current_value))
    return menu


def generate_menu_from_protobuf(interface: object) -> Dict[str, Any]:
    """
    Builds the full settings menu structure from the protobuf definitions.
    """
    menu_structure = {"Main Menu": {}}

    # Add User Settings
    current_node_info = interface.getMyNodeInfo() if interface else None

    if current_node_info:
        current_user_config = current_node_info.get("user", None)
        if current_user_config and isinstance(current_user_config, dict):
            menu_structure["Main Menu"]["User Settings"] = {
                "longName": (None, current_user_config.get("longName", "Not Set")),
                "shortName": (None, current_user_config.get("shortName", "Not Set")),
                "isLicensed": (None, current_user_config.get("isLicensed", "False")),
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
                channel_config = extract_fields(channel, current_channel.settings)
                menu_structure["Main Menu"]["Channels"][f"Channel {i + 1}"] = channel_config

    # Add Radio Settings
    radio = config_pb2.Config()
    current_radio_config = interface.localNode.localConfig if interface else None
    menu_structure["Main Menu"]["Radio Settings"] = extract_fields(radio, current_radio_config)

    # Add Lat/Lon/Alt
    position_data = {
        "latitude": (None, current_node_info["position"].get("latitude", 0.0)),
        "longitude": (None, current_node_info["position"].get("longitude", 0.0)),
        "altitude": (None, current_node_info["position"].get("altitude", 0)),
    }

    existing_position_menu = menu_structure["Main Menu"]["Radio Settings"].get("position", {})
    ordered_position_menu = OrderedDict()

    for key, value in existing_position_menu.items():
        if key == "fixed_position":  # Insert before or after a specific key
            ordered_position_menu[key] = value
            ordered_position_menu.update(position_data)  # Insert Lat/Lon/Alt **right here**
        else:
            ordered_position_menu[key] = value

    menu_structure["Main Menu"]["Radio Settings"]["position"] = ordered_position_menu

    # Add Module Settings
    module = module_config_pb2.ModuleConfig()
    current_module_config = interface.localNode.moduleConfig if interface else None
    menu_structure["Main Menu"]["Module Settings"] = extract_fields(module, current_module_config)

    # Add App Settings
    menu_structure["Main Menu"]["App Settings"] = {"Open": "app_settings"}

    # Additional settings options
    menu_structure["Main Menu"].update(
        {
            "Export Config File": None,
            "Load Config File": None,
            "Config URL": None,
            "Reboot": None,
            "Reset Node DB": None,
            "Shutdown": None,
            "Factory Reset": None,
            "Exit": None,
        }
    )

    return menu_structure
