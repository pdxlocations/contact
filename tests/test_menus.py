from types import SimpleNamespace
import unittest

from meshtastic.protobuf import config_pb2, module_config_pb2

from contact.ui.menus import generate_menu_from_protobuf


class MenusTests(unittest.TestCase):
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
