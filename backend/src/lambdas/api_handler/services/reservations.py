"""Table reservations for customers and waiters, including status transitions."""

from __future__ import annotations

import datetime as dt
import logging
import secrets
import uuid
from typing import Any

from core import auth, dynamo, timeutils
from core.auth import Caller
from core.enums import OrderStatus, ReservationStatus, parse_enum
from core.errors import BadRequest, Conflict, Forbidden, NotFound
from core.validation import as_int, optional_str
from repositories import bookings, catalog, people
from services import groups, locations, mappers, reports, tables, waiters

logger = logging.getLogger(__name__)

Item = dict[str, Any]

BOOKING_BUFFER = dt.timedelta(minutes=15)
MIN_LEAD_TIME = dt.timedelta(minutes=15)
CANCELLATION_CUTOFF = dt.timedelta(minutes=30)


def _bounds(reservation: Item) -> tuple[dt.datetime, dt.datetime]:
    return timeutils.parse_datetime(reservation["startTime"]), timeutils.parse_datetime(reservation["endTime"])


def require_reservation(reservation_id: str) -> Item:
    reservation = bookings.get_reservation(reservation_id)
    if not reservation:
        raise NotFound("Reservation not found.")
    return reservation


def address_for_table(table_id: str) -> str:
    try:
        return locations.location_by_table(table_id).get("address", "Unknown address")
    except BadRequest:
        return "Unknown address"


def view(reservation: Item, *, include_invite_flag: bool = True) -> Item:
    """Reservation response with location address, pre-order flag and invite-link availability."""
    order = bookings.active_order(reservation["id"])
    invite = False
    if (
        include_invite_flag
        and dynamo.number(reservation.get("guestCount")) > 1
        and mappers.reservation_status(reservation) != ReservationStatus.Completed
    ):
        group = bookings.group_by_reservation(reservation["id"])
        invite = bool(group) and groups.is_open(group)
    return mappers.reservation_response(
        reservation,
        reservation.get("locationAddress") or address_for_table(reservation.get("tableId", "")),
        order,
        guest_invite_available=invite,
    )


def _ensure_no_overlap(table_id: str, start: dt.datetime, end: dt.datetime, exclude_id: str | None = None) -> None:
    now = timeutils.utcnow()
    for other in bookings.reservations_by_table(table_id):
        if other["id"] == exclude_id or mappers.reservation_status(other) in (
            ReservationStatus.Cancelled,
            ReservationStatus.Completed,
        ):
            continue
        other_start, other_end = _bounds(other)
        if other_end > now and start < other_end + BOOKING_BUFFER and end > other_start - BOOKING_BUFFER:
            raise BadRequest(
                f"Reservation from {start:%H:%M} to {end:%H:%M} overlaps with an existing reservation "
                f"for table '{table_id}'."
            )


def _validate_times(start: dt.datetime, end: dt.datetime) -> None:
    now = timeutils.utcnow()
    if start - now < MIN_LEAD_TIME:
        raise BadRequest(
            "Reservations must be made at least 15 minutes in advance. "
            f"Requested start time: {start:%H:%M}, Current time: {now:%H:%M} UTC."
        )
    if end <= start:
        raise BadRequest(f"End time ({end:%H:%M}) must be after start time ({start:%H:%M}).")
    tables.validate_window(start, end)


def _validate_guests(guest_count: int, capacity: int) -> None:
    if guest_count < 1:
        raise BadRequest("Guest count must be at least 1.")
    if guest_count > capacity:
        raise BadRequest(f"Guest count ({guest_count}) exceeds table capacity ({capacity}).")


def create(caller: Caller, body: dict[str, Any]) -> Item:
    table_id = body.get("tableId")
    table = catalog.get_table(table_id) if isinstance(table_id, str) and table_id else None
    if not table:
        raise BadRequest(f"The specified table '{table_id}' was not found.")
    location = locations.location_by_table(table["id"])

    if caller.is_waiter:
        waiter = waiters.require_waiter(caller.user_id)
        if waiter["locationId"] != table["locationId"]:
            raise Forbidden(
                f"Action forbidden: You are assigned to location '{waiter['locationId']}', "
                f"but table '{table['id']}' belongs to location '{table['locationId']}'."
            )
        customer_id = None
        customer_email = optional_str(body, "customerEmail")
        if customer_email:
            customer_id = people.attributes(people.user_by_email(customer_email)).get("sub")
            if not customer_id:
                raise NotFound(f"Customer with email '{customer_email}' not found.")
        waiter_id, created_by_waiter = caller.user_id, True
    else:
        customer_id = caller.user_id
        waiter_id, created_by_waiter = waiters.least_busy_waiter(table["locationId"])["userId"], False

    start = timeutils.parse_datetime(body.get("startTime"), "startTime")
    end = timeutils.parse_datetime(body.get("endTime"), "endTime")
    guest_count = as_int(body.get("guestCount"), "guestCount")
    _validate_times(start, end)
    _validate_guests(guest_count, int(dynamo.number(table.get("capacity"))))
    _ensure_no_overlap(table["id"], start, end)

    reservation: Item = {
        "id": str(uuid.uuid4()),
        "tableId": table["id"],
        "waiterId": waiter_id,
        "createdByWaiter": created_by_waiter,
        "startTime": timeutils.iso(start),
        "endTime": timeutils.iso(end),
        "guestCount": guest_count,
        "status": int(ReservationStatus.Reserved),
        "locationId": location["id"],
        "locationAddress": location.get("address", ""),
    }
    if customer_id:
        reservation["customerId"] = customer_id
    bookings.save_reservation(reservation)
    waiters.assign_reservation(waiter_id, reservation["id"])
    has_group = guest_count >= 2 and bool(customer_id)
    if has_group:
        groups.create_group(reservation["id"])
    logger.info("Created reservation %s on table %s", reservation["id"], table["id"])
    return mappers.reservation_response(reservation, location.get("address", ""), guest_invite_available=has_group)


