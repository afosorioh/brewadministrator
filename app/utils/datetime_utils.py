from datetime import datetime, timezone
from zoneinfo import ZoneInfo

BOGOTA_TZ = ZoneInfo("America/Bogota")

def now_bogota():
    return datetime.now(BOGOTA_TZ).replace(tzinfo=None)

def today_bogota():
    return datetime.now(BOGOTA_TZ).date()


def utc_to_bogota(value):
    """Convert a stored UTC datetime (naive or aware) to Bogota local time."""
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(BOGOTA_TZ).replace(tzinfo=None)
