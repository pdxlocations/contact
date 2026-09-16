"""Parse command-line options before initializing Contact's runtime."""

from contact.utilities.arg_parser import setup_parser


def start(argv=None) -> None:
    args = setup_parser().parse_args(argv)
    if args.settings:
        from contact.settings_runtime import start as start_runtime
    else:
        from contact.runtime import start as start_runtime
    start_runtime(args)


if __name__ == "__main__":
    start()
