import unittest
from types import SimpleNamespace
from tempfile import NamedTemporaryFile
from unittest.mock import Mock

import yaml
from meshtastic.protobuf import config_pb2, module_config_pb2

from contact.utilities.config_io import _is_repeated_field, config_export, config_import, splitCompoundName


class ConfigIoTests(unittest.TestCase):
    def test_split_compound_name_preserves_multi_part_values(self) -> None:
        self.assertEqual(splitCompoundName("config.device.role"), ["config", "device", "role"])

    def test_split_compound_name_duplicates_single_part_values(self) -> None:
        self.assertEqual(splitCompoundName("owner"), ["owner", "owner"])

    def test_is_repeated_field_prefers_new_style_attribute(self) -> None:
        field = type("Field", (), {"is_repeated": True})()

        self.assertTrue(_is_repeated_field(field))

    def test_is_repeated_field_falls_back_to_label_comparison(self) -> None:
        field_type = type("Field", (), {"label": 3, "LABEL_REPEATED": 3})

        self.assertTrue(_is_repeated_field(field_type()))

    def test_config_export_uses_selected_remote_node(self) -> None:
        local_node = SimpleNamespace(nodeNum=1)
        remote_node = SimpleNamespace(
            nodeNum=2,
            localConfig=config_pb2.Config(),
            moduleConfig=module_config_pb2.ModuleConfig(),
            getURL=lambda: "remote-channel-url",
        )
        interface = SimpleNamespace(
            localNode=local_node,
            nodesByNum={
                2: {
                    "user": {"longName": "Remote Node", "shortName": "REM"},
                    "position": {"latitude": 1.25, "longitude": 2.5, "altitude": 12},
                }
            },
        )

        exported = yaml.safe_load(config_export(interface, node=remote_node))

        self.assertEqual(exported["owner"], "Remote Node")
        self.assertEqual(exported["owner_short"], "REM")
        self.assertEqual(exported["channel_url"], "remote-channel-url")
        self.assertEqual(exported["location"], {"lat": 1.25, "lon": 2.5, "alt": 12})

    def test_config_import_uses_selected_remote_node(self) -> None:
        remote_node = Mock()
        interface = SimpleNamespace(localNode=Mock())
        with NamedTemporaryFile("w", suffix=".yaml") as config_file:
            yaml.safe_dump({"owner": "Remote Node"}, config_file)
            config_file.flush()

            config_import(interface, config_file.name, node=remote_node)

        remote_node.beginSettingsTransaction.assert_called_once_with()
        remote_node.setOwner.assert_called_once_with("Remote Node")
        remote_node.commitSettingsTransaction.assert_called_once_with()
        interface.localNode.setOwner.assert_not_called()
