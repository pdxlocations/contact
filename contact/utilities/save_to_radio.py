from meshtastic.protobuf import channel_pb2
from google.protobuf.message import Message
import logging
import base64
import time


def save_changes(interface, modified_settings, menu_state):
    """
    Save changes to the device based on modified settings.
    :param interface: Meshtastic interface instance
    :param menu_path: Current menu path
    :param modified_settings: Dictionary of modified settings
    """
    try:
        if not modified_settings:
            logging.info("No changes to save. modified_settings is empty.")
            return

        node = interface.getNode("^local")
        admin_key_backup = None
        if "admin_key" in modified_settings:
            # Get reference to security config
            security_config = node.localConfig.security
            admin_keys = modified_settings["admin_key"]

            # Filter out empty keys
            valid_keys = [key for key in admin_keys if key and key.strip() and key != b""]

            if not valid_keys:
                logging.warning("No valid admin keys provided. Skipping admin key update.")
            else:
                # Clear existing keys if needed
                if security_config.admin_key:
                    logging.info("Clearing existing admin keys...")
                    del security_config.admin_key[:]
                    node.writeConfig("security")
                    time.sleep(2)  # Give time for device to process

                # Append new keys
                for key in valid_keys:
                    logging.info(f"Adding admin key: {key}")
                    security_config.admin_key.append(key)
                node.writeConfig("security")
                logging.info("Admin keys updated successfully!")

            # Backup 'admin_key' before removing it
            admin_key_backup = modified_settings.get("admin_key", None)
            # Remove 'admin_key' from modified_settings to prevent interference
            del modified_settings["admin_key"]

            # Return early if there are no other settings left to process
            if not modified_settings:
                return

        if menu_state.menu_path[1] == "Radio Settings" or menu_state.menu_path[1] == "Module Settings":
            config_category = menu_state.menu_path[2].lower()  # for radio and module configs

            if {"latitude", "longitude", "altitude"} & modified_settings.keys():
                lat = float(modified_settings.get("latitude", 0.0))
                lon = float(modified_settings.get("longitude", 0.0))
                alt = int(modified_settings.get("altitude", 0))

                interface.localNode.setFixedPosition(lat, lon, alt)
                logging.info(f"Updated {config_category} with Latitude: {lat} and Longitude {lon} and Altitude {alt}")
                return

        elif menu_state.menu_path[1] == "User Settings":  # for user configs
            config_category = "User Settings"
            long_name = modified_settings.get("longName")
            short_name = modified_settings.get("shortName")
            is_licensed = modified_settings.get("isLicensed")
            is_licensed = is_licensed == "True" or is_licensed is True  # Normalize boolean

            node.setOwner(long_name, short_name, is_licensed)

            logging.info(
                f"Updated {config_category} with Long Name: {long_name}, Short Name: {short_name}, Licensed Mode: {is_licensed}"
            )

            return

        elif menu_state.menu_path[1] == "Channels":  # for channel configs
            config_category = "Channels"

            try:
                channel = menu_state.menu_path[-1]
                channel_num = int(channel.split()[-1]) - 1
            except (IndexError, ValueError) as e:
                channel_num = None

            channel = node.channels[channel_num]
            for key, value in modified_settings.items():
                if key == "psk":  # Special case: decode Base64 for psk
                    channel.settings.psk = base64.b64decode(value)
                elif key == "position_precision":  # Special case: module_settings
                    channel.settings.module_settings.position_precision = value
                else:
                    setattr(channel.settings, key, value)  # Use setattr for other fields

            if channel_num == 0:
                channel.role = channel_pb2.Channel.Role.PRIMARY
            else:
                channel.role = channel_pb2.Channel.Role.SECONDARY

            node.writeChannel(channel_num)

            logging.info(f"Updated Channel {channel_num} in {config_category}")
            logging.info(node.channels)
            return

        else:
            config_category = None

        for config_item, new_value in modified_settings.items():
            # Check if the category exists in localConfig
            if hasattr(node.localConfig, config_category):
                config_subcategory = getattr(node.localConfig, config_category)
            # Check if the category exists in moduleConfig
            elif hasattr(node.moduleConfig, config_category):
                config_subcategory = getattr(node.moduleConfig, config_category)
            else:
                logging.warning(f"Config category '{config_category}' not found in config.")
                continue

            # Check if the config_item exists in the subcategory
            if hasattr(config_subcategory, config_item):
                field = getattr(config_subcategory, config_item)

                try:
                    if isinstance(field, (int, float, str, bool)):  # Direct field types
                        setattr(config_subcategory, config_item, new_value)
                        logging.info(f"Updated {config_category}.{config_item} to {new_value}")
                    elif isinstance(field, Message):  # Handle protobuf sub-messages
                        if isinstance(new_value, dict):  # If new_value is a dictionary
                            for sub_field, sub_value in new_value.items():
                                if hasattr(field, sub_field):
                                    setattr(field, sub_field, sub_value)
                                    logging.info(f"Updated {config_category}.{config_item}.{sub_field} to {sub_value}")
                                else:
                                    logging.warning(
                                        f"Sub-field '{sub_field}' not found in {config_category}.{config_item}"
                                    )
                        else:
                            logging.warning(f"Invalid value for {config_category}.{config_item}. Expected dict.")
                    else:
                        logging.warning(f"Unsupported field type for {config_category}.{config_item}.")
                except AttributeError as e:
                    logging.error(f"Failed to update {config_category}.{config_item}: {e}")
            else:
                logging.warning(f"Config item '{config_item}' not found in config category '{config_category}'.")

        # Write the configuration changes to the node
        try:
            node.writeConfig(config_category)
            logging.info(f"Changes written to config category: {config_category}")

            if admin_key_backup is not None:
                modified_settings["admin_key"] = admin_key_backup
        except Exception as e:
            logging.error(f"Failed to write configuration for category '{config_category}': {e}")

    except Exception as e:
        logging.error(f"Error saving changes: {e}")
