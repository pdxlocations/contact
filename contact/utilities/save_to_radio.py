from meshtastic.protobuf import channel_pb2
from google.protobuf.message import Message
import logging
import base64

DEVICE_REBOOT_KEYS = {"button_gpio", "buzzer_gpio", "role", "rebroadcast_mode"}
POWER_REBOOT_KEYS = {
    "device_battery_ina_address",
    "is_power_saving",
    "ls_secs",
    "min_wake_secs",
    "on_battery_shutdown_after_secs",
    "sds_secs",
    "wait_bluetooth_secs",
}
DISPLAY_REBOOT_KEYS = {"screen_on_secs", "flip_screen", "oled", "displaymode"}
LORA_REBOOT_KEYS = {
    "use_preset",
    "region",
    "modem_preset",
    "bandwidth",
    "spread_factor",
    "coding_rate",
    "tx_power",
    "frequency_offset",
    "override_frequency",
    "channel_num",
    "sx126x_rx_boosted_gain",
}
SECURITY_NON_REBOOT_KEYS = {"debug_log_api_enabled", "serial_enabled"}
USER_RECONNECT_KEYS = {"longName", "shortName", "isLicensed", "is_licensed", "isUnmessagable", "is_unmessagable"}


def _collect_changed_keys(modified_settings):
    changed = set()
    for key, value in modified_settings.items():
        if isinstance(value, dict):
            changed.update(_collect_changed_keys(value))
        else:
            changed.add(key)
    return changed


def _requires_reconnect(menu_state, modified_settings) -> bool:
    if not modified_settings or len(menu_state.menu_path) < 2:
        return False

    section = menu_state.menu_path[1]
    changed_keys = _collect_changed_keys(modified_settings)

    if section == "Module Settings":
        return True
    if section == "User Settings":
        return bool(changed_keys & USER_RECONNECT_KEYS)
    if section == "Channels":
        return False
    if section != "Radio Settings" or len(menu_state.menu_path) < 3:
        return False

    config_category = menu_state.menu_path[2].lower()

    if config_category in {"network", "bluetooth"}:
        return True
    if config_category == "security":
        return not changed_keys.issubset(SECURITY_NON_REBOOT_KEYS)
    if config_category == "device":
        return bool(changed_keys & DEVICE_REBOOT_KEYS)
    if config_category == "power":
        return bool(changed_keys & POWER_REBOOT_KEYS)
    if config_category == "display":
        return bool(changed_keys & DISPLAY_REBOOT_KEYS)
    if config_category == "lora":
        return bool(changed_keys & LORA_REBOOT_KEYS)

    # Firmware defaults most config writes to reboot-required unless a handler
    # explicitly clears that flag.
    return True


