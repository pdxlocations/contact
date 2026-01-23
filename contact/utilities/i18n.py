from typing import Optional

import contact.ui.default_config as config
from contact.utilities.control_utils import parse_ini_file

_translations = {}
_language = None


def _load_translations() -> None:
    global _translations, _language
    language = config.language
    if _translations and _language == language:
        return

    translation_file = config.get_localisation_file(language)
    _translations, _ = parse_ini_file(translation_file)
    _language = language


def t(key: str, default: Optional[str] = None, **kwargs: object) -> str:
    _load_translations()
    text = _translations.get(key, default if default is not None else key)
    try:
        return text.format(**kwargs)
    except Exception:
        return text


def t_text(text: str, **kwargs: object) -> str:
    return t(text, default=text, **kwargs)
