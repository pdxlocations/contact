class MenuState:
    def __init__(self):
        self.menu_index = []        # Row we left the previous menus
        self.start_index = [0]      # Row to start the menu if it doesn't all fit
        self.selected_index = 0     # Selected Row
        self.current_menu = {}      # Contents of the current menu
        self.menu_path = []         # Menu Path
        self.show_save_option = False