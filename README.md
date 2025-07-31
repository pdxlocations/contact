## Contact - A Console UI for Meshtastic

#### Powered by Meshtastic.org

### Install with:
```bash
pip install contact
```

This Python curses client for Meshtastic is a terminal-based client designed to manage device settings, enable mesh chat communication, and handle configuration backups and restores.


<img width="846" alt="Contact - Main UI Screenshot" src="https://github.com/user-attachments/assets/d2996bfb-2c6d-46a8-b820-92a9143375f4">

<br><br>
The settings dialogue can be accessed within the client or may be run standalone to configure your node by launching `contact --settings` or `contact -c`

<img width="696" alt="Screenshot 2025-04-08 at 6 10 06 PM" src="https://github.com/user-attachments/assets/3d5e3964-f009-4772-bd6e-91b907c65a3b" />

## Message Persistence 

All messages will saved in a SQLite DB and restored upon relaunch of the app.  You may delete `client.db` if you wish to erase all stored messages and node data.  If multiple nodes are used, each will independently store data in the database, but the data will not be shared or viewable between nodes.

## Client Configuration

By navigating to Settings -> App Settings, you may customize your UI's icons, colors, and more!

## Commands

- `↑→↓←` = Navigate around the UI.
- `ENTER` = Send a message typed in the Input Window, or with the Node List highlighted, select a node to DM
-  `` ` `` = Open the Settings dialogue
- `CTRL` + `p` = Hide/show a log of raw received packets.
- `CTRL` + `t` = With the Node List highlighted, send a traceroute to the selected node 
- `CTRL` + `d` = With the Channel List hightlighted, archive a chat to reduce UI clutter. Messages will be saved in the db and repopulate if you send or receive a DM from this user.
- `ESC` = Exit out of the Settings Dialogue, or Quit the application if settings are not displayed.

### Search
- Press `CTRL` + `/` while the nodes or channels window is highlighted to start search
- Type text to search as you type, first matching item will be selected, starting at current selected index
- Press Tab to find next match starting from the current index - search wraps around if necessary
- Press Esc or Enter to exit search mode

## Arguments

You can pass the following arguments to the client:

### Connection Arguments

Optional arguments to specify a device to connect to and how.

- `--port`, `--serial`, `-s`: The port to connect to via serial, e.g. `/dev/ttyUSB0`.
- `--host`, `--tcp`, `-t`: The hostname or IP address to connect to using TCP, will default to localhost if no host is passed.
- `--ble`, `-b`: The BLE device MAC address or name to connect to.
- `--settings`, `--set`, `--control`, `-c`: Launch directly into the settings.

If no connection arguments are specified, the client will attempt a serial connection and then a TCP connection to localhost.

### Example Usage

```sh
contact --port /dev/ttyUSB0
contact --host 192.168.1.1
contact --ble BlAddressOfDevice
```
To quickly connect to localhost, use:
```sh
contact -t
```
## Install in development (editable) mode:
```bash
git clone https://github.com/pdxlocations/contact.git
cd contact
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```
