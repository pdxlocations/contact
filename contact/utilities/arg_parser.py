from argparse import ArgumentParser
from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("contact")
except PackageNotFoundError:
    __version__ = "dev"


def setup_parser() -> ArgumentParser:
    parser = ArgumentParser(
        add_help=True,
        epilog="If no connection arguments are specified, we attempt a serial connection and then a TCP connection to localhost.",
    )
    parser.add_argument("--version", "-V", action="version", version=__version__)

    connOuter = parser.add_argument_group(
        "Connection", "Optional arguments to specify a device to connect to and how."
    )
    conn = connOuter.add_mutually_exclusive_group()
    conn.add_argument(
        "--port",
        "--serial",
        "-s",
        help="The port to connect to via serial, e.g. `/dev/ttyUSB0`.",
        nargs="?",
        default=None,
        const=None,
    )
    conn.add_argument(
        "--host",
        "--tcp",
        "-t",
        help="The hostname or IP address to connect to using TCP.",
        nargs="?",
        default=None,
        const="localhost",
    )
    conn.add_argument(
        "--ble", "-b", help="The BLE device MAC address or name to connect to.", nargs="?", default=None, const="any"
    )
    parser.add_argument(
        "--settings", "--set", "--control", "-c", help="Launch directly into the settings", action="store_true"
    )
    parser.add_argument(
        "--demo-screenshot",
        help="Launch with a fake interface and seeded demo data for screenshots/testing.",
        action="store_true",
    )

    return parser
