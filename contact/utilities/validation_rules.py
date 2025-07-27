validation_rules = {
    "shortName": {"max_length": 4},
    "longName": {"max_length": 32},
    "fixed_pin": {"min_length": 6, "max_length": 6},
    "position_flags": {"max_length": 3},
    "enabled_protocols": {"max_value": 2},
    "hop_limit": {"max_value": 7},
    "latitude": {"min_value": -90, "max_value": 90},
    "longitude": {"min_value": -180, "max_value": 180},
    "altitude": {"min_value": -4294967295, "max_value": 4294967295},
    "red": {"max_value": 255},
    "green": {"max_value": 255},
    "blue": {"max_value": 255},
    "current": {"max_value": 255},
    "position_precision": {"max_value": 32},
}


def get_validation_for(key: str) -> dict:
    for rule_key, config in validation_rules.items():
        if rule_key in key:
            return config
    return {}
