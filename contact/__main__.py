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
from contact.utilities.i18n import t
from contact.ui.dialog import dialog
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
def prompt_region_if_unset(args: object) -> None:
    """Prompt user to set region if it is unset."""
    confirmation = get_list_input("Your region is UNSET. Set it now?", "Yes", ["Yes", "No"])
    if confirmation == "Yes":
        set_region(interface_state.interface)
        interface_state.interface.close()
        interface_state.interface = initialize_interface(args)


def initialize_globals() -> None:
    """Initializes interface and shared globals."""

    interface_state.myNodeNum = get_nodeNum()
    ui_state.channel_list = get_channels()
    ui_state.node_list = get_node_list()
    ui_state.single_pane_mode = config.single_pane_mode.lower() == "true"
    pub.subscribe(on_receive, "meshtastic.receive")

    init_nodedb()
    load_messages_from_db()


def main(stdscr: curses.window) -> None:
    """Main entry point for the curses UI."""

    output_capture = io.StringIO()
    try:
        setup_colors()
        ensure_min_rows(stdscr)
        draw_splash(stdscr)

        args = setup_parser().parse_args()

        if getattr(args, "settings", False):
            subprocess.run([sys.executable, "-m", "contact.settings"], check=True)
            return

        logging.info("Initializing interface...")
        with app_state.lock:
            interface_state.interface = initialize_interface(args)

            if interface_state.interface.localNode.localConfig.lora.region == 0:
                prompt_region_if_unset(args)

            initialize_globals()
            logging.info("Starting main UI")

            stdscr.clear()
            stdscr.refresh()

        try:
            with contextlib.redirect_stdout(output_capture), contextlib.redirect_stderr(output_capture):
                main_ui(stdscr)
        except Exception:
            console_output = output_capture.getvalue()
            logging.error("Uncaught exception inside main_ui")
            logging.error("Traceback:\n%s", traceback.format_exc())
            logging.error("Console output:\n%s", console_output)
            return

    except Exception:
        raise


def ensure_min_rows(stdscr: curses.window, min_rows: int = 11) -> None:
    while True:
        rows, _ = stdscr.getmaxyx()
        if rows >= min_rows:
            return
        dialog(
            t("ui.dialog.resize_title", default="Resize Terminal"),
            t(
                "ui.dialog.resize_body",
                default="Please resize the terminal to at least {rows} rows.",
                rows=min_rows,
            ),
        )
        curses.update_lines_cols()
        stdscr.clear()
        stdscr.refresh()


def start() -> None:
    """Entry point for the application."""

    if "--help" in sys.argv or "-h" in sys.argv:
        setup_parser().print_help()
        sys.exit(0)

    try:
        curses.wrapper(main)
        interface_state.interface.close()
    except KeyboardInterrupt:
        logging.info("User exited with Ctrl+C")
        interface_state.interface.close()
        sys.exit(0)
    except Exception as e:
        logging.critical("Fatal error", exc_info=True)
        try:
            curses.endwin()
        except Exception:
            pass
        print("Fatal error:", e)
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    start()