def save_changes(interface, modified_settings, menu_state, node=None):
    """
    Save changes to the device based on modified settings.
    :param interface: Meshtastic interface instance
    :param menu_path: Current menu path
    :param modified_settings: Dictionary of modified settings
    """
    try:
        if not modified_settings:
            logging.info("No changes to save. modified_settings is empty.")
            return False

        node = node or interface.getNode("^local")
        admin_key_backup = None
        if "admin_key" in modified_settings:
            # Get reference to security config
            security_config = node.localConfig.security
            admin_keys = modified_settings["admin_key"]

            # Filter out empty keys
            valid_keys = [key for key in admin_keys if key and key.strip() and key != b""]

            # Update the repeated field in memory, then send one complete
            # security config. Sending an empty list first can revoke the key
            # authorizing this remote-admin session before a second write can
            # restore the remaining keys.
            del security_config.admin_key[:]
            security_config.admin_key.extend(valid_keys)
            node.writeConfig("security")
            logging.info("Admin keys updated successfully (%d key(s)).", len(valid_keys))

            # Backup 'admin_key' before removing it
            admin_key_backup = modified_settings.get("admin_key", None)
            # Remove 'admin_key' from modified_settings to prevent interference
            del modified_settings["admin_key"]

            # Return early if there are no other settings left to process
            if not modified_settings:
                return _requires_reconnect(menu_state, {"admin_key": admin_key_backup})

        if menu_state.menu_path[1] == "Radio Settings" or menu_state.menu_path[1] == "Module Settings":
            config_category = menu_state.menu_path[2].lower()  # for radio and module configs

            if {"latitude", "longitude", "altitude"} & modified_settings.keys():
                lat = float(modified_settings.get("latitude", 0.0))
                lon = float(modified_settings.get("longitude", 0.0))
                alt = int(modified_settings.get("altitude", 0))

                node.setFixedPosition(lat, lon, alt)
                logging.info(f"Updated {config_category} with Latitude: {lat} and Longitude {lon} and Altitude {alt}")
                return False

        elif menu_state.menu_path[1] == "User Settings":  # for user configs
            config_category = "User Settings"
            long_name = modified_settings.get("longName")
            short_name = modified_settings.get("shortName")
            is_licensed = modified_settings.get("isLicensed")
            is_unmessagable = modified_settings.get("isUnmessagable")
            is_licensed = is_licensed == "True" or is_licensed is True  # Normalize boolean
            if is_unmessagable is not None:
                is_unmessagable = is_unmessagable == "True" or is_unmessagable is True

            node.setOwner(long_name, short_name, is_licensed, is_unmessagable)

            logging.info(
                f"Updated {config_category} with Long Name: {long_name}, Short Name: {short_name}, "
                f"Licensed Mode: {is_licensed}, Unmessageable: {is_unmessagable}"
            )

            return _requires_reconnect(menu_state, modified_settings)

        elif menu_state.menu_path[1] == "Channels":  # for channel configs
            config_category = "Channels"

            try:
                channels_index = menu_state.menu_path.index("Channels")
                channel = menu_state.menu_path[channels_index + 1]
                channel_num = int(channel.split()[-1]) - 1
            except (IndexError, ValueError) as e:
                channel_num = None

            channel = node.channels[channel_num]
            for key, value in modified_settings.items():
                if key == "enabled":
                    if not value:
                        channel.role = channel_pb2.Channel.Role.DISABLED
                    elif channel.role == channel_pb2.Channel.Role.DISABLED:
                        channel.role = (
                            channel_pb2.Channel.Role.PRIMARY if channel_num == 0
                            else channel_pb2.Channel.Role.SECONDARY
                        )
                elif key == "psk":  # Special case: decode Base64 for psk
                    channel.settings.psk = base64.b64decode(value)
                elif key in {"position_precision", "is_muted"}:
                    # These fields belong to ChannelSettings.module_settings,
                    # not ChannelSettings itself.
                    setattr(channel.settings.module_settings, key, value)
                else:
                    setattr(channel.settings, key, value)  # Use setattr for other fields

            node.writeChannel(channel_num)

            logging.info(f"Updated Channel {channel_num} in {config_category}")
            logging.info(node.channels)
            return False

        else:
            config_category = None

        # Resolve the target config container, including nested sub-messages (e.g., network.ipv4_config)
        config_container = None
        if hasattr(node.localConfig, config_category):
            config_container = getattr(node.localConfig, config_category)
        elif hasattr(node.moduleConfig, config_category):
            config_container = getattr(node.moduleConfig, config_category)
        else:
            logging.warning(f"Config category '{config_category}' not found in config.")
            return False

        if len(menu_state.menu_path) >= 4:
            nested_key = menu_state.menu_path[3]
            if hasattr(config_container, nested_key):
                config_container = getattr(config_container, nested_key)

        for config_item, new_value in modified_settings.items():
            config_subcategory = config_container

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
            return _requires_reconnect(menu_state, modified_settings)
        except Exception as e:
            logging.error(f"Failed to write configuration for category '{config_category}': {e}")
            return False

    except Exception as e:
        logging.error(f"Error saving changes: {e}")
        return False
