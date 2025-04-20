import sqlite3
import time
import logging
from datetime import datetime
from typing import Optional, Union, Dict

from contact.utilities.utils import decimal_to_hex
import contact.ui.default_config as config


from contact.utilities.singleton import ui_state, interface_state


def get_table_name(channel: str) -> str:
    # Construct the table name
    table_name = f"{str(interface_state.myNodeNum)}_{channel}_messages"
    quoted_table_name = f'"{table_name}"'  # Quote the table name becuase we begin with numerics and contain spaces
    return quoted_table_name


def save_message_to_db(channel: str, user_id: str, message_text: str) -> Optional[int]:
    """Save messages to the database, ensuring the table exists."""
    try:
        quoted_table_name = get_table_name(channel)

        schema = """
            user_id TEXT,
            message_text TEXT,
            timestamp INTEGER,
            ack_type TEXT
        """
        ensure_table_exists(quoted_table_name, schema)

        with sqlite3.connect(config.db_file_path) as db_connection:
            db_cursor = db_connection.cursor()
            timestamp = int(time.time())

            # Insert the message
            insert_query = f"""
                INSERT INTO {quoted_table_name} (user_id, message_text, timestamp, ack_type)
                VALUES (?, ?, ?, ?)
            """
            db_cursor.execute(insert_query, (user_id, message_text, timestamp, None))
            db_connection.commit()

            return timestamp

    except sqlite3.Error as e:
        logging.error(f"SQLite error in save_message_to_db: {e}")
    except Exception as e:
        logging.error(f"Unexpected error in save_message_to_db: {e}")


def update_ack_nak(channel: str, timestamp: int, message: str, ack: str) -> None:
    try:
        with sqlite3.connect(config.db_file_path) as db_connection:
            db_cursor = db_connection.cursor()
            update_query = f"""
                UPDATE {get_table_name(channel)}
                SET ack_type = ?
                WHERE user_id = ? AND
                      timestamp = ? AND
                      message_text = ?
            """

            db_cursor.execute(update_query, (ack, str(interface_state.myNodeNum), timestamp, message))
            db_connection.commit()

    except sqlite3.Error as e:
        logging.error(f"SQLite error in update_ack_nak: {e}")

    except Exception as e:
        logging.error(f"Unexpected error in update_ack_nak: {e}")


def load_messages_from_db() -> None:
    """Load messages from the database for all channels and update ui_state.all_messages and ui_state.channel_list."""
    try:
        with sqlite3.connect(config.db_file_path) as db_connection:
            db_cursor = db_connection.cursor()

            query = "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE ?"
            db_cursor.execute(query, (f"{str(interface_state.myNodeNum)}_%_messages",))
            tables = [row[0] for row in db_cursor.fetchall()]

            # Iterate through each table and fetch its messages
            for table_name in tables:
                quoted_table_name = (
                    f'"{table_name}"'  # Quote the table name because we begin with numerics and contain spaces
                )
                table_columns = [i[1] for i in db_cursor.execute(f"PRAGMA table_info({quoted_table_name})")]
                if "ack_type" not in table_columns:
                    update_table_query = f"ALTER TABLE {quoted_table_name} ADD COLUMN ack_type TEXT"
                    db_cursor.execute(update_table_query)

                query = f"SELECT user_id, message_text, timestamp, ack_type FROM {quoted_table_name}"

                try:
                    # Fetch all messages from the table
                    db_cursor.execute(query)
                    db_messages = [(row[0], row[1], row[2], row[3]) for row in db_cursor.fetchall()]  # Save as tuples

                    # Extract the channel name from the table name
                    channel = table_name.split("_")[1]

                    # Convert the channel to an integer if it's numeric, otherwise keep it as a string (nodenum vs channel name)
                    channel = int(channel) if channel.isdigit() else channel

                    # Add the channel to ui_state.channel_list if not already present
                    if channel not in ui_state.channel_list and not is_chat_archived(channel):
                        ui_state.channel_list.append(channel)

                    # Ensure the channel exists in ui_state.all_messages
                    if channel not in ui_state.all_messages:
                        ui_state.all_messages[channel] = []

                    # Add messages to ui_state.all_messages grouped by hourly timestamp
                    hourly_messages = {}
                    for user_id, message, timestamp, ack_type in db_messages:
                        hour = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:00")
                        if hour not in hourly_messages:
                            hourly_messages[hour] = []

                        ack_str = config.ack_unknown_str
                        if ack_type == "Implicit":
                            ack_str = config.ack_implicit_str
                        elif ack_type == "Ack":
                            ack_str = config.ack_str
                        elif ack_type == "Nak":
                            ack_str = config.nak_str

                        if user_id == str(interface_state.myNodeNum):
                            formatted_message = (f"{config.sent_message_prefix}{ack_str}: ", message)
                        else:
                            formatted_message = (
                                f"{config.message_prefix} {get_name_from_database(int(user_id), 'short')}: ",
                                message,
                            )

                        hourly_messages[hour].append(formatted_message)

                    # Flatten the hourly messages into ui_state.all_messages[channel]
                    for hour, messages in sorted(hourly_messages.items()):
                        ui_state.all_messages[channel].append((f"-- {hour} --", ""))
                        ui_state.all_messages[channel].extend(messages)

                except sqlite3.Error as e:
                    logging.error(f"SQLite error while loading messages from table '{table_name}': {e}")

    except sqlite3.Error as e:
        logging.error(f"SQLite error in load_messages_from_db: {e}")


