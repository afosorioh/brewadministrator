from datetime import datetime
from zoneinfo import ZoneInfo

BOGOTA_TZ = ZoneInfo("America/Bogota")

def now_bogota():
    return datetime.now(BOGOTA_TZ).replace(tzinfo=None)

def today_bogota():
    return datetime.now(BOGOTA_TZ).date()