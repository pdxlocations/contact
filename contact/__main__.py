#!/usr/bin/env python3

'''
Contact - A Console UI for Meshtastic by http://github.com/pdxlocations
Powered by Meshtastic.org

Meshtastic® is a registered trademark of Meshtastic LLC. Meshtastic software components are released under various licenses, see GitHub for details. No warranty is provided - use at your own risk.
'''

import contextlib
import curses
import os
from pubsub import pub
import sys
import io
import logging
import subprocess
import traceback
import threading

from contact.utilities.db_handler import init_nodedb, load_messages_from_db
from contact.message_handlers.rx_handler import on_receive
from contact.settings import set_region
from contact.ui.contact_ui import main_ui
from contact.ui.colors import setup_colors
from contact.ui.splash import draw_splash
import contact.ui.default_config as config
from contact.utilities.arg_parser import setup_parser
from contact.utilities.interfaces import initialize_interface
from contact.utilities.input_handlers import get_list_input
from contact.utilities.utils import get_channels, get_node_list, get_nodeNum

import contact.globals as globals
from contact.ui.ui_state import NodeState

node_state = NodeState()

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

globals.lock = threading.Lock()

def main(stdscr):
    output_capture = io.StringIO()
    try:
        with contextlib.redirect_stdout(output_capture), contextlib.redirect_stderr(output_capture):

            setup_colors()
            draw_splash(stdscr)
            parser = setup_parser()
            args = parser.parse_args()

            # Check if --settings was passed and run settings.py as a subprocess
            if getattr(args, 'settings', False):
                subprocess.run([sys.executable, "-m", "contact.settings"], check=True)
                return

            logging.info("Initializing interface %s", args)
            with globals.lock:
                node_state.interface = initialize_interface(args)

                if node_state.interface.localNode.localConfig.lora.region == 0:
                    confirmation = get_list_input("Your region is UNSET. Set it now?", "Yes", ["Yes", "No"])
                    if confirmation == "Yes":
                        set_region(node_state)
                        node_state.interface.close()
                        node_state.interface = initialize_interface(args)

                logging.info("Interface initialized")
                get_nodeNum(node_state)
                globals.channel_list = get_channels()
                globals.node_list = get_node_list()
                pub.subscribe(on_receive, 'meshtastic.receive')
                init_nodedb(node_state)
                load_messages_from_db(node_state)
                logging.info("Starting main UI")

            main_ui(stdscr, node_state)

    except Exception as e:
        console_output = output_capture.getvalue()
        logging.error("An error occurred: %s", e)
        logging.error("Traceback: %s", traceback.format_exc())
        logging.error("Console output before crash:\n%s", console_output)
        raise  # Re-raise only unexpected errors

def start():
    log_file = config.log_file_path
    log_f = open(log_file, "a", buffering=1)  # Enable line-buffering for immediate log writes

    sys.stdout = log_f
    sys.stderr = log_f

    with contextlib.redirect_stderr(log_f), contextlib.redirect_stdout(log_f):
        try:
            curses.wrapper(main)
        except KeyboardInterrupt:
            logging.info("User exited with Ctrl+C or Ctrl+X")  # Clean exit logging
            sys.exit(0)  # Ensure a clean exit
        except Exception as e:
            logging.error("Fatal error in curses wrapper: %s", e)
            logging.error("Traceback: %s", traceback.format_exc())
            sys.exit(1)  # Exit with an error code

if __name__ == "__main__":
    start()
