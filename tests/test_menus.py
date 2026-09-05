from types import SimpleNamespace
import unittest

from meshtastic.protobuf import channel_pb2, config_pb2, module_config_pb2

from contact.ui.menus import generate_menu_from_protobuf


class MenusTests(unittest.TestCase):
    def test_channels_include_enabled_state_and_display_names(self):
        from contact.ui.control_ui import get_settings_option_label

        channels = [
            channel_pb2.Channel(role=channel_pb2.Channel.PRIMARY, settings=channel_pb2.ChannelSettings(name="Local")),
            channel_pb2.Channel(role=channel_pb2.Channel.DISABLED, settings=channel_pb2.ChannelSettings(name="Local")),
            channel_pb2.Channel(role=channel_pb2.Channel.DISABLED),
        ]
        node = SimpleNamespace(
            localConfig=config_pb2.Config(), moduleConfig=module_config_pb2.ModuleConfig(),
            getChannelByChannelIndex=lambda index: channels[index] if index < len(channels) else None,
        )
        menu = generate_menu_from_protobuf(None, node=node)["Main Menu"]["Channels"]
        self.assertEqual(menu["Channel 1"]["enabled"], (None, True))
        self.assertEqual(menu["Channel 2"]["enabled"], (None, False))
        labels = [get_settings_option_label(key, value, ["Main Menu", "Channels"]) for key, value in menu.items()]
        self.assertEqual(labels, ["Local", "Local", "Channel 3"])

    def test_main_menu_includes_factory_reset_config_after_factory_reset(self) -> None:
        local_node = SimpleNamespace(
            localConfig=config_pb2.Config(),
            moduleConfig=module_config_pb2.ModuleConfig(),
            getChannelByChannelIndex=lambda _: None,
        )
        interface = SimpleNamespace(
            localNode=local_node,
            getMyNodeInfo=lambda: {
                "user": {"longName": "Test User", "shortName": "TU", "isLicensed": False},
                "position": {"latitude": 0.0, "longitude": 0.0, "altitude": 0},
            },
        )

        menu = generate_menu_from_protobuf(interface)
        keys = list(menu["Main Menu"].keys())

        self.assertLess(keys.index("Factory Reset"), keys.index("factory_reset_config"))
        self.assertEqual(keys[keys.index("Factory Reset") + 1], "factory_reset_config")

    def test_module_settings_include_ringtone_and_canned_messages(self) -> None:
        local_node = SimpleNamespace(
            localConfig=config_pb2.Config(),
            moduleConfig=module_config_pb2.ModuleConfig(),
            ringtone="tone",
            cannedPluginMessage="Hi|Bye",
            getChannelByChannelIndex=lambda _: None,
        )
        interface = SimpleNamespace(
            localNode=local_node,
            getMyNodeInfo=lambda: {"position": {"latitude": 0.0, "longitude": 0.0, "altitude": 0}},
        )

        module_settings = generate_menu_from_protobuf(interface)["Main Menu"]["Module Settings"]

        self.assertEqual(module_settings["external_notification"]["ringtone"], (None, "tone"))
        self.assertEqual(module_settings["canned_message"]["messages"], (None, "Hi|Bye"))

    def test_user_settings_include_unmessageable_toggle(self) -> None:
        local_node = SimpleNamespace(
            localConfig=config_pb2.Config(),
            moduleConfig=module_config_pb2.ModuleConfig(),
            getChannelByChannelIndex=lambda _: None,
        )
        interface = SimpleNamespace(
            localNode=local_node,
            getMyNodeInfo=lambda: {
                "user": {"longName": "Test User", "shortName": "TU", "isUnmessagable": True},
                "position": {},
            },
        )

        user_settings = generate_menu_from_protobuf(interface)["Main Menu"]["User Settings"]
        self.assertEqual(user_settings["isUnmessagable"], (None, True))