def init_nodedb() -> None:
    """Initialize the node database and update it with nodes from the interface."""

    try:
        if not interface_state.interface.nodes:
            return  # No nodes to initialize

        ensure_node_table_exists()  # Ensure the table exists before insertion
        nodes_snapshot = list(interface_state.interface.nodes.values())

        # Insert or update all nodes
        for node in nodes_snapshot:
            update_node_info_in_db(
                user_id=node["num"],
                long_name=node["user"].get("longName", ""),
                short_name=node["user"].get("shortName", ""),
                hw_model=node["user"].get("hwModel", ""),
                is_licensed=node["user"].get("isLicensed", "0"),
                role=node["user"].get("role", "CLIENT"),
                public_key=node["user"].get("publicKey", ""),
            )

        logging.info("Node database initialized successfully.")

    except sqlite3.Error as e:
        logging.error(f"SQLite error in init_nodedb: {e}")
    except Exception as e:
        logging.error(f"Unexpected error in init_nodedb: {e}")


def maybe_store_nodeinfo_in_db(packet: Dict[str, object]) -> None:
    """Save nodeinfo unless that record is already there, updating if necessary."""
    try:
        user_id = packet["from"]
        long_name = packet["decoded"]["user"]["longName"]
        short_name = packet["decoded"]["user"]["shortName"]
        hw_model = packet["decoded"]["user"]["hwModel"]
        is_licensed = packet["decoded"]["user"].get("isLicensed", "0")
        role = packet["decoded"]["user"].get("role", "CLIENT")
        public_key = packet["decoded"]["user"].get("publicKey", "")

        update_node_info_in_db(user_id, long_name, short_name, hw_model, is_licensed, role, public_key)

    except sqlite3.Error as e:
        logging.error(f"SQLite error in maybe_store_nodeinfo_in_db: {e}")
    except Exception as e:
        logging.error(f"Unexpected error in maybe_store_nodeinfo_in_db: {e}")


def update_node_info_in_db(
    user_id: Union[int, str],
    long_name: Optional[str] = None,
    short_name: Optional[str] = None,
    hw_model: Optional[str] = None,
    is_licensed: Optional[Union[str, int]] = None,
    role: Optional[str] = None,
    public_key: Optional[str] = None,
    chat_archived: Optional[int] = None,
) -> None:
    """Update or insert node information into the database, preserving unchanged fields."""
    try:
        ensure_node_table_exists()  # Ensure the table exists before any operation

        with sqlite3.connect(config.db_file_path) as db_connection:
            db_cursor = db_connection.cursor()
            table_name = f'"{interface_state.myNodeNum}_nodedb"'  # Quote in case of numeric names

            table_columns = [i[1] for i in db_cursor.execute(f"PRAGMA table_info({table_name})")]
            if "chat_archived" not in table_columns:
                update_table_query = f"ALTER TABLE {table_name} ADD COLUMN chat_archived INTEGER"
                db_cursor.execute(update_table_query)

            # Fetch existing values to preserve unchanged fields
            db_cursor.execute(f"SELECT * FROM {table_name} WHERE user_id = ?", (user_id,))
            existing_record = db_cursor.fetchone()

            if existing_record:
                (
                    existing_long_name,
                    existing_short_name,
                    existing_hw_model,
                    existing_is_licensed,
                    existing_role,
                    existing_public_key,
                    existing_chat_archived,
                ) = existing_record[1:]

                long_name = long_name if long_name is not None else existing_long_name
                short_name = short_name if short_name is not None else existing_short_name
                hw_model = hw_model if hw_model is not None else existing_hw_model
                is_licensed = is_licensed if is_licensed is not None else existing_is_licensed
                role = role if role is not None else existing_role
                public_key = public_key if public_key is not None else existing_public_key
                chat_archived = chat_archived if chat_archived is not None else existing_chat_archived

            long_name = long_name if long_name is not None else "Meshtastic " + str(decimal_to_hex(user_id)[-4:])
            short_name = short_name if short_name is not None else str(decimal_to_hex(user_id)[-4:])
            hw_model = hw_model if hw_model is not None else "UNSET"
            is_licensed = is_licensed if is_licensed is not None else 0
            role = role if role is not None else "CLIENT"
            public_key = public_key if public_key is not None else ""
            chat_archived = chat_archived if chat_archived is not None else 0

            # Upsert logic
            upsert_query = f"""
                INSERT INTO {table_name} (user_id, long_name, short_name, hw_model, is_licensed, role, public_key, chat_archived)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    long_name = excluded.long_name,
                    short_name = excluded.short_name,
                    hw_model = excluded.hw_model,
                    is_licensed = excluded.is_licensed,
                    role = excluded.role,
                    public_key = excluded.public_key,
                    chat_archived = excluded.chat_archived
            """
            db_cursor.execute(
                upsert_query, (user_id, long_name, short_name, hw_model, is_licensed, role, public_key, chat_archived)
            )
            db_connection.commit()

    except sqlite3.Error as e:
        logging.error(f"SQLite error in update_node_info_in_db: {e}")
    except Exception as e:
        logging.error(f"Unexpected error in update_node_info_in_db: {e}")


