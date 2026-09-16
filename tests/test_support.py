import threading

import contact.ui.default_config as config
from contact.ui.ui_state import AppState, ChatUIState, InterfaceState, MenuState
from contact.utilities.shared_state import app_state, interface_state, menu_state, ui_state


def reset_shared_state() -> None:
    _reset_instance(ui_state, ChatUIState())
    _reset_instance(interface_state, InterfaceState())
    _reset_instance(menu_state, MenuState())
    _reset_instance(app_state, AppState())
    app_state.lock = threading.Lock()


def restore_config(saved: dict) -> None:
    for key, value in saved.items():
        setattr(config, key, value)


def snapshot_config(*keys: str) -> dict:
    return {key: getattr(config, key) for key in keys}


def _reset_instance(target: object, replacement: object) -> None:
    target.__dict__.clear()
    target.__dict__.update(replacement.__dict__)
