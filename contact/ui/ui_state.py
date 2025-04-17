from typing import Any


class MenuState:
    def __init__(self):
        self.menu_index: list[int] = []  # Row we left the previous menus
        self.start_index: list[int] = [0]  # Row to start the menu if it doesn't all fit
        self.selected_index: int = 0  # Selected Row
        self.current_menu: dict[str, Any] | list[Any] | str | int = {}  # Contents of the current menu
        self.menu_path: list[str] = []  # Menu Path
        self.show_save_option: bool = False  # Display 'Save'
