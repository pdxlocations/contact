from types import SimpleNamespace
import unittest
from unittest import mock

from contact.utilities.save_to_radio import save_changes


class SaveToRadioTests(unittest.TestCase):
    def build_interface(self):
        node = mock.Mock()
        node.localConfig = SimpleNamespace(
            lora=SimpleNamespace(region=0, serial_enabled=False),
            device=SimpleNamespace(role="CLIENT", name="node"),
            security=SimpleNamespace(debug_log_api_enabled=False, serial_enabled=False, admin_key=[]),
            display=SimpleNamespace(flip_screen=False, units=0),
            power=SimpleNamespace(is_power_saving=False, adc_enabled=False),
            network=SimpleNamespace(wifi_enabled=False),
            bluetooth=SimpleNamespace(enabled=False),
        )
        node.moduleConfig = SimpleNamespace(mqtt=SimpleNamespace(enabled=False))
        interface = mock.Mock()
        interface.getNode.return_value = node
        return interface, node

    def test_save_changes_returns_true_for_lora_writes_that_require_reconnect(self) -> None:
        interface, node = self.build_interface()
        menu_state = SimpleNamespace(menu_path=["Main Menu", "Radio Settings", "Lora"])

        reconnect_required = save_changes(interface, {"region": 7}, menu_state)

        self.assertTrue(reconnect_required)
        self.assertEqual(node.localConfig.lora.region, 7)
        node.writeConfig.assert_called_once_with("lora")

    def test_save_changes_returns_false_when_nothing_changed(self) -> None:
        interface = mock.Mock()
        menu_state = SimpleNamespace(menu_path=["Main Menu", "Radio Settings", "Lora"])

        self.assertFalse(save_changes(interface, {}, menu_state))

    def test_save_changes_returns_false_for_non_rebooting_security_fields(self) -> None:
        interface, node = self.build_interface()
        menu_state = SimpleNamespace(menu_path=["Main Menu", "Radio Settings", "Security"])

        reconnect_required = save_changes(interface, {"serial_enabled": True}, menu_state)

        self.assertFalse(reconnect_required)
        self.assertTrue(node.localConfig.security.serial_enabled)

    def test_save_changes_returns_true_for_rebooting_security_fields(self) -> None:
        interface, _node = self.build_interface()
        menu_state = SimpleNamespace(menu_path=["Main Menu", "Radio Settings", "Security"])

        reconnect_required = save_changes(interface, {"admin_key": [b"12345678"]}, menu_state)

        self.assertTrue(reconnect_required)

    def test_save_changes_returns_true_only_for_rebooting_device_fields(self) -> None:
        interface, node = self.build_interface()
        menu_state = SimpleNamespace(menu_path=["Main Menu", "Radio Settings", "Device"])

        self.assertFalse(save_changes(interface, {"name": "renamed"}, menu_state))
        self.assertEqual(node.localConfig.device.name, "renamed")

        node.writeConfig.reset_mock()
        self.assertTrue(save_changes(interface, {"role": "ROUTER"}, menu_state))
        self.assertEqual(node.localConfig.device.role, "ROUTER")

    def test_save_changes_returns_true_for_network_settings(self) -> None:
        interface, node = self.build_interface()
        menu_state = SimpleNamespace(menu_path=["Main Menu", "Radio Settings", "Network"])

        reconnect_required = save_changes(interface, {"wifi_enabled": True}, menu_state)

        self.assertTrue(reconnect_required)
        self.assertTrue(node.localConfig.network.wifi_enabled)

    def test_save_changes_returns_true_only_for_rebooting_power_fields(self) -> None:
        interface, node = self.build_interface()
        menu_state = SimpleNamespace(menu_path=["Main Menu", "Radio Settings", "Power"])

        self.assertFalse(save_changes(interface, {"adc_enabled": True}, menu_state))
        self.assertTrue(node.localConfig.power.adc_enabled)

        node.writeConfig.reset_mock()
        self.assertTrue(save_changes(interface, {"is_power_saving": True}, menu_state))
        self.assertTrue(node.localConfig.power.is_power_saving)

    def test_save_changes_returns_true_for_module_settings(self) -> None:
        interface, node = self.build_interface()
        menu_state = SimpleNamespace(menu_path=["Main Menu", "Module Settings", "Mqtt"])

        reconnect_required = save_changes(interface, {"enabled": True}, menu_state)

        self.assertTrue(reconnect_required)
        self.assertTrue(node.moduleConfig.mqtt.enabled)

    def test_save_changes_returns_true_for_user_name_changes(self) -> None:
        interface, node = self.build_interface()
        menu_state = SimpleNamespace(menu_path=["Main Menu", "User Settings"])

        reconnect_required = save_changes(interface, {"longName": "Node"}, menu_state)

        self.assertTrue(reconnect_required)
        node.setOwner.assert_called_once()

    def test_save_changes_returns_true_for_user_license_changes(self) -> None:
        interface, node = self.build_interface()
        menu_state = SimpleNamespace(menu_path=["Main Menu", "User Settings"])

        reconnect_required = save_changes(interface, {"isLicensed": True}, menu_state)

        self.assertTrue(reconnect_required)
        node.setOwner.assert_called_once()

    def test_save_changes_sends_user_unmessageable_setting(self) -> None:
        interface, node = self.build_interface()
        menu_state = SimpleNamespace(menu_path=["Main Menu", "User Settings"])

        reconnect_required = save_changes(interface, {"isUnmessagable": True}, menu_state)

        self.assertTrue(reconnect_required)
        self.assertEqual(node.setOwner.call_args.args[3], True)
