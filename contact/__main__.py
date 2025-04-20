#!/usr/bin/env python3

"""
Contact - A Console UI for Meshtastic by http://github.com/pdxlocations
Powered by Meshtastic.org

Meshtastic® is a registered trademark of Meshtastic LLC.
Meshtastic software components are released under various licenses—see GitHub for details.
No warranty is provided. Use at your own risk.
"""

# Standard library
import contextlib
import curses
import io
import logging
import os
import subprocess
import sys
import threading
import traceback

# Third-party
from pubsub import pub

# Local application
import contact.ui.default_config as config
from contact.message_handlers.rx_handler import on_receive
from contact.settings import set_region
from contact.ui.colors import setup_colors
from contact.ui.contact_ui import main_ui
from contact.ui.splash import draw_splash
from contact.utilities.arg_parser import setup_parser
from contact.utilities.db_handler import init_nodedb, load_messages_from_db
from contact.utilities.input_handlers import get_list_input
from contact.utilities.interfaces import initialize_interface
from contact.utilities.utils import get_channels, get_nodeNum, get_node_list
from contact.utilities.singleton import ui_state, interface_state, app_state

# ------------------------------------------------------------------------------
# Environment & Logging Setup
# ------------------------------------------------------------------------------

os.environ["NCURSES_NO_UTF8_ACS"] = "1"
os.environ["LANG"] = "C.UTF-8"
os.environ.setdefault("TERM", "xterm-256color")
if os.environ.get("COLORTERM") == "gnome-terminal":
    os.environ["TERM"] = "xterm-256color"

logging.basicConfig(
    filename=config.log_file_path, level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

app_state.lock = threading.Lock()

# ------------------------------------------------------------------------------
# Main Program Logic
# ------------------------------------------------------------------------------


def initialize_globals(args) -> None:
    """Initializes interface and shared globals."""
    interface_state.interface = initialize_interface(args)

    # Prompt for region if unset
    if interface_state.interface.localNode.localConfig.lora.region == 0:
        confirmation = get_list_input("Your region is UNSET. Set it now?", "Yes", ["Yes", "No"])
        if confirmation == "Yes":
            set_region(interface_state.interface)
            interface_state.interface.close()
            interface_state.interface = initialize_interface(args)

    interface_state.myNodeNum = get_nodeNum()
    ui_state.channel_list = get_channels()
    ui_state.node_list = get_node_list()
    pub.subscribe(on_receive, "meshtastic.receive")

    init_nodedb()
    load_messages_from_db()


def main(stdscr: curses.window) -> None:
    """Main entry point for the curses UI."""
    output_capture = io.StringIO()

    try:
        with contextlib.redirect_stdout(output_capture), contextlib.redirect_stderr(output_capture):
            setup_colors()
            draw_splash(stdscr)

            args = setup_parser().parse_args()

            if getattr(args, "settings", False):
                subprocess.run([sys.executable, "-m", "contact.settings"], check=True)
                return

            logging.info("Initializing interface...")
            with app_state.lock:
                initialize_globals(args)
                logging.info("Starting main UI")

            main_ui(stdscr)

    except Exception as e:
        console_output = output_capture.getvalue()
        logging.error("Uncaught exception: %s", e)
        logging.error("Traceback: %s", traceback.format_exc())
        logging.error("Console output:\n%s", console_output)
        raise


def start() -> None:
    """Launch curses wrapper and redirect logs to file."""

    if "--help" in sys.argv or "-h" in sys.argv:
        setup_parser().print_help()
        sys.exit(0)

    with open(config.log_file_path, "a", buffering=1) as log_f:
        sys.stdout = log_f
        sys.stderr = log_f

        with contextlib.redirect_stdout(log_f), contextlib.redirect_stderr(log_f):
            try:
                curses.wrapper(main)
            except KeyboardInterrupt:
                logging.info("User exited with Ctrl+C")
                sys.exit(0)
            except Exception as e:
                logging.error("Fatal error: %s", e)
                logging.error("Traceback: %s", traceback.format_exc())
                sys.exit(1)


if __name__ == "__main__":
    start()
