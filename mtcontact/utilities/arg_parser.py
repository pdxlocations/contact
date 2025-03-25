import argparse

def setup_parser():
    parser = argparse.ArgumentParser(
            add_help=True,
            epilog="If no connection arguments are specified, we attempt a serial connection and then a TCP connection to localhost.")

    connOuter = parser.add_argument_group('Connection', 'Optional arguments to specify a device to connect to and how.')
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
        "--ble",
        "-b",
        help="The BLE device MAC address or name to connect to.",
        nargs="?",
        default=None,
        const="any"
    )

    return parser