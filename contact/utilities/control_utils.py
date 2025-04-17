from typing import Optional, Tuple, Dict, List
import re


def parse_ini_file(ini_file_path: str) -> Tuple[Dict[str, str], Dict[str, str]]:
    """Parses an INI file and returns a mapping of keys to human-readable names and help text."""

    field_mapping: Dict[str, str] = {}
    help_text: Dict[str, str] = {}
    current_section: Optional[str] = None

    with open(ini_file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            # Skip empty lines and comments
            if not line or line.startswith(";") or line.startswith("#"):
                continue

            # Handle sections like [config.device]
            if line.startswith("[") and line.endswith("]"):
                current_section = line[1:-1]
                continue

            # Parse lines like: key, "Human-readable name", "helptext"
            parts = [p.strip().strip('"') for p in line.split(",", 2)]
            if len(parts) >= 2:
                key = parts[0]

                # If key is 'title', map directly to the section
                if key == "title":
                    full_key = current_section
                else:
                    full_key = f"{current_section}.{key}" if current_section else key

                # Use the provided human-readable name or fallback to key
                human_readable_name = parts[1] if parts[1] else key
                field_mapping[full_key] = human_readable_name

                # Handle help text or default
                help = parts[2] if len(parts) == 3 and parts[2] else "No help available."
                help_text[full_key] = help

            else:
                # Handle cases with only the key present
                full_key = f"{current_section}.{key}" if current_section else key
                field_mapping[full_key] = key
                help_text[full_key] = "No help available."

    return field_mapping, help_text


def transform_menu_path(menu_path: List[str]) -> List[str]:
    """Applies path replacements and normalizes entries in the menu path."""
    path_replacements = {"Radio Settings": "config", "Module Settings": "module"}

    transformed_path: List[str] = []
    for part in menu_path[1:]:  # Skip 'Main Menu'
        # Apply fixed replacements
        part = path_replacements.get(part, part)

        # Normalize entries like "Channel 1", "Channel 2", etc.
        if re.match(r"Channel\s+\d+", part, re.IGNORECASE):
            part = "channel"

        transformed_path.append(part)

    return transformed_path
