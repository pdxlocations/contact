
import yaml
import logging
from typing import List
from google.protobuf.json_format import MessageToDict
from meshtastic import BROADCAST_ADDR, mt_config
from meshtastic.util import camel_to_snake, snake_to_camel, fromStr

# defs are from meshtastic/python/main

def traverseConfig(config_root, config, interface_config) -> bool:
    """Iterate through current config level preferences and either traverse deeper if preference is a dict or set preference"""
    snake_name = camel_to_snake(config_root)
    for pref in config:
        pref_name = f"{snake_name}.{pref}"
        if isinstance(config[pref], dict):
            traverseConfig(pref_name, config[pref], interface_config)
        else:
            setPref(interface_config, pref_name, config[pref])

    return True

def splitCompoundName(comp_name: str) -> List[str]:
    """Split compound (dot separated) preference name into parts"""
    name: List[str] = comp_name.split(".")
    if len(name) < 2:
        name[0] = comp_name
        name.append(comp_name)
    return name

def setPref(config, comp_name, raw_val) -> bool:
    """Set a channel or preferences value"""

    name = splitCompoundName(comp_name)

    snake_name = camel_to_snake(name[-1])
    camel_name = snake_to_camel(name[-1])
    uni_name = camel_name if mt_config.camel_case else snake_name
    logging.debug(f"snake_name:{snake_name}")
    logging.debug(f"camel_name:{camel_name}")

    objDesc = config.DESCRIPTOR
    config_part = config
    config_type = objDesc.fields_by_name.get(name[0])
    if config_type and config_type.message_type is not None:
        for name_part in name[1:-1]:
            part_snake_name = camel_to_snake((name_part))
            config_part = getattr(config, config_type.name)
            config_type = config_type.message_type.fields_by_name.get(part_snake_name)
    pref = None
    if config_type and config_type.message_type is not None:
        pref = config_type.message_type.fields_by_name.get(snake_name)
    # Others like ChannelSettings are standalone
    elif config_type:
        pref = config_type

    if (not pref) or (not config_type):
        return False

    if isinstance(raw_val, str):
        val = fromStr(raw_val)
    else:
        val = raw_val
    logging.debug(f"valStr:{raw_val} val:{val}")

    if snake_name == "wifi_psk" and len(str(raw_val)) < 8:
        logging.info(f"Warning: network.wifi_psk must be 8 or more characters.")
        return False

    enumType = pref.enum_type
    # pylint: disable=C0123
    if enumType and type(val) == str:
        # We've failed so far to convert this string into an enum, try to find it by reflection
        e = enumType.values_by_name.get(val)
        if e:
            val = e.number
        else:
            logging.info(
                f"{name[0]}.{uni_name} does not have an enum called {val}, so you can not set it."
            )
            logging.info(f"Choices in sorted order are:")
            names = []
            for f in enumType.values:
                # Note: We must use the value of the enum (regardless if camel or snake case)
                names.append(f"{f.name}")
            for temp_name in sorted(names):
                logging.info(f"    {temp_name}")
            return False

    # repeating fields need to be handled with append, not setattr
    if pref.label != pref.LABEL_REPEATED:
        try:
            if config_type.message_type is not None:
                config_values = getattr(config_part, config_type.name)
                setattr(config_values, pref.name, val)
            else:
                setattr(config_part, snake_name, val)
        except TypeError:
            # The setter didn't like our arg type guess try again as a string
            config_values = getattr(config_part, config_type.name)
            setattr(config_values, pref.name, str(val))
    elif type(val) == list:
        new_vals = [fromStr(x) for x in val]
        config_values = getattr(config, config_type.name)
        getattr(config_values, pref.name)[:] = new_vals
    else:
        config_values = getattr(config, config_type.name)
        if val == 0:
            # clear values
            logging.info(f"Clearing {pref.name} list")
            del getattr(config_values, pref.name)[:]
        else:
            logging.info(f"Adding '{raw_val}' to the {pref.name} list")
            cur_vals = [x for x in getattr(config_values, pref.name) if x not in [0, "", b""]]
            cur_vals.append(val)
            getattr(config_values, pref.name)[:] = cur_vals
        return True

    prefix = f"{'.'.join(name[0:-1])}." if config_type.message_type is not None else ""
    logging.info(f"Set {prefix}{uni_name} to {raw_val}")

    return True



