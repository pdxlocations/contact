import asyncio
import io
import contextlib
import socket
import logging

from .interfaces import initialize_interface
import globals


test_connection_seconds = 20
retry_connection_seconds = 3

# Function to get firmware version
def getNodeFirmware(interface):
    try:
        output_capture = io.StringIO()
        with contextlib.redirect_stdout(output_capture), contextlib.redirect_stderr(output_capture):
            interface.localNode.getMetadata()

        console_output = output_capture.getvalue()

        if "firmware_version" in console_output:
            return console_output.split("firmware_version: ")[1].split("\n")[0]

        return -1
    except (socket.error, BrokenPipeError, ConnectionResetError, Exception) as e:
        logging.warning(f"Error retrieving firmware: {e}")
        raise e  # Propagate the error to handle reconnection

# Async function to retry connection
async def retry_interface(args):
    logging.warning("Retrying connection to the interface...")
    await asyncio.sleep(retry_connection_seconds)  # Wait before retrying

    try:
        globals.interface = initialize_interface(args)
        if globals.interface and hasattr(globals.interface, 'localNode'):
            logging.warning("Interface reinitialized successfully.")
            return globals.interface
        else:
            logging.error("Failed to reinitialize interface: Missing localNode or invalid interface.")
            globals.interface = None  # Clear invalid interface
            return None

    except (ConnectionRefusedError, socket.error, Exception) as e:
        logging.error(f"Failed to reinitialize interface: {e}")
        globals.interface = None
        return None

# Function to check connection and reconnect if needed
async def check_and_reconnect(args):
    if globals.interface is None:
        logging.error("No valid interface. Attempting to reconnect...")
        interface = await retry_interface(args)
        return interface

    try:
        # logging.info("Checking interface connection...")
        fw_ver = getNodeFirmware(globals.interface)
        if fw_ver != -1:
            return globals.interface
        else:
            raise Exception("Failed to retrieve firmware version.")

    except (socket.error, BrokenPipeError, ConnectionResetError, Exception) as e:
        logging.error(f"Error with the interface, setting to None and attempting reconnect: {e}")
        globals.interface = None
        return await retry_interface(args)

# Main watchdog loop
async def watchdog(args):
    while True:  # Infinite loop for continuous monitoring
        await asyncio.sleep(test_connection_seconds)
        globals.interface = await check_and_reconnect(args)
        if globals.interface:
            pass  # Interface is connected
        else:
            logging.error("Interface connection failed. Retrying...")