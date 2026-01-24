from typing import List
import re


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
