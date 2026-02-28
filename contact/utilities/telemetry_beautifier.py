import datetime

sensors = {
    'temperature': {'icon':'🌡️  ','unit':'°'},
    'relative_humidity': {'icon':'💧','unit':'%'},
    'barometric_pressure': {'icon':'⮇ ','unit': 'hPa'},
    'lux': {'icon':'🔦 ','unit': 'lx'},
    'uv_lux': {'icon':'uv🔦 ','unit': 'lx'},
    'wind_speed': {'icon':'💨 ','unit': 'm/s'},
    'wind_direction': {'icon':'⮆ ','unit': ''},
    'battery_level': {'icon':'🔋 ', 'unit':'%'},
    'voltage': {'icon':'', 'unit':'V'},
    'channel_utilization': {'icon':'ChUtil:', 'unit':'%'},
    'air_util_tx': {'icon':'AirUtil:', 'unit':'%'},
    'uptime_seconds': {'icon':'🆙 ', 'unit':'h'},
    'latitude_i': {'icon':'🌍 ', 'unit':''},
    'longitude_i': {'icon':'', 'unit':''},
    'altitude': {'icon':'⬆️  ', 'unit':'m'},
    'time': {'icon':'🕔 ', 'unit':''}
}

def humanize_wind_direction(degrees):
    """ Convert degrees to Eest-West-Nnoth-Ssouth directions """
    if not 0 <= degrees <= 360:
        return None

    directions = [
        ("N", 337.5, 22.5),
        ("NE", 22.5, 67.5),
        ("E", 67.5, 112.5),
        ("SE", 112.5, 157.5),
        ("S", 157.5, 202.5),
        ("SW", 202.5, 247.5),
        ("W", 247.5, 292.5),
        ("NW", 292.5, 337.5),
    ]

    if degrees >= directions[0][1] or degrees < directions[0][2]:
        return directions[0][0]

    # Check for all other directions
    for direction, lower_bound, upper_bound in directions[1:]:
        if lower_bound <= degrees < upper_bound:
            return direction

    # This part should ideally not be reached with valid input
    return None

def get_chunks(data):
    """ Breakdown telemetry data and assign emojis for more visual appeal of the payloads """
    reading = data.split('\n')

    # remove empty list lefover from the split
    reading = list(filter(None, reading))
    parsed=""

    for item in reading:
        key, value = item.split(":")

        # If value is float, round it to the 1 digit after point
        # else make it int
        if "." in value:
            value = round(float(value.strip()),1)
        else:
            try:
                value = int(value.strip())
            except Exception:
                # Leave it string as last resort
                value = value

        # Python 3.9-compatible alternative to match/case.
        if key == "uptime_seconds":
            # convert seconds to hours, for our sanity
            value = round(value / 60 / 60, 1)
        elif key in ("longitude_i", "latitude_i"):
            # Convert position to degrees (humanize), as per Meshtastic protobuf comment for this telemetry
            # truncate to 6th digit after floating point, which would be still accurate
            value = round(value * 1e-7, 6)
        elif key == "wind_direction":
            # Convert wind direction from degrees to abbreviation
            value = humanize_wind_direction(value)
        elif key == "time":
            value = datetime.datetime.fromtimestamp(int(value)).strftime("%d.%m.%Y %H:%m")

        if key in sensors:
            parsed+= f"{sensors[key.strip()]['icon']}{value}{sensors[key]['unit']}  "
        else:
            # just pass through if we haven't added the particular telemetry key:value to the sensor dict
            parsed+=f"{key}:{value}  "
    return parsed
