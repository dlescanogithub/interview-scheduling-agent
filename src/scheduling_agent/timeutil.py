"""Time parsing, canonical instants, and zone display."""

from __future__ import annotations

from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

WEEKDAYS_ES = (
    "lunes",
    "martes",
    "miércoles",
    "jueves",
    "viernes",
    "sábado",
    "domingo",
)
WEEKDAYS_EN = (
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
)
MONTHS_ES = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "setiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}


def parse_iso(value: str) -> datetime:
    """Parse an aware ISO-8601 instant and return it in UTC.

    Naive datetimes are rejected. They are not treated as UTC and not treated
    as America/Argentina/Buenos_Aires. A model-facing caller must catch this
    and answer with an offset, for example 2026-10-20T10:00:00-03:00.
    """
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    parsed = datetime.fromisoformat(raw)
    if parsed.tzinfo is None:
        raise ValueError(f"naive datetime: {value}")
    return parsed.astimezone(UTC)


def format_zoned(value: datetime, zone: str) -> str:
    """Local ISO-8601 with a numeric offset, such as 2026-04-13T09:00:00-03:00."""
    if value.tzinfo is None:
        raise ValueError("naive datetime")
    local = value.astimezone(ZoneInfo(zone))
    raw = local.strftime("%z")
    if len(raw) == 5:
        raw = f"{raw[:3]}:{raw[3:]}"
    return local.strftime("%Y-%m-%dT%H:%M:%S") + raw


def to_canonical(value: datetime) -> str:
    """Format an aware instant as UTC `YYYY-MM-DDTHH:MM:SSZ`."""
    if value.tzinfo is None:
        raise ValueError("naive datetime")
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def isoformat_utc(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("naive datetime")
    return value.astimezone(UTC).isoformat()


def parse_hhmm(value: str) -> time:
    hour, minute = value.split(":")
    return time(int(hour), int(minute))


def weekday_name(value: datetime, lang: str, zone: str) -> str:
    local = value.astimezone(ZoneInfo(zone))
    names = WEEKDAYS_ES if lang == "es" else WEEKDAYS_EN
    return names[local.weekday()]


def format_local(value: datetime, zone: str) -> tuple[str, str, str]:
    """Return `(date, start_hhmm, weekday index as str)` in `zone`."""
    local = value.astimezone(ZoneInfo(zone))
    return local.strftime("%Y-%m-%d"), local.strftime("%H:%M"), str(local.weekday())


def combine_local(date_text: str, hhmm: str, zone: str) -> datetime:
    """Build a UTC instant from a local date and HH:MM."""
    hour, minute = hhmm.split(":")
    local = datetime(
        int(date_text[0:4]),
        int(date_text[5:7]),
        int(date_text[8:10]),
        int(hour),
        int(minute),
        tzinfo=ZoneInfo(zone),
    )
    return local.astimezone(UTC)


def overlaps(
    start_a: datetime, end_a: datetime, start_b: datetime, end_b: datetime
) -> bool:
    """Half-open overlap: [start, end)."""
    return start_a < end_b and start_b < end_a


def expand(
    start: datetime, end: datetime, buffer_minutes: int
) -> tuple[datetime, datetime]:
    delta = timedelta(minutes=buffer_minutes)
    return start - delta, end + delta
