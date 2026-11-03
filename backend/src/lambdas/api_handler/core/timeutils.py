"""UTC date/time helpers. All timestamps are stored and returned as ISO 8601 strings in UTC."""

from __future__ import annotations

import datetime as dt

from core.errors import BadRequest

UTC = dt.timezone.utc


def utcnow() -> dt.datetime:
    return dt.datetime.now(UTC)


def parse_datetime(value: object, field: str = "date") -> dt.datetime:
    """Parse an ISO 8601 string into an aware UTC datetime (naive values are treated as UTC)."""
    if isinstance(value, dt.datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        text = value.strip()
        if text.endswith(("Z", "z")):
            text = text[:-1] + "+00:00"
        try:
            parsed = dt.datetime.fromisoformat(text)
        except ValueError as exc:
            raise BadRequest(f"Invalid {field} '{value}'. Expected ISO 8601 format.") from exc
    else:
        raise BadRequest(f"Missing or invalid {field}.")
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def parse_date(value: object, field: str = "date") -> dt.date:
    if isinstance(value, str):
        try:
            return dt.date.fromisoformat(value.strip()[:10])
        except ValueError:
            pass
    raise BadRequest(f"Invalid or missing {field}")


def iso(value: dt.datetime) -> str:
    """Fixed-width ISO format (sortable as a string), e.g. ``2026-08-07T19:00:00.000Z``."""
    value = value.astimezone(UTC)
    return value.strftime("%Y-%m-%dT%H:%M:%S.") + f"{value.microsecond // 1000:03d}Z"


def human(value: dt.datetime) -> str:
    """``Aug 07, 2026, 7:00 PM`` — the .NET ``MMM dd, yyyy, h:mm tt`` format used in orders/notifications."""
    return f"{value:%b %d, %Y}, {clock(value)}"


def clock(value: dt.datetime) -> str:
    """``7:00 PM`` — the .NET ``h:mm tt`` format."""
    hour = value.hour % 12 or 12
    return f"{hour}:{value:%M} {'AM' if value.hour < 12 else 'PM'}"