def config_import(interface, filename):
    with open(filename, encoding="utf8") as file:
        configuration = yaml.safe_load(file)
        closeNow = True

        interface.getNode('^local', False).beginSettingsTransaction()

        if "owner" in configuration:
            logging.info(f"Setting device owner to {configuration['owner']}")
            waitForAckNak = True
            interface.getNode('^local', False).setOwner(configuration["owner"])

        if "owner_short" in configuration:
            logging.info(
                f"Setting device owner short to {configuration['owner_short']}"
            )
            waitForAckNak = True
            interface.getNode('^local', False).setOwner(
                long_name=None, short_name=configuration["owner_short"]
            )

        if "ownerShort" in configuration:
            logging.info(
                f"Setting device owner short to {configuration['ownerShort']}"
            )
            waitForAckNak = True
            interface.getNode('^local', False).setOwner(
                long_name=None, short_name=configuration["ownerShort"]
            )

        if "channel_url" in configuration:
            logging.info(f"Setting channel url to {configuration['channel_url']}")
            interface.getNode('^local').setURL(configuration["channel_url"])

        if "channelUrl" in configuration:
            logging.info(f"Setting channel url to {configuration['channelUrl']}")
            interface.getNode('^local').setURL(configuration["channelUrl"])

        if "location" in configuration:
            alt = 0
            lat = 0.0
            lon = 0.0
            localConfig = interface.localNode.localConfig

            if "alt" in configuration["location"]:
                alt = int(configuration["location"]["alt"] or 0)
                logging.info(f"Fixing altitude at {alt} meters")
            if "lat" in configuration["location"]:
                lat = float(configuration["location"]["lat"] or 0)
                logging.info(f"Fixing latitude at {lat} degrees")
            if "lon" in configuration["location"]:
                lon = float(configuration["location"]["lon"] or 0)
                logging.info(f"Fixing longitude at {lon} degrees")
            logging.info("Setting device position")
            interface.localNode.setFixedPosition(lat, lon, alt)

        if "config" in configuration:
            localConfig = interface.getNode('^local').localConfig
            for section in configuration["config"]:
                traverseConfig(
                    section, configuration["config"][section], localConfig
                )
                interface.getNode('^local').writeConfig(
                    camel_to_snake(section)
                )

        if "module_config" in configuration:
            moduleConfig = interface.getNode('^local').moduleConfig
            for section in configuration["module_config"]:
                traverseConfig(
                    section,
                    configuration["module_config"][section],
                    moduleConfig,
                )
                interface.getNode('^local').writeConfig(
                    camel_to_snake(section)
                )

        interface.getNode('^local', False).commitSettingsTransaction()
        logging.info("Writing modified configuration to device")



def config_export(interface) -> str:
    """used in --export-config"""
    configObj = {}

    owner = interface.getLongName()
    owner_short = interface.getShortName()
    channel_url = interface.localNode.getURL()
    myinfo = interface.getMyNodeInfo()
    pos = myinfo.get("position")
    lat = None
    lon = None
    alt = None
    if pos:
        lat = pos.get("latitude")
        lon = pos.get("longitude")
        alt = pos.get("altitude")

    if owner:
        configObj["owner"] = owner
    if owner_short:
        configObj["owner_short"] = owner_short
    if channel_url:
        if mt_config.camel_case:
            configObj["channelUrl"] = channel_url
        else:
            configObj["channel_url"] = channel_url
    # lat and lon don't make much sense without the other (so fill with 0s), and alt isn't meaningful without both
    if lat or lon:
        configObj["location"] = {"lat": lat or float(0), "lon": lon or float(0)}
        if alt:
            configObj["location"]["alt"] = alt

    config = MessageToDict(interface.localNode.localConfig)	#checkme - Used as a dictionary here and a string below
    if config:
        # Convert inner keys to correct snake/camelCase
        prefs = {}
        for pref in config:
            if mt_config.camel_case:
                prefs[snake_to_camel(pref)] = config[pref]
            else:
                prefs[pref] = config[pref]
            # mark base64 encoded fields as such
            if pref == "security":
                if 'privateKey' in prefs[pref]:
                    prefs[pref]['privateKey'] = 'base64:' + prefs[pref]['privateKey']
                if 'publicKey' in prefs[pref]:
                    prefs[pref]['publicKey'] = 'base64:' + prefs[pref]['publicKey']
                if 'adminKey' in prefs[pref]:
                    for i in range(len(prefs[pref]['adminKey'])):
                        prefs[pref]['adminKey'][i] = 'base64:' + prefs[pref]['adminKey'][i]
        if mt_config.camel_case:
            configObj["config"] = config		#Identical command here and 2 lines below?
        else:
            configObj["config"] = config

    module_config = MessageToDict(interface.localNode.moduleConfig)
    if module_config:
        # Convert inner keys to correct snake/camelCase
        prefs = {}
        for pref in module_config:
            if len(module_config[pref]) > 0:
                prefs[pref] = module_config[pref]
        if mt_config.camel_case:
            configObj["module_config"] = prefs
        else:
            configObj["module_config"] = prefs

    config_txt = "# start of Meshtastic configure yaml\n"		#checkme - "config" (now changed to config_out)
                                                                        #was used as a string here and a Dictionary above
    config_txt += yaml.dump(configObj)

    # logging.info(config_txt)
    return config_txt