validation_rules = {
    "shortName": {"max_length": 4},
    "longName": {"max_length": 32},
    "fixed_pin": {"min_length": 6, "max_length": 6},
    "position_flags": {"max_length": 3},
    "enabled_protocols": {"max_value": 2},
    "hop_limit": {"max_value": 7},
}


def get_validation_for(key: str) -> dict:
    for rule_key, config in validation_rules.items():
        if rule_key in key:
            return config
    return {}