def get_for_caller(caller: Caller, reservation_id: str) -> Item:
    reservation = require_reservation(reservation_id)
    allowed = caller.is_admin or caller.user_id in (reservation.get("customerId"), reservation.get("waiterId"))
    if not allowed:
        raise Forbidden("You are not allowed to view this reservation.")
    return view(reservation)


def list_for_caller(caller: Caller) -> list[Item]:
    if caller.is_admin:
        items = bookings.all_reservations()
    elif caller.is_waiter:
        items = bookings.reservations_by_waiter(caller.user_id)
    elif auth.CUSTOMER in caller.groups:
        items = bookings.reservations_by_customer(caller.user_id)
    else:
        raise Forbidden("Forbidden: User does not have the required permissions.")
    result = []
    for reservation in sorted(items, key=lambda r: str(r.get("startTime", ""))):
        try:
            result.append(view(reservation))
        except Exception:  # one corrupted record must not hide the others
            logger.exception("Skipping reservation %s", reservation.get("id"))
    return result


def _ensure_can_modify(caller: Caller, reservation: Item, action: str) -> None:
    owner_field = "waiterId" if caller.is_waiter else "customerId"
    if reservation.get(owner_field) != caller.user_id:
        raise Forbidden(f"Not authorized to {action} this reservation.")


def after_status_change(reservation: Item) -> None:
    """Keep the group pre-order in sync with the reservation status."""
    if mappers.reservation_status(reservation) == ReservationStatus.Reserved:
        if reservation.get("customerId") and dynamo.number(reservation.get("guestCount")) >= 2:
            groups.ensure_group(reservation["id"])
    else:
        groups.close_group(reservation["id"])


def cancel(caller: Caller, body: dict[str, Any]) -> None:
    reservation_id = body.get("id") or body.get("reservationId")
    if not isinstance(reservation_id, str) or not reservation_id.strip():
        raise BadRequest("ReservationId is required")
    reservation = require_reservation(reservation_id)
    _ensure_can_modify(caller, reservation, "cancel")
    if mappers.reservation_status(reservation) != ReservationStatus.Reserved:
        raise BadRequest("Only reservations in 'Reserved' status can be cancelled.")
    start, _ = _bounds(reservation)
    if start - timeutils.utcnow() < CANCELLATION_CUTOFF:
        raise BadRequest("Too late to cancel reservation. Must be 30 minutes before reservation time")
    reservation["status"] = int(ReservationStatus.Cancelled)
    bookings.save_reservation(reservation)
    after_status_change(reservation)
    waiters.release_reservation(reservation["id"])
    order = bookings.active_order(reservation["id"])
    if order:
        order["status"] = int(OrderStatus.Cancelled)
        bookings.save_order(order)


