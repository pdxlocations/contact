import os
import sqlite3
import tempfile
from dataclasses import dataclass
from typing import Dict, List, Tuple, Union

import contact.ui.default_config as config
from contact.utilities.db_handler import get_table_name
from contact.utilities.singleton import interface_state


DEMO_DB_FILENAME = "contact_demo_client.db"
DEMO_LOCAL_NODE_NUM = 0xC0DEC0DE
DEMO_BASE_TIMESTAMP = 1738717200  # 2025-02-04 17:00:00 UTC
DEMO_CHANNELS = ["MediumFast", "Another Channel"]


@dataclass
class DemoChannelSettings:
    name: str


@dataclass
class DemoChannel:
    role: bool
    settings: DemoChannelSettings


@dataclass
class DemoLoRaConfig:
    region: int = 1
    modem_preset: int = 0


@dataclass
class DemoLocalConfig:
    lora: DemoLoRaConfig


class DemoLocalNode:
    def __init__(self, interface: "DemoInterface", channels: List[DemoChannel]) -> None:
        self._interface = interface
        self.channels = channels
        self.localConfig = DemoLocalConfig(lora=DemoLoRaConfig())

    def setFavorite(self, node_num: int) -> None:
        self._interface.nodesByNum[node_num]["isFavorite"] = True

    def removeFavorite(self, node_num: int) -> None:
        self._interface.nodesByNum[node_num]["isFavorite"] = False

    def setIgnored(self, node_num: int) -> None:
        self._interface.nodesByNum[node_num]["isIgnored"] = True

    def removeIgnored(self, node_num: int) -> None:
        self._interface.nodesByNum[node_num]["isIgnored"] = False

    def removeNode(self, node_num: int) -> None:
        self._interface.nodesByNum.pop(node_num, None)


class DemoInterface:
    def __init__(self, nodes: Dict[int, Dict[str, object]], channels: List[DemoChannel]) -> None:
        self.nodesByNum = nodes
        self.nodes = self.nodesByNum
        self.localNode = DemoLocalNode(self, channels)

    def getMyNodeInfo(self) -> Dict[str, int]:
        return {"num": DEMO_LOCAL_NODE_NUM}

    def getNode(self, selector: str) -> DemoLocalNode:
        if selector != "^local":
            raise KeyError(selector)
        return self.localNode

    def close(self) -> None:
        return


def build_demo_interface() -> DemoInterface:
    channels = [DemoChannel(role=True, settings=DemoChannelSettings(name=name)) for name in DEMO_CHANNELS]

    nodes = {
        DEMO_LOCAL_NODE_NUM: _build_node(
            DEMO_LOCAL_NODE_NUM,
            "Meshtastic fb3c",
            "fb3c",
            hops=0,
            snr=13.7,
            last_heard_offset=5,
            battery=88,
            voltage=4.1,
            favorite=True,
        ),
        0xA1000001: _build_node(0xA1000001, "KG7NDX-N2", "N2", hops=1, last_heard_offset=18, battery=79, voltage=4.0),
        0xA1000002: _build_node(0xA1000002, "Satellite II Repeater", "SAT2", hops=2, last_heard_offset=31),
        0xA1000003: _build_node(0xA1000003, "Search for Discord/Meshtastic", "DISC", hops=1, last_heard_offset=46),
        0xA1000004: _build_node(0xA1000004, "K7EOK Mobile", "MOBL", hops=1, last_heard_offset=63, battery=52),
        0xA1000005: _build_node(0xA1000005, "Turtle", "TRTL", hops=3, last_heard_offset=87),
        0xA1000006: _build_node(0xA1000006, "CARS Trewvilliger Plaza", "CARS", hops=2, last_heard_offset=121),
        0xA1000007: _build_node(0xA1000007, "No Hands!", "NHDS", hops=1, last_heard_offset=155),
        0xA1000008: _build_node(0xA1000008, "McCutie", "MCCU", hops=2, last_heard_offset=211, ignored=True),
        0xA1000009: _build_node(0xA1000009, "K1PDX", "K1PX", hops=2, last_heard_offset=267),
        0xA100000A: _build_node(0xA100000A, "Arnold Creek", "ARND", hops=1, last_heard_offset=301),
        0xA100000B: _build_node(0xA100000B, "Nansen", "NANS", hops=1, last_heard_offset=355),
        0xA100000C: _build_node(0xA100000C, "Kodin 1", "KOD1", hops=2, last_heard_offset=402),
        0xA100000D: _build_node(0xA100000D, "PH1", "PH1", hops=3, last_heard_offset=470),
        0xA100000E: _build_node(0xA100000E, "Luna", "LUNA", hops=1, last_heard_offset=501),
        0xA100000F: _build_node(0xA100000F, "sputnik1", "SPUT", hops=1, last_heard_offset=550),
        0xA1000010: _build_node(0xA1000010, "K7EOK Maplewood West", "MAPL", hops=2, last_heard_offset=602),
        0xA1000011: _build_node(0xA1000011, "KE7YVU 2", "YVU2", hops=2, last_heard_offset=655),
        0xA1000012: _build_node(0xA1000012, "DNET", "DNET", hops=1, last_heard_offset=702),
        0xA1000013: _build_node(0xA1000013, "Green Bluff", "GBLF", hops=1, last_heard_offset=780),
        0xA1000014: _build_node(0xA1000014, "Council Crest Solar", "CCST", hops=2, last_heard_offset=830),
        0xA1000015: _build_node(0xA1000015, "Meshtastic 61c7", "61c7", hops=1, last_heard_offset=901),
        0xA1000016: _build_node(0xA1000016, "Bella", "BELA", hops=2, last_heard_offset=950),
        0xA1000017: _build_node(0xA1000017, "Mojo Solar Base 4f12", "MOJO", hops=1, last_heard_offset=1010, favorite=True),
    }

    return DemoInterface(nodes=nodes, channels=channels)


