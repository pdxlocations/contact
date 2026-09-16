from contextlib import ExitStack
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from meshtastic.protobuf import admin_pb2, config_pb2, module_config_pb2
from contact.ui import control_ui
from contact.ui.menus import generate_menu_from_protobuf, update_ham_fields
from contact.utilities.save_to_radio import save_changes
from tests.test_support import reset_shared_state


class HamSettingsTests(unittest.TestCase):
    def build_interface(self, licensed=False):
        node = Mock(nodeNum=2, localConfig=config_pb2.Config(), moduleConfig=module_config_pb2.ModuleConfig())
        node.localConfig.lora.tx_power = 20
        node.localConfig.lora.override_frequency = 915.5
        node.getChannelByChannelIndex.return_value = None
        info = {'user': {'longName': 'KD2ABC', 'shortName': 'HAM', 'isLicensed': licensed}}
        interface = SimpleNamespace(localNode=node, getMyNodeInfo=lambda: info, nodesByNum={2: info})
        node.iface = interface
        return interface, node

    def test_fields_follow_license_selection_and_installed_descriptors(self):
        interface, node = self.build_interface()
        user = generate_menu_from_protobuf(interface)['Main Menu']['User Settings']
        descriptors = admin_pb2.HamParameters.DESCRIPTOR.fields
        self.assertTrue(all(field.name not in user for field in descriptors))
        user['isLicensed'] = (None, True)
        update_ham_fields(user, node)
        for field in descriptors:
            self.assertIs(user[field.name][0], field)
        self.assertEqual(user['call_sign'][1], 'KD2ABC')
        self.assertEqual(user['tx_power'][1], 20)
        self.assertEqual(user['frequency'][1], 915.5)
        self.assertNotIn('longName', user)
        user['frequency'] = (user['frequency'][0], 916.0)
        update_ham_fields(user, node)
        self.assertEqual(user['frequency'][1], 916.0)
        user['isLicensed'] = (None, False)
        update_ham_fields(user, node)
        self.assertTrue(all(field.name not in user for field in descriptors))
        self.assertEqual(user['longName'][1], 'KD2ABC')
        self.assertEqual(user['shortName'][1], 'HAM')

    def test_remote_menu_uses_remote_license_and_radio_values(self):
        interface, node = self.build_interface(True)
        interface.localNode = Mock()
        user = generate_menu_from_protobuf(interface, node=node)['Main Menu']['User Settings']
        self.assertEqual(user['frequency'][1], 915.5)
        self.assertEqual(user['call_sign'][1], 'KD2ABC')

    def test_save_full_ham_message_on_selected_node(self):
        for remote in (False, True):
            interface, node = self.build_interface(True)
            if remote:
                interface.localNode = Mock()
            user = generate_menu_from_protobuf(interface, node=node)['Main Menu']['User Settings']
            changes = {name: value for name, (_, value) in user.items()}
            changes['frequency'] = 916.0
            state = SimpleNamespace(menu_path=['Main Menu', 'User Settings'])
            self.assertTrue(save_changes(interface, changes, state, node=node))
            message = node._sendAdmin.call_args.args[0]
            self.assertEqual(message.WhichOneof('payload_variant'), 'set_ham_mode')
            self.assertEqual(message.set_ham_mode.call_sign, 'KD2ABC')
            self.assertEqual(message.set_ham_mode.short_name, 'HAM')
            self.assertEqual(message.set_ham_mode.tx_power, 20)
            self.assertEqual(message.set_ham_mode.frequency, 916.0)
            self.assertEqual(node._sendAdmin.call_args.kwargs['onResponse'], node.onAckNak if remote else None)
            self.assertEqual([c[0] for c in node.method_calls], [
                *['getChannelByChannelIndex'] * 8, 'ensureSessionKey', 'beginSettingsTransaction',
                'setOwner', '_sendAdmin', 'commitSettingsTransaction'])

    def test_disabling_license_does_not_send_ham_command(self):
        interface, node = self.build_interface(True)
        user = generate_menu_from_protobuf(interface)['Main Menu']['User Settings']
        user['isLicensed'] = (None, False)
        update_ham_fields(user, node)
        state = SimpleNamespace(menu_path=['Main Menu', 'User Settings'])
        self.assertTrue(save_changes(interface, {k: v[1] for k, v in user.items()}, state, node=node))
        node._sendAdmin.assert_not_called()
        node.setOwner.assert_called_once_with('KD2ABC', 'HAM', False, False)

    def test_edit_through_normal_menu_after_selecting_licensed(self):
        reset_shared_state()
        interface, node = self.build_interface()
        win = Mock()
        # Open User Settings, select licensed, edit the now-visible callsign, save.
        win.getch.side_effect = [10, control_ui.curses.KEY_DOWN, control_ui.curses.KEY_DOWN,
                                10, control_ui.curses.KEY_DOWN, control_ui.curses.KEY_DOWN, 10, 9, 10, 27]
        saved = {}
        def capture(_interface, values, _state, **kwargs):
            saved.update(values)
            return False
        try:
            with ExitStack() as stack:
                stack.enter_context(patch.object(control_ui.curses, 'update_lines_cols'))
                stack.enter_context(patch.object(control_ui, 'display_menu', return_value=(win, Mock())))
                stack.enter_context(patch.object(control_ui, 'move_highlight'))
                stack.enter_context(patch.object(control_ui, 'get_list_input', return_value='True'))
                text = stack.enter_context(patch.object(control_ui, 'get_text_input', return_value='KD2XYZ'))
                stack.enter_context(patch.object(control_ui, 'save_changes', side_effect=capture))
                control_ui.settings_menu(Mock(), interface)
            self.assertEqual(text.call_args.args[1], 'call_sign')
            self.assertEqual(saved['call_sign'], 'KD2XYZ')
            self.assertTrue(saved['isLicensed'])
            self.assertEqual(saved['tx_power'], 20)
        finally:
            reset_shared_state()

    def test_new_library_fields_are_discovered_edited_and_saved(self):
        from google.protobuf import descriptor_pb2, descriptor_pool, message_factory
        schema = descriptor_pb2.FileDescriptorProto(name='future_ham.proto', syntax='proto3')
        params = schema.message_type.add(name='HamParameters')
        for field in admin_pb2.HamParameters.DESCRIPTOR.fields:
            params.field.add(name=field.name, number=field.number, type=field.type)
        if 'long_name' not in admin_pb2.HamParameters.DESCRIPTOR.fields_by_name:
            params.field.add(name='long_name', number=5, type=9)
        params.field.add(name='future_option', number=100, type=8)
        message = schema.message_type.add(name='AdminMessage')
        message.field.add(name='set_ham_mode', number=18, type=11, type_name='.HamParameters')
        pool = descriptor_pool.DescriptorPool()
        pool.Add(schema)
        future_params = message_factory.GetMessageClass(pool.FindMessageTypeByName('HamParameters'))
        future_message = message_factory.GetMessageClass(pool.FindMessageTypeByName('AdminMessage'))
        interface, node = self.build_interface(True)
        with patch.object(admin_pb2, 'HamParameters', future_params), patch.object(admin_pb2, 'AdminMessage', future_message):
            user = generate_menu_from_protobuf(interface)['Main Menu']['User Settings']
            self.assertIn('long_name', user)
            self.assertEqual(user['future_option'][1], False)
            changes = {name: setting[1] for name, setting in user.items()}
            changes.update(long_name='Alice', future_option=True)
            state = SimpleNamespace(menu_path=['Main Menu', 'User Settings'])
            self.assertTrue(save_changes(interface, changes, state, node=node))
            sent = node._sendAdmin.call_args.args[0]
            parsed = future_message.FromString(sent.SerializeToString())
            self.assertEqual(parsed.set_ham_mode.long_name, 'Alice')
            self.assertTrue(parsed.set_ham_mode.future_option)

    def test_remote_user_settings_fetch_lora_before_showing_ham_defaults(self):
        _, node = self.build_interface(True)
        with patch.object(control_ui, '_request_remote_with_timeout') as request:
            self.assertTrue(control_ui._request_remote_section(node, ['Main Menu'], 'User Settings'))
        request.assert_called_once_with(node.requestConfig,
                                        node.localConfig.DESCRIPTOR.fields_by_name['lora'],
                                        cancel_callback=None)
