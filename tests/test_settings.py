from argparse import Namespace
from types import SimpleNamespace
import unittest
from unittest import mock

import contact.settings_runtime as settings


class SettingsRuntimeTests(unittest.TestCase):
    def test_main_closes_interface_after_normal_settings_exit(self) -> None:
        stdscr = mock.Mock()
        args = Namespace()
        interface = mock.Mock()
        interface.localNode = SimpleNamespace(localConfig=SimpleNamespace(lora=SimpleNamespace(region=1)))

        with mock.patch.object(settings, "setup_colors"):
            with mock.patch.object(settings, "ensure_min_rows"):
                with mock.patch.object(settings, "draw_splash"):
                    with mock.patch.object(settings.curses, "curs_set"):
                        with mock.patch.object(settings, "initialize_interface", return_value=interface):
                            with mock.patch.object(settings, "settings_menu") as settings_menu:
                                settings.main(stdscr, args)

        settings_menu.assert_called_once_with(stdscr, interface)
        interface.close.assert_called_once_with()

    def test_main_closes_reconnected_interface_after_region_reset(self) -> None:
        stdscr = mock.Mock()
        args = Namespace()
        old_interface = mock.Mock()
        old_interface.localNode = SimpleNamespace(localConfig=SimpleNamespace(lora=SimpleNamespace(region=0)))
        new_interface = mock.Mock()
        new_interface.localNode = SimpleNamespace(localConfig=SimpleNamespace(lora=SimpleNamespace(region=1)))

        with mock.patch.object(settings, "setup_colors"):
            with mock.patch.object(settings, "ensure_min_rows"):
                with mock.patch.object(settings, "draw_splash"):
                    with mock.patch.object(settings.curses, "curs_set"):
                        with mock.patch.object(settings, "initialize_interface", return_value=old_interface):
                            with mock.patch.object(settings, "get_list_input", return_value="Yes"):
                                with mock.patch.object(settings, "set_region") as set_region:
                                    with mock.patch.object(
                                        settings, "reconnect_interface", return_value=new_interface
                                    ) as reconnect_interface:
                                        with mock.patch.object(settings, "settings_menu") as settings_menu:
                                            settings.main(stdscr, args)

        set_region.assert_called_once_with(old_interface)
        reconnect_interface.assert_called_once_with(args)
        settings_menu.assert_called_once_with(stdscr, new_interface)
        old_interface.close.assert_called_once_with()
        new_interface.close.assert_called_once_with()

    def test_main_closes_interface_when_settings_menu_raises(self) -> None:
        stdscr = mock.Mock()
        args = Namespace()
        interface = mock.Mock()
        interface.localNode = SimpleNamespace(localConfig=SimpleNamespace(lora=SimpleNamespace(region=1)))

        with mock.patch.object(settings, "setup_colors"):
            with mock.patch.object(settings, "ensure_min_rows"):
                with mock.patch.object(settings, "draw_splash"):
                    with mock.patch.object(settings.curses, "curs_set"):
                        with mock.patch.object(settings, "initialize_interface", return_value=interface):
                            with mock.patch.object(settings, "settings_menu", side_effect=RuntimeError("boom")):
                                with self.assertRaises(RuntimeError):
                                    settings.main(stdscr, args)

        interface.close.assert_called_once_with()
