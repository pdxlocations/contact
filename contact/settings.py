import contextlib
import curses
import io
import logging
import sys
import traceback

import contact.ui.default_config as config
from contact.utilities.input_handlers import get_list_input
from contact.ui.colors import setup_colors
from contact.ui.splash import draw_splash
from contact.ui.control_ui import set_region, settings_menu
from contact.utilities.arg_parser import setup_parser
from contact.utilities.interfaces import initialize_interface


def main(stdscr: curses.window) -> None:
    output_capture = io.StringIO()
    try:
        with contextlib.redirect_stdout(output_capture), contextlib.redirect_stderr(output_capture):
            setup_colors()
            draw_splash(stdscr)
            curses.curs_set(0)
            stdscr.keypad(True)

            parser = setup_parser()
            args = parser.parse_args()
            interface = initialize_interface(args)

            if interface.localNode.localConfig.lora.region == 0:
                confirmation = get_list_input("Your region is UNSET.  Set it now?", "Yes", ["Yes", "No"])
                if confirmation == "Yes":
                    set_region(interface)
                    interface.close()
                    interface = initialize_interface(args)
            stdscr.clear()
            stdscr.refresh()
            settings_menu(stdscr, interface)

    except Exception as e:
        console_output = output_capture.getvalue()
        logging.error("An error occurred: %s", e)
        logging.error("Traceback: %s", traceback.format_exc())
        logging.error("Console output before crash:\n%s", console_output)
        raise


logging.basicConfig(  # Run `tail -f client.log` in another terminal to view live
    filename=config.log_file_path,
    level=logging.WARNING,  # DEBUG, INFO, WARNING, ERROR, CRITICAL)
    format="%(asctime)s - %(levelname)s - %(message)s",
)

if __name__ == "__main__":
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
