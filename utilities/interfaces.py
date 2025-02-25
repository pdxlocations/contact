import logging
import contextlib
import io
import meshtastic.serial_interface, meshtastic.tcp_interface, meshtastic.ble_interface
import globals


def initialize_interface(args):
    try:
        if args.ble:
            return meshtastic.ble_interface.BLEInterface(args.ble if args.ble != "any" else None)
        elif args.host:
            return meshtastic.tcp_interface.TCPInterface(args.host)
        else:
            try:
                # Suppress stdout and stderr during SerialInterface initialization
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    return meshtastic.serial_interface.SerialInterface(args.port)
            except PermissionError as ex:
                logging.error(f"You probably need to add yourself to the `dialout` group to use a serial connection. {ex}")
            except Exception as ex:
                # Suppress specific message but log unexpected errors
                if "No Serial Meshtastic device detected" not in str(ex):
                    logging.error(f"Unexpected error initializing interface: {ex}")

            # Attempt TCP connection if Serial fails
            if globals.interface.devPath is None:
                return meshtastic.tcp_interface.TCPInterface("meshtastic.local")

    except Exception as ex:
        logging.critical(f"Fatal error initializing interface: {ex}")