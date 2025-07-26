validation_rules = {
    "shortName": {"max_length": 4},
    "longName": {"max_length": 32},
    "fixed_pin": {"max_length": 6, "fixed_length": 6},
}


def get_validation_for(key: str) -> dict:
    for rule_key, config in validation_rules.items():
        if rule_key in key:
            return config
    return {}