def ensure_node_table_exists() -> None:
    """Ensure the node database table exists."""
    table_name = f'"{interface_state.myNodeNum}_nodedb"'  # Quote for safety
    schema = """
        user_id TEXT PRIMARY KEY,
        long_name TEXT,
        short_name TEXT,
        hw_model TEXT,
        is_licensed TEXT,
        role TEXT,
        public_key TEXT,
        chat_archived INTEGER
    """
    ensure_table_exists(table_name, schema)


def ensure_table_exists(table_name: str, schema: str) -> None:
    """Ensure the given table exists in the database."""
    try:
        with sqlite3.connect(config.db_file_path) as db_connection:
            db_cursor = db_connection.cursor()
            create_table_query = f"CREATE TABLE IF NOT EXISTS {table_name} ({schema})"
            db_cursor.execute(create_table_query)
            db_connection.commit()
    except sqlite3.Error as e:
        logging.error(f"SQLite error in ensure_table_exists({table_name}): {e}")
    except Exception as e:
        logging.error(f"Unexpected error in ensure_table_exists({table_name}): {e}")


def get_name_from_database(user_id: int, type: str = "long") -> str:
    """
    Retrieve a user's name (long or short) from the node database.

    :param user_id: The user ID to look up.
    :param type: "long" for long name, "short" for short name.
    :return: The retrieved name or the hex of the user id
    """
    try:
        with sqlite3.connect(config.db_file_path) as db_connection:
            db_cursor = db_connection.cursor()

            # Construct table name
            table_name = f"{str(interface_state.myNodeNum)}_nodedb"
            nodeinfo_table = f'"{table_name}"'  # Quote table name for safety

            # Determine the correct column to fetch
            column_name = "long_name" if type == "long" else "short_name"

            # Query the database
            query = f"SELECT {column_name} FROM {nodeinfo_table} WHERE user_id = ?"
            db_cursor.execute(query, (user_id,))
            result = db_cursor.fetchone()

            return result[0] if result else decimal_to_hex(user_id)

    except sqlite3.Error as e:
        logging.error(f"SQLite error in get_name_from_database: {e}")
        return "Unknown"

    except Exception as e:
        logging.error(f"Unexpected error in get_name_from_database: {e}")
        return "Unknown"


def is_chat_archived(user_id: int) -> int:
    try:
        with sqlite3.connect(config.db_file_path) as db_connection:
            db_cursor = db_connection.cursor()
            table_name = f"{str(interface_state.myNodeNum)}_nodedb"
            nodeinfo_table = f'"{table_name}"'
            query = f"SELECT chat_archived FROM {nodeinfo_table} WHERE user_id = ?"
            db_cursor.execute(query, (user_id,))
            result = db_cursor.fetchone()

            return result[0] if result else 0

    except sqlite3.Error as e:
        logging.error(f"SQLite error in is_chat_archived: {e}")
        return "Unknown"

    except Exception as e:
        logging.error(f"Unexpected error in is_chat_archived: {e}")
        return "Unknown"
