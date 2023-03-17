import random
import datetime
from pytz import timezone

utc = timezone('UTC')
tz_str = 'America/New_York'
ny_tz = timezone(tz_str)

SECS_IN_MINUTE = 60
MINUTE_IN_HOUR = 60
SECS_IN_HOUR = MINUTE_IN_HOUR * SECS_IN_MINUTE

def get_current_datetime() -> datetime.datetime:
    now = utc.localize(datetime.datetime.utcnow().replace(microsecond=0))
    return now.astimezone(ny_tz)
    
def get_current_timestamp() -> int:
    return int(get_current_datetime().timestamp())

def get_current_iso() -> str:
    return get_current_datetime().isoformat()

def get_timezone_str() -> str:
    return get_current_datetime().strftime('%Z')

def datetime_from_timestamp(timestamp:int) -> datetime.datetime:
    return datetime.datetime.fromtimestamp(timestamp, ny_tz)
    
def datetime_from_iso(isostring:str) -> datetime.datetime:
    return datetime.datetime.fromisoformat(isostring)
    
def datetime_combine(date, time) -> datetime.datetime:
    return datetime.datetime.combine(date, time, ny_tz)
    
def time_from_iso(isotimestring:str) -> datetime.time:
    return datetime.time.fromisoformat(isotimestring).replace(tzinfo=ny_tz)

def get_hours_from_secs(timestamp_delta: int) -> float:
    res = round(timestamp_delta/SECS_IN_HOUR, 2)
    return res if res > 0 else 0.00
    
def scram(w:str) -> str:
    st = w[0]
    en = w[len(w)-1]
    w = w[1:len(w)-1]
    e = ''
    while w:
        pos = random.randrange(len(w))
        e += w[pos]
        w = w[:pos] + w[(pos+1):]
    return st + e + en