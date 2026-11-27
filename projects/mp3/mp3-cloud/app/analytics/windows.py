"""UTC half-open, whole-hour windows shared by refresh and read routes."""

from datetime import UTC, datetime, timedelta

HOUR = timedelta(hours=1)


def closed_hour(now: datetime) -> datetime:
    return utc(now).replace(minute=0, second=0, microsecond=0)


def utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Timezone-aware dates are required")
    return value.astimezone(UTC)


def validate_window(start: datetime, end: datetime, now: datetime, max_hours: int = 744):
    start, end = utc(start), utc(end)
    if start != closed_hour(start) or end != closed_hour(end):
        raise ValueError("from and to must align to whole UTC hours")
    if start >= end:
        raise ValueError("to must be after from")
    if end > closed_hour(now):
        raise ValueError("Only completed hours can be queried or refreshed")
    if end - start > HOUR * max_hours:
        raise ValueError(f"Window must not exceed {max_hours} hours")
    return start, end
