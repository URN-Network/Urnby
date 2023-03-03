SECS_IN_MINUTE = 60
MINUTE_IN_HOUR = 60
SECS_IN_HOUR = MINUTE_IN_HOUR * SECS_IN_MINUTE

def get_hours_from_secs(timestamp_delta: int) -> float:
    return round(timestamp_delta/SECS_IN_HOUR, 2)