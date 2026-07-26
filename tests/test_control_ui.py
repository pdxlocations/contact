from argparse import Namespace
from types import SimpleNamespace
import unittest
from unittest import mock

from contact.ui import control_ui
from contact.utilities.singleton import interface_state

from tests.test_support import reset_singletons


class ControlUiTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_singletons()

    def tearDown(self) -> None:
        reset_singletons()

    def test_reconnect_interface_with_splash_replaces_interface(self) -> None:
        old_interface = mock.Mock()
        new_interface = mock.Mock()
        stdscr = mock.Mock()
        parser = mock.Mock()
        parser.parse_args.return_value = Namespace()

        with mock.patch.object(control_ui, "setup_parser", return_value=parser):
            with mock.patch.object(control_ui, "draw_splash") as draw_splash:
                with mock.patch.object(control_ui, "reconnect_interface", return_value=new_interface) as reconnect:
                    with mock.patch.object(control_ui, "redraw_main_ui_after_reconnect") as redraw:
                        result = control_ui.reconnect_interface_with_splash(stdscr, old_interface)

        old_interface.close.assert_called_once_with()
        stdscr.clear.assert_called_once_with()
        stdscr.refresh.assert_called_once_with()
        draw_splash.assert_called_once_with(stdscr)
        reconnect.assert_called_once_with(parser.parse_args.return_value)
        redraw.assert_called_once_with(stdscr)
        self.assertIs(result, new_interface)
        self.assertIs(interface_state.interface, new_interface)

    def test_reconnect_after_admin_action_runs_action_then_reconnects(self) -> None:
        stdscr = mock.Mock()
        interface = mock.Mock()
        new_interface = mock.Mock()
        action = mock.Mock()

        with mock.patch.object(control_ui, "reconnect_interface_with_splash", return_value=new_interface) as reconnect:
            result = control_ui.reconnect_after_admin_action(
                stdscr, interface, action, "Factory Reset Requested by menu"
            )

        action.assert_called_once_with()
        reconnect.assert_called_once_with(stdscr, interface)
        self.assertIs(result, new_interface)

    def test_verify_remote_admin_requests_only_device_config(self) -> None:
        device_field = object()
        node = SimpleNamespace(
            localConfig=SimpleNamespace(DESCRIPTOR=SimpleNamespace(fields_by_name={"device": device_field})),
            requestConfig=mock.Mock(),
        )
        status_callback = mock.Mock()

        with mock.patch.object(control_ui, "_request_remote_with_timeout") as request:
            control_ui.verify_remote_admin(node, status_callback=status_callback)

        status_callback.assert_called_once_with("Checking remote-admin permission…")
        request.assert_called_once_with(node.requestConfig, device_field, cancel_callback=None)

    def test_redraw_main_ui_after_reconnect_refreshes_channels_nodes_and_layout(self) -> None:
        stdscr = mock.Mock()

        with mock.patch("contact.utilities.utils.get_channels") as get_channels:
            with mock.patch("contact.utilities.utils.refresh_node_list") as refresh_node_list:
                with mock.patch("contact.ui.contact_ui.handle_resize") as handle_resize:
                    control_ui.redraw_main_ui_after_reconnect(stdscr)

        get_channels.assert_called_once_with()
        refresh_node_list.assert_called_once_with()
        handle_resize.assert_called_once_with(stdscr, False)

    def test_request_factory_reset_uses_library_helper_when_supported(self) -> None:
        node = mock.Mock()

        control_ui.request_factory_reset(node)

        node.factoryReset.assert_called_once_with(full=False)
        node.ensureSessionKey.assert_not_called()
        node._sendAdmin.assert_not_called()

    def test_request_factory_reset_uses_library_helper_for_full_reset_when_supported(self) -> None:
        node = mock.Mock()

        control_ui.request_factory_reset(node, full=True)

        node.factoryReset.assert_called_once_with(full=True)
        node.ensureSessionKey.assert_not_called()
        node._sendAdmin.assert_not_called()

    def test_request_factory_reset_falls_back_to_int_valued_admin_message(self) -> None:
        node = mock.Mock()
        node.factoryReset.side_effect = TypeError(
            "Field meshtastic.protobuf.AdminMessage.factory_reset_config: Expected an int, got a boolean."
        )
        node.iface = SimpleNamespace(localNode=node)

        control_ui.request_factory_reset(node)

        node.ensureSessionKey.assert_called_once_with()
        sent_message = node._sendAdmin.call_args.args[0]
        self.assertEqual(sent_message.factory_reset_config, 1)
        self.assertIsNone(node._sendAdmin.call_args.kwargs["onResponse"])

    def test_request_factory_reset_full_falls_back_to_int_valued_admin_message(self) -> None:
        node = mock.Mock()
        node.factoryReset.side_effect = TypeError(
            "Field meshtastic.protobuf.AdminMessage.factory_reset_device: Expected an int, got a boolean."
        )
        node.iface = SimpleNamespace(localNode=node)

        control_ui.request_factory_reset(node, full=True)

        node.ensureSessionKey.assert_called_once_with()
        sent_message = node._sendAdmin.call_args.args[0]
        self.assertEqual(sent_message.factory_reset_device, 1)
        self.assertIsNone(node._sendAdmin.call_args.kwargs["onResponse"])
