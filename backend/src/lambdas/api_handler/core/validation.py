"""Input validation shared by handlers (port of PersonalDataValidator and OccupancyHelper)."""

from __future__ import annotations

import re
import unicodedata
from decimal import Decimal, InvalidOperation
from typing import Any

from core.errors import BadRequest

_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@.]+(?:\.[^\s@.]+)+$")


def validate_name(name: Any, field: str) -> str:
    if isinstance(name, str):
        name = unicodedata.normalize("NFC", " ".join(name.split()))
    if not isinstance(name, str) or not name.strip() or not 2 <= len(name) <= 50:
        raise BadRequest(f"{field} must be between 2 and 50 characters long.")
    if not any(ch.isalpha() for ch in name) or any(
        not (unicodedata.category(ch)[0] in {"L", "M"} or ch in " -'’") for ch in name
    ):
        raise BadRequest(f"{field} can only contain letters, spaces, hyphens, and apostrophes.")
    return name


def validate_email(email: Any) -> str:
    if not isinstance(email, str) or not email.strip() or len(email) > 254:
        raise BadRequest("Email must be a valid email address and cannot exceed 254 characters.")
    if not _EMAIL_RE.match(email):
        raise BadRequest("Invalid email address. Please ensure it follows the format: username@domain.com")
    return email


def validate_passwords(password: Any, confirm_password: Any) -> None:
    if not isinstance(password, str) or not password.strip() or not 8 <= len(password) <= 16:
        raise BadRequest("Password must be between 8 and 16 characters long.")
    if password != confirm_password:
        raise BadRequest("Passwords do not match.")
    if not (
        any(ch.isupper() for ch in password)
        and any(ch.islower() for ch in password)
        and any(ch.isdigit() for ch in password)
        and any(not ch.isalnum() and not ch.isspace() for ch in password)
    ):
        raise BadRequest("Password must include uppercase and lowercase letters, a number, and a special character.")


def validate_password(password: Any) -> str:
    if not isinstance(password, str) or not password.strip():
        raise BadRequest("Password is required. Please enter your password to continue.")
    return password


def parse_occupancy(value: Any) -> str:
    """Strict ``0``–``100`` (optionally with ``%``) → ``"65%"``; anything else is rejected."""
    text = str(value).strip() if value is not None else ""
    digits = text[:-1] if text.endswith("%") else text
    if digits.isdigit() and 0 <= int(digits) <= 100:
        return f"{int(digits)}%"
    raise BadRequest(
        f"Invalid Average Occupancy '{value}'. Must be a numeric value between 0 and 100 (e.g., '65' or '65%')."
    )


def sanitize_occupancy(value: Any) -> str:
    """Lenient normalisation for values already stored (legacy ``high``/``medium``/``low`` included)."""
    text = str(value or "").strip()
    digits = "".join(ch for ch in text if ch.isdigit())
    if digits:
        return f"{max(0, min(100, int(digits)))}%"
    return {"high": "75%", "medium": "50%", "low": "25%"}.get(text.lower(), "0%")


def required_str(body: dict[str, Any], key: str, message: str | None = None) -> str:
    value = body.get(key)
    if not isinstance(value, str) or not value.strip():
        raise BadRequest(message or f"'{key}' is required.")
    return value.strip()


def optional_str(body: dict[str, Any], key: str) -> str | None:
    value = body.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise BadRequest(f"'{key}' must be a string.")
    return value.strip() or None


def catalog_translations(value: Any, *, fields: tuple[str, ...]) -> dict[str, dict[str, str]]:
    """Optional catalog copy; an explicit empty object clears translations on update."""
    if not isinstance(value, dict):
        raise BadRequest("'translations' must be an object.")
    result: dict[str, dict[str, str]] = {}
    for locale, content in value.items():
        if locale not in {"en", "uk", "fr", "es", "de"}:
            raise BadRequest("Translation language must be one of: en, uk, fr, es, de.")
        if not isinstance(content, dict) or any(field not in fields for field in content):
            raise BadRequest(f"Translation '{locale}' must contain only: {', '.join(fields)}.")
        translated = {}
        for field, text in content.items():
            limit = 200 if field == "name" else 2000
            if not isinstance(text, str) or len(text) > limit:
                raise BadRequest(f"Translation '{locale}.{field}' must be a string up to {limit} characters.")
            if text.strip():
                translated[field] = text.strip()
        if translated:
            result[locale] = translated
    return result


def as_int(value: Any, field: str, default: int | None = None) -> int:
    if value is None or value == "":
        if default is not None:
            return default
        raise BadRequest(f"'{field}' is required.")
    if isinstance(value, bool):
        raise BadRequest(f"'{field}' must be a whole number.")
    try:
        number = Decimal(str(value))
    except InvalidOperation as exc:
        raise BadRequest(f"'{field}' must be a whole number.") from exc
    if not number.is_finite() or number != number.to_integral_value():
        raise BadRequest(f"'{field}' must be a whole number.")
    return int(number)


def as_decimal(value: Any, field: str) -> Decimal:
    if isinstance(value, bool) or value is None or value == "":
        raise BadRequest(f"'{field}' must be a number.")
    try:
        number = Decimal(str(value))
        if not number.is_finite():
            raise BadRequest(f"'{field}' must be a finite number.")
        return number
    except InvalidOperation as exc:
        raise BadRequest(f"'{field}' must be a number.") from exc


def as_bool(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes"}
