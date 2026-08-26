from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from flask import current_app


DEFAULT_TIMEZONE = "America/Bogota"


def validate_timezone_name(value):
    """Validate and return an IANA timezone configured for the application."""
    name = str(value or "").strip()
    if not name:
        raise ValueError("TIMEZONE no puede estar vacia.")
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError as error:
        raise ValueError(
            "TIMEZONE '%s' no es una zona horaria IANA valida." % name
        ) from error


def app_timezone():
    """Return the timezone selected for the current Flask application."""
    return validate_timezone_name(
        current_app.config.get("TIMEZONE", DEFAULT_TIMEZONE)
    )


def utc_now():
    """Return current UTC as a naive datetime for existing DateTime columns."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def local_today():
    """Return the current calendar date in the configured application timezone."""
    return datetime.now(app_timezone()).date()


def utc_to_local(value):
    """Convert a stored UTC datetime (naive or aware) to configured local time."""
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    return value.astimezone(app_timezone())


def format_local_datetime(value, date_format="%Y-%m-%d %H:%M:%S"):
    """Format a stored UTC datetime in the configured application timezone."""
    local_value = utc_to_local(value)
    return "" if local_value is None else local_value.strftime(date_format)


def local_to_utc(value):
    """Convert a configured local datetime to naive UTC for database storage."""
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=app_timezone())
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def local_date_to_utc_range(value):
    """Return the inclusive/exclusive UTC bounds for one configured local day."""
    if value is None:
        return None, None
    timezone_local = app_timezone()
    start_local = datetime.combine(value, time.min).replace(tzinfo=timezone_local)
    end_local = datetime.combine(
        value + timedelta(days=1), time.min
    ).replace(tzinfo=timezone_local)
    return (
        start_local.astimezone(timezone.utc).replace(tzinfo=None),
        end_local.astimezone(timezone.utc).replace(tzinfo=None),
    )
