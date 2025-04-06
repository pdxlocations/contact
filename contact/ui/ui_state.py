class MenuState:
    def __init__(self):
        self.menu_index = []        # Row we left the previous menus
        self.start_index = [0]      # Row to start the menu if it doesn't all fit
        self.selected_index = 0     # Selected Row
        self.current_menu = {}      # Contents of the current menu
        self.menu_path = []         # Menu Path
        self.show_save_option = False

class UIState:
    def __init__(self):
        self.interface = None
        # self.lock = None
        # self.display_log = False
        # self.all_messages = {}
        # self.channel_list = []
        # self.notifications = []
        # self.packet_buffer = []
        # self.node_list = []
        # self.myNodeNum = 0
        # self.selected_channel = 0
        # self.selected_message = 0
        # self.selected_node = 0
        # self.current_window = 0