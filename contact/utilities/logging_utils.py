import logging
import os
import sys

import contact.ui.default_config as config


def configure_logging(level: int) -> None:
    """Set up file logging or exit with instructions for fixing its path."""
    try:
        logging.basicConfig(
            filename=config.log_file_path,
            level=level,
            format="%(asctime)s - %(levelname)s - %(message)s",
            force=True,
        )
    except OSError as error:
        print(
            f"Unable to open log file: {os.path.abspath(config.log_file_path)}\n"
            f"{error}\n"
            f"Please edit config.json at: {os.path.abspath(config.json_file_path)}\n"
            'Set "log_file_path" to a file in an existing, writable directory, '
            "then restart Contact.",
            file=sys.stderr,
        )
        raise SystemExit(1) from None
