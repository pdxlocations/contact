import logging
import meshtastic.serial_interface, meshtastic.tcp_interface, meshtastic.ble_interface
import contact.globals as globals

def initialize_interface(args):
    try:
        if args.ble:
            return meshtastic.ble_interface.BLEInterface(args.ble if args.ble != "any" else None)
        elif args.host:
            return meshtastic.tcp_interface.TCPInterface(args.host)
        else:
            try:
                client = meshtastic.serial_interface.SerialInterface(args.port)
            except PermissionError as ex:
                logging.error(f"You probably need to add yourself to the `dialout` group to use a serial connection. {ex}")
            except Exception as ex:
                logging.error(f"Unexpected error initializing interface: {ex}")
            if client.devPath is None:
                client = meshtastic.tcp_interface.TCPInterface("localhost")
    
            return client
    except Exception as ex:
        logging.critical(f"Fatal error initializing interface: {ex}")
    