from datetime import datetime, time
from zoneinfo import ZoneInfo
from dateutil import parser

def now_tz(tz_str: str) -> datetime:
    return datetime.now(ZoneInfo(tz_str))

def parse_dt(iso_str: str):
    try:
        return parser.isoparse(iso_str)
    except Exception:
        return None

def in_quiet_hours(now: datetime, quiet_hours: tuple[int,int]) -> bool:
    start, end = quiet_hours
    return time(start,0) <= now.time() < time(end,0)

def time_in_range(now: datetime, start_hour: int, end_hour: int) -> bool:
    return time(start_hour,0) <= now.time() <= time(end_hour,0)

def short_id5() -> str:
    import random
    return f"{random.randint(10000,99999)}"