def edit(caller: Caller, body: dict[str, Any]) -> Item:
    reservation_id = body.get("reservationId")
    if not isinstance(reservation_id, str) or not reservation_id.strip():
        raise BadRequest("Invalid request body")
    reservation = require_reservation(reservation_id)
    _ensure_can_modify(caller, reservation, "edit")
    if mappers.reservation_status(reservation) != ReservationStatus.Reserved:
        raise BadRequest("Only reservations in 'Reserved' status can be edited.")
    if not caller.is_waiter and _bounds(reservation)[0] - timeutils.utcnow() < CANCELLATION_CUTOFF:
        raise BadRequest("Reservations can only be edited at least 30 minutes before their current start time.")
    start = timeutils.parse_datetime(body.get("startTime"), "startTime")
    end = timeutils.parse_datetime(body.get("endTime"), "endTime")
    guest_count = as_int(body.get("guestCount"), "guestCount")
    if start - timeutils.utcnow() < MIN_LEAD_TIME:
        raise BadRequest("Must edit at least 15 minutes in advance.")
    if start >= end:
        raise BadRequest("End time must be after start time.")
    tables.validate_window(start, end)
    table = catalog.get_table(reservation["tableId"])
    if not table:
        raise NotFound("Table not found.")
    if guest_count < 1 or dynamo.number(table.get("capacity")) < guest_count:
        raise BadRequest("Table capacity is insufficient for the number of guests.")
    group = bookings.group_by_reservation(reservation_id)
    if (
        group
        and len([s for s in bookings.sessions_by_group(group["groupReservationId"]) if not s.get("isOwnerSession")]) + 1
        > guest_count
    ):
        raise Conflict("Remove extra group participants before reducing the guest count.")
    try:
        _ensure_no_overlap(table["id"], start, end, exclude_id=reservation["id"])
    except BadRequest as exc:
        raise Conflict("Time overlaps with existing reservation.") from exc
    reservation.update(startTime=timeutils.iso(start), endTime=timeutils.iso(end), guestCount=guest_count)
    bookings.save_reservation(reservation)
    after_status_change(reservation)
    return view(reservation)


def update_status(caller: Caller, reservation_id: str, body: dict[str, Any]) -> None:
    if "newStatus" not in body:
        raise BadRequest("Invalid request body. Please provide a valid JSON with the new status.")
    new_status = parse_enum(ReservationStatus, body.get("newStatus"), "status")
    reservation = require_reservation(reservation_id)
    if reservation.get("waiterId") != caller.user_id:
        raise Forbidden("You are not the waiter assigned to this reservation.")
    current = mappers.reservation_status(reservation)
    if current in (ReservationStatus.Cancelled, ReservationStatus.Completed):
        raise BadRequest("Cannot update a cancelled or completed reservation status.")
    if new_status == current:
        raise BadRequest("The new status is the same as the current status.")
    if new_status == ReservationStatus.Reserved:
        raise BadRequest("Cannot update reservation status to Reserved.")
    if new_status == ReservationStatus.Completed and current != ReservationStatus.InProgress:
        raise BadRequest("Start the visit before completing it.")
    reservation["status"] = int(new_status)
    if new_status == ReservationStatus.Completed:
        reservation["completedAt"] = timeutils.iso(timeutils.utcnow())
        reservation["feedbackToken"] = secrets.token_urlsafe(32)
        reservation["feedbackTokenExpiresAt"] = int((timeutils.utcnow() + dt.timedelta(days=7)).timestamp())
        reports.prepare_completed_reservation(reservation)
    bookings.save_reservation(reservation)
    after_status_change(reservation)
    if new_status in (ReservationStatus.Cancelled, ReservationStatus.Completed):
        waiters.release_reservation(reservation_id)
    if new_status == ReservationStatus.Cancelled:
        order = bookings.active_order(reservation_id)
        if order:
            order["status"] = int(OrderStatus.Cancelled)
            bookings.save_order(order)
    if new_status == ReservationStatus.Completed:
        reports.publish_completed_reservation(reservation)


def change_table(caller: Caller, reservation_id: str, body: dict[str, Any]) -> Item:
    new_table_id = body.get("tableId")
    if not isinstance(new_table_id, str) or not new_table_id.strip():
        raise BadRequest("TableId must be provided.")
    reservation = require_reservation(reservation_id)
    if mappers.reservation_status(reservation) not in (ReservationStatus.Reserved, ReservationStatus.InProgress):
        raise BadRequest("A finished reservation cannot be moved to another table.")
    if not reservation.get("waiterId"):
        raise BadRequest(f"Reservation '{reservation_id}' has no assigned waiter.")
    if reservation["waiterId"].lower() != caller.user_id.lower():
        raise Forbidden(
            f"Action forbidden: You ({caller.user_id}) are not the assigned waiter "
            f"({reservation['waiterId']}) for reservation '{reservation_id}'."
        )
    waiter = waiters.require_waiter(caller.user_id)
    new_table = catalog.get_table(new_table_id)
    if not new_table:
        raise BadRequest(f"The specified table '{new_table_id}' was not found.")
    if new_table["locationId"] != waiter["locationId"]:
        raise Forbidden(
            f"Action forbidden: Cannot assign reservation to a table in location '{new_table['locationId']}' "
            f"because you are assigned to location '{waiter['locationId']}'."
        )
    _validate_guests(int(dynamo.number(reservation.get("guestCount"))), int(dynamo.number(new_table.get("capacity"))))
    start, end = _bounds(reservation)
    _ensure_no_overlap(new_table_id, start, end, exclude_id=reservation_id)
    reservation["tableId"] = new_table_id
    bookings.save_reservation(reservation)
    return view(reservation)
