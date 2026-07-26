import logging
import time
import meshtastic.serial_interface, meshtastic.tcp_interface, meshtastic.ble_interface


def interface_is_connected(interface) -> bool:
    """Return the transport-independent connection state for an interface.

    TCPInterface deliberately leaves ``stream`` set to ``None`` and uses its
    ``socket`` instead.  Checking only ``stream`` therefore treats every TCP
    connection (including meshtasticd) as disconnected.
    """
    if interface is None:
        return False

    connected = getattr(interface, "isConnected", None)
    if hasattr(connected, "is_set"):
        return connected.is_set()
    if isinstance(connected, bool):
        return connected
    if hasattr(interface, "socket"):
        return getattr(interface, "socket", None) is not None
    if hasattr(interface, "stream"):
        return getattr(interface, "stream", None) is not None
    return getattr(interface, "localNode", None) is not None


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


def reconnect_interface(args, attempts: int = 20, delay_seconds: float = 1.0):
    last_error = None

    for attempt in range(attempts):
        try:
            interface = initialize_interface(args)
            if interface_is_connected(interface) and getattr(interface, "localNode", None) is not None and getattr(
                interface.localNode, "localConfig", None
            ) is not None:
                return interface
            last_error = RuntimeError("interface did not complete connection setup")
            try:
                interface.close()
            except Exception:
                pass
        except Exception as ex:
            last_error = ex

        if attempt < attempts - 1:
            time.sleep(delay_seconds)

    raise RuntimeError("Failed to reconnect to the Meshtastic node") from last_error
