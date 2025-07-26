class InputType:
    STRING = str
    INTEGER = int
    FLOAT = float


validation_rules = {
    "shortName": {
        "max_length": 4,
        "type": InputType.STRING,
    },
    "longName": {
        "max_length": 32,
        "type": InputType.STRING,
    },
    "fixed_pin": {
        "max_length": 6,
        "fixed_length": 6,
        "type": InputType.INTEGER,
    },
    "adc_multiplier_override": {
        "type": InputType.FLOAT,
    },
}


def get_validation_for(key: str) -> dict:
    for rule_key, config in validation_rules.items():
        if rule_key in key:
            return config
    return {}
