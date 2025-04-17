from typing import Any, Union, List, Dict


class MenuState:
    def __init__(self):
        self.menu_index: List[int] = []  # Row we left the previous menus
        self.start_index: List[int] = [0]  # Row to start the menu if it doesn't all fit
        self.selected_index: int = 0  # Selected Row
        self.current_menu: Union[Dict[str, Any], List[Any], str, int] = {}  # Contents of the current menu
        self.menu_path: List[str] = []  # Menu Path
        self.show_save_option: bool = False  # Display 'Save'
