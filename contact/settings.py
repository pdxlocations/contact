"""Standalone command-line entry point for node settings."""

from contact.utilities.arg_parser import setup_parser


def start(argv=None) -> None:
    args = setup_parser().parse_args(argv)
    from contact.settings_runtime import start as start_runtime

    start_runtime(args)


if __name__ == "__main__":
    start()
