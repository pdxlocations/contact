from typing import Any, Union, List, Dict
from dataclasses import dataclass, field


@dataclass
class MenuState:
    menu_index: List[int] = field(default_factory=list)
    start_index: List[int] = field(default_factory=lambda: [0])
    selected_index: int = 0
    current_menu: Union[Dict[str, Any], List[Any], str, int] = field(default_factory=dict)
    menu_path: List[str] = field(default_factory=list)
    show_save_option: bool = False


@dataclass
class ChatUIState:
    display_log: bool = False
    channel_list: List[str] = field(default_factory=list)
    all_messages: Dict[str, List[str]] = field(default_factory=dict)
    notifications: List[str] = field(default_factory=list)
    packet_buffer: List[str] = field(default_factory=list)
    node_list: List[str] = field(default_factory=list)
    selected_channel: int = 0
    selected_message: int = 0
    selected_node: int = 0
    current_window: int = 0

    selected_index: int = 0
    start_index: List[int] = field(default_factory=lambda: [0, 0, 0])
    show_save_option: bool = False
    menu_path: List[str] = field(default_factory=list)


@dataclass
class InterfaceState:
    interface: Any = None
    myNodeNum: int = 0


@dataclass
class AppState:
    lock: Any = None
