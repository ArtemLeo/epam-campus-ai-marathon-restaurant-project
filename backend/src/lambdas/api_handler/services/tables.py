"""Tables, their availability and bookable time slots.

Working hours are 10:00–22:00 UTC; a booking lasts 90 minutes with a 15 minute gap between bookings.
"""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

from core import config, dynamo, timeutils
from core.enums import ReservationStatus
from core.errors import BadRequest, Conflict, NotFound
from core.validation import as_int
from repositories import bookings, catalog
from services import mappers

Item = dict[str, Any]

OPENING_HOUR = 10
CLOSING_HOUR = 22
SLOT = dt.timedelta(minutes=90)
GAP = dt.timedelta(minutes=15)


def _working_day(day: dt.datetime) -> tuple[dt.datetime, dt.datetime]:
    local = day.astimezone(config.restaurant_timezone())
    start = local.replace(hour=OPENING_HOUR, minute=0, second=0, microsecond=0)
    end = local.replace(hour=CLOSING_HOUR, minute=0, second=0, microsecond=0)
    return start.astimezone(timeutils.UTC), end.astimezone(timeutils.UTC)


def validate_window(start: dt.datetime, end: dt.datetime) -> None:
    opening, closing = _working_day(start)
    if start < opening or end > closing:
        raise BadRequest(f"Reservations must be within 10:00–22:00 ({config.restaurant_timezone().key}).")
    if end - start != SLOT:
        raise BadRequest("A reservation lasts 90 minutes.")


def _bounds(reservation: Item) -> tuple[dt.datetime, dt.datetime]:
    return timeutils.parse_datetime(reservation["startTime"]), timeutils.parse_datetime(reservation["endTime"])


def _active_reservations(table_id: str) -> list[Item]:
    return [
        r
        for r in bookings.current_reservations_by_table(table_id)
        if mappers.reservation_status(r) in (ReservationStatus.Reserved, ReservationStatus.InProgress)
    ]


def time_slots(table_id: str, start_time: Any) -> list[Item]:
    """Bookable windows in the restaurant's day, using exactly the booking buffer rules."""
    require_table(table_id)
    start = timeutils.parse_datetime(start_time, "startTime")
    day_start, day_end = _working_day(start)
    current = max(start, day_start, timeutils.utcnow() + GAP)
    # Offer clean quarter-hour starts, including when searching for a table today.
    remainder = (current - day_start) % GAP
    if remainder:
        current += GAP - remainder
    busy = sorted((_bounds(r) for r in _active_reservations(table_id)), key=lambda b: b[0])
    slots = []
    while current + SLOT <= day_end:
        end = current + SLOT
        overlap = next(((s, e) for s, e in busy if current < e + GAP and s - GAP < end), None)
        if overlap is None:
            slots.append({"start": timeutils.iso(current), "end": timeutils.iso(end)})
            current = end + GAP
        else:
            current = overlap[1] + GAP
    return slots


def available_tables(location_id: str | None, capacity: Any, start_time: Any) -> list[Item]:
    start = timeutils.parse_datetime(start_time, "startTime") if start_time else timeutils.utcnow()
    if start_time and start < timeutils.utcnow():
        raise BadRequest("Cannot query timeslots in the past.")
    minimum = as_int(capacity, "capacity", default=0)
    if minimum < 0:
        raise BadRequest("Capacity cannot be negative.")
    found = catalog.tables_by_location(location_id) if location_id else catalog.all_tables()
    result = [t for t in found if dynamo.number(t.get("capacity")) >= minimum and time_slots(t["id"], start)]
    return [mappers.table_response(t) for t in sorted(result, key=lambda t: dynamo.number(t.get("tableNumber")))]


def location_tables(location_id: str) -> list[Item]:
    tables = catalog.tables_by_location(location_id)
    return [mappers.table_response(t) for t in sorted(tables, key=lambda t: dynamo.number(t.get("tableNumber")))]


def _check_number_free(location_id: str, table_number: int, table_id: str | None = None) -> None:
    for table in catalog.tables_by_location(location_id):
        if table["id"] != table_id and dynamo.number(table.get("tableNumber")) == table_number:
            raise Conflict(f"Table number {table_number} already exists at this location.")


def create_table(body: dict[str, Any]) -> Item:
    location_id = body.get("locationId")
    capacity = as_int(body.get("capacity"), "capacity", default=0)
    table_number = as_int(body.get("tableNumber"), "tableNumber", default=0)
    if not isinstance(location_id, str) or not location_id.strip() or not 1 <= capacity <= 50 or table_number <= 0:
        raise BadRequest("Invalid payload")
    if not catalog.get_location(location_id):
        raise NotFound(f"Location with id '{location_id}' was not found.")
    _check_number_free(location_id, table_number)
    table = {"id": str(uuid.uuid4()), "locationId": location_id, "capacity": capacity, "tableNumber": table_number}
    catalog.save_table(table)
    return mappers.table_response(table)


def require_table(table_id: str) -> Item:
    table = catalog.get_table(table_id)
    if not table:
        raise BadRequest(f"Table '{table_id}' not found.")
    return table


def update_table(table_id: str, body: dict[str, Any]) -> Item:
    table = require_table(table_id)
    lowered = {k.lower(): v for k, v in body.items()}
    capacity = as_int(lowered.get("capacity"), "capacity")
    table_number = as_int(lowered.get("tablenumber"), "tableNumber")
    if not 1 <= capacity <= 50 or table_number <= 0:
        raise BadRequest("Capacity must be 1–50 and table number must be positive.")
    _check_number_free(table["locationId"], table_number, table_id)
    if any(int(r.get("guestCount", 0)) > capacity for r in _active_reservations(table_id)):
        raise Conflict("This capacity is smaller than an existing reservation. Move or cancel that reservation first.")
    table.update(capacity=capacity, tableNumber=table_number)
    catalog.save_table(table)
    return mappers.table_response(table)


def delete_table(table_id: str) -> None:
    table = require_table(table_id)
    now = timeutils.utcnow()
    active = [
        r
        for r in _active_reservations(table_id)
        if mappers.reservation_status(r) == ReservationStatus.InProgress or _bounds(r)[1] > now
    ]
    if active:
        raise BadRequest(f"Cannot delete table '{table_id}' because it has {len(active)} active upcoming reservations.")
    dynamo.transaction([dynamo.delete_action("tables", {"id": table_id}, table)])
