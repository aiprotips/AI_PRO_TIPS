import hashlib, json, pytz, os
from datetime import datetime
from dateutil import parser as duparser

def now_tz(tzname: str):
    tz = pytz.timezone(tzname)
    return datetime.now(tz)

def in_quiet_hours(now, quiet_hours):
    start, end = quiet_hours
    return start <= now.hour < end

def time_in_range(now, hhmm_a: str, hhmm_b: str):
    s = int(hhmm_a[:2])*60 + int(hhmm_a[3:])
    e = int(hhmm_b[:2])*60 + int(hhmm_b[3:])
    m = now.hour*60 + now.minute
    return s <= m <= e

def progress_bar(taken: int, total: int) -> str:
    return "✅"*taken + "⬜"*(total - taken)

def sha256(s: str):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def parse_dt(s: str):
    try:
        return duparser.parse(s)
    except Exception:
        return None

def json_dumps(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(",",":"))
