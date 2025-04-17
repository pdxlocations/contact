import logging
import meshtastic.serial_interface, meshtastic.tcp_interface, meshtastic.ble_interface


def initialize_interface(args):
    try:

        if args.ble:
            return meshtastic.ble_interface.BLEInterface(args.ble if args.ble != "any" else None)

        elif args.host:
            try:
                if ":" in args.host:
                    tcp_hostname, tcp_port = args.host.split(":")
                else:
                    tcp_hostname = args.host
                    tcp_port = meshtastic.tcp_interface.DEFAULT_TCP_PORT
                return meshtastic.tcp_interface.TCPInterface(tcp_hostname, portNumber=tcp_port)
            except Exception as ex:
                logging.error(f"Error connecting to {args.host}. {ex}")
        else:
            try:
                client = meshtastic.serial_interface.SerialInterface(args.port)
            except FileNotFoundError as ex:
                logging.error(f"The serial device at '{args.port}' was not found. {ex}")
            except PermissionError as ex:
                logging.error(
                    f"You probably need to add yourself to the `dialout` group to use a serial connection. {ex}"
                )
            except Exception as ex:
                logging.error(f"Unexpected error initializing interface: {ex}")
            except OSError as ex:
                logging.error(f"The serial device couldn't be opened, it might be in use by another process. {ex}")
            if client.devPath is None:
                try:
                    client = meshtastic.tcp_interface.TCPInterface("localhost")
                except Exception as ex:
                    logging.error(f"Error connecting to localhost:{ex}")

            return client

    except Exception as ex:
        logging.critical(f"Fatal error initializing interface: {ex}")
