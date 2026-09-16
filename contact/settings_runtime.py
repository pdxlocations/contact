import contextlib
import curses
import io
import logging
import sys
import traceback

import contact.ui.default_config as config
from contact.ui.colors import setup_colors
from contact.ui.control_ui import set_region, settings_menu
from contact.ui.dialog import dialog
from contact.ui.splash import draw_splash
from contact.utilities.i18n import t
from contact.utilities.input_handlers import get_list_input
from contact.utilities.interfaces import initialize_interface, reconnect_interface
from contact.utilities.logging_utils import configure_logging
from contact.utilities.shared_state import app_state


def close_interface(interface: object) -> None:
    if interface is None:
        return
    with contextlib.suppress(Exception):
        interface.close()


def main(stdscr: curses.window, args: object) -> None:
    app_state.connection_args = args
    output_capture = io.StringIO()
    interface = None
    try:
        with contextlib.redirect_stdout(output_capture), contextlib.redirect_stderr(output_capture):
            setup_colors()
            ensure_min_rows(stdscr)
            draw_splash(stdscr)
            curses.curs_set(0)
            stdscr.keypad(True)

            interface = initialize_interface(args, status_callback=lambda status: draw_splash(stdscr, status))

            if interface.localNode.localConfig.lora.region == 0:
                confirmation = get_list_input(
                    t("ui.confirm.region_unset", default="Your region is UNSET.  Set it now?"),
                    "Yes",
                    ["Yes", "No"],
                )
                if confirmation == "Yes":
                    set_region(interface)
                    close_interface(interface)
                    draw_splash(stdscr)
                    interface = reconnect_interface(args)
            stdscr.clear()
            stdscr.refresh()
            settings_menu(stdscr, interface)

    except Exception as e:
        console_output = output_capture.getvalue()
        logging.error("An error occurred: %s", e)
        logging.error("Traceback: %s", traceback.format_exc())
        logging.error("Console output before crash:\n%s", console_output)
        raise
    finally:
        close_interface(interface)


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


def start(args: object) -> None:
    configure_logging(logging.WARNING)
    with open(config.log_file_path, "a", buffering=1) as log_file:
        with contextlib.redirect_stderr(log_file), contextlib.redirect_stdout(log_file):
            try:
                curses.wrapper(main, args)
            except KeyboardInterrupt:
                logging.info("User exited with Ctrl+C or Ctrl+X")
            except Exception:
                logging.exception("Fatal error in curses wrapper")
                sys.exit(1)
