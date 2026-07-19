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
    need_redraw: bool = False


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
    last_sent_time: float = 0.0
    last_traceroute_time: float = 0.0
    bot_mode_enabled: bool = False

    selected_index: int = 0
    start_index: List[int] = field(default_factory=lambda: [0, 0, 0])
    show_save_option: bool = False
    menu_path: List[str] = field(default_factory=list)
    single_pane_mode: bool = False
    redraw_channels: bool = False
    redraw_messages: bool = False
    redraw_nodes: bool = False
    redraw_packetlog: bool = False
    redraw_full_ui: bool = False
    scroll_messages_to_bottom: bool = False
    preserve_message_selection: bool = False
    oldest_message_rowid: Dict[Union[str, int], int] = field(default_factory=dict)
    has_older_messages: Dict[Union[str, int], bool] = field(default_factory=dict)
    message_line_ranges: Dict[Union[str, int], List[tuple]] = field(default_factory=dict)
    highlighted_message_range: tuple = field(default_factory=tuple)
    message_packet_ids: Dict[Union[str, int], List[Any]] = field(default_factory=dict)
    reply_id: Any = None
    reply_context: str = ""
    reply_id_unavailable: bool = False


@dataclass
class InterfaceState:
    interface: Any = None
    myNodeNum: int = 0


@dataclass
class AppState:
    lock: Any = None
