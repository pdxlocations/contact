#!/usr/bin/env python3

'''
Contact - A Console UI for Meshtastic by http://github.com/pdxlocations
Powered by Meshtastic.org
V 1.2.0
'''

import curses
from pubsub import pub
import os
import logging
import traceback

from utilities.arg_parser import setup_parser
from utilities.interfaces import initialize_interface
from message_handlers.rx_handler import on_receive
from ui.curses_ui import main_ui, draw_splash
from utilities.utils import get_channels, get_node_list, get_nodeNum
from db_handler import init_nodedb, load_messages_from_db
import default_config as config
import globals

import os

# Set ncurses compatibility settings
os.environ["NCURSES_NO_UTF8_ACS"] = "1"
os.environ["LANG"] = "C.UTF-8"
os.environ.setdefault("TERM", "xterm-256color")
if os.environ.get("COLORTERM") == "gnome-terminal":
    os.environ["TERM"] = "xterm-256color"

# Configure logging
# Run `tail -f client.log` in another terminal to view live
logging.basicConfig(
    filename=config.log_file_path,
    level=logging.INFO,  # DEBUG, INFO, WARNING, ERROR, CRITICAL)
    format="%(asctime)s - %(levelname)s - %(message)s"
)

def main(stdscr):
    try:
        draw_splash(stdscr)
        parser = setup_parser()
        args = parser.parse_args()

        logging.info("Initializing interface %s", args)
        globals.interface = initialize_interface(args)
        logging.info("Interface initialized")
        globals.myNodeNum = get_nodeNum()
        globals.channel_list = get_channels()
        globals.node_list = get_node_list()
        pub.subscribe(on_receive, 'meshtastic.receive')
        init_nodedb()
        load_messages_from_db()
        logging.info("Starting main UI")
        main_ui(stdscr)
    except Exception as e:
        logging.error("An error occurred: %s", e)
        logging.error("Traceback: %s", traceback.format_exc())
        raise

if __name__ == "__main__":
    try:
        curses.wrapper(main)
    except Exception as e:
        logging.error("Fatal error in curses wrapper: %s", e)
        logging.error("Traceback: %s", traceback.format_exc())