def configure_demo_database(base_dir: str = "") -> str:
    if not base_dir:
        base_dir = tempfile.mkdtemp(prefix="contact_demo_")
    os.makedirs(base_dir, exist_ok=True)

    db_path = os.path.join(base_dir, DEMO_DB_FILENAME)
    if os.path.exists(db_path):
        os.remove(db_path)

    config.db_file_path = db_path
    return db_path


def seed_demo_messages() -> None:
    schema = """
        user_id TEXT,
        message_text TEXT,
        timestamp INTEGER,
        ack_type TEXT
    """

    with sqlite3.connect(config.db_file_path, timeout=10.0) as db_connection:
        db_connection.execute("PRAGMA busy_timeout=10000")
        cursor = db_connection.cursor()

        for channel_name, rows in _demo_messages().items():
            table_name = get_table_name(channel_name)
            cursor.execute(f"CREATE TABLE IF NOT EXISTS {table_name} ({schema})")
            cursor.executemany(
                f"""
                INSERT INTO {table_name} (user_id, message_text, timestamp, ack_type)
                VALUES (?, ?, ?, ?)
                """,
                rows,
            )

        db_connection.commit()


def _build_node(
    node_num: int,
    long_name: str,
    short_name: str,
    *,
    hops: int,
    last_heard_offset: int,
    snr: float = 0.0,
    battery: int = 0,
    voltage: float = 0.0,
    favorite: bool = False,
    ignored: bool = False,
) -> Dict[str, object]:
    node = {
        "num": node_num,
        "user": {
            "longName": long_name,
            "shortName": short_name,
            "hwModel": "TBEAM",
            "role": "CLIENT",
            "publicKey": f"pk-{node_num:08x}",
            "isLicensed": True,
        },
        "lastHeard": DEMO_BASE_TIMESTAMP + 3600 - last_heard_offset,
        "hopsAway": hops,
        "isFavorite": favorite,
        "isIgnored": ignored,
    }

    if snr:
        node["snr"] = snr
    if battery:
        node["deviceMetrics"] = {
            "batteryLevel": battery,
            "voltage": voltage or 4.0,
            "uptimeSeconds": 86400 + node_num % 10000,
            "channelUtilization": 12.5 + (node_num % 7),
            "airUtilTx": 4.5 + (node_num % 5),
        }

    if node_num % 3 == 0:
        node["position"] = {
            "latitude": 45.5231 + ((node_num % 50) * 0.0001),
            "longitude": -122.6765 - ((node_num % 50) * 0.0001),
            "altitude": 85 + (node_num % 20),
        }

    return node


def _demo_messages() -> Dict[Union[str, int], List[Tuple[str, str, int, Union[str, None]]]]:
    return {
        "MediumFast": [
            (str(DEMO_LOCAL_NODE_NUM), "Help, I'm stuck in a ditch!", DEMO_BASE_TIMESTAMP + 45, "Ack"),
            ("2701131778", "Do you require a alpinist?", DEMO_BASE_TIMESTAMP + 80, None),
            (str(DEMO_LOCAL_NODE_NUM), "I don't know what that is.", DEMO_BASE_TIMESTAMP + 104, "Implicit"),
        ],
        "Another Channel": [
            ("2701131788", "Weather is holding for the summit push.", DEMO_BASE_TIMESTAMP + 220, None),
            (str(DEMO_LOCAL_NODE_NUM), "Copy that. Keep me posted.", DEMO_BASE_TIMESTAMP + 260, "Ack"),
        ],
        2701131788: [
            ("2701131788", "Ping me when you are back at the trailhead.", DEMO_BASE_TIMESTAMP + 330, None),
            (str(DEMO_LOCAL_NODE_NUM), "Will do.", DEMO_BASE_TIMESTAMP + 350, "Ack"),
        ],
    }
