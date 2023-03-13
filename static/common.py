import random

SECS_IN_MINUTE = 60
MINUTE_IN_HOUR = 60
SECS_IN_HOUR = MINUTE_IN_HOUR * SECS_IN_MINUTE

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