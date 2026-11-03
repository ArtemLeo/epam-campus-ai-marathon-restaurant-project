"""Customer feedback on service and cuisine, per reservation and per location."""

from __future__ import annotations

import datetime as dt
import math
import secrets
from typing import Any

from core import auth, dynamo, timeutils
from core.auth import Caller
from core.enums import FeedbackType, ReservationStatus, SortingOrder, parse_enum, stored_enum
from core.errors import BadRequest, Conflict, Forbidden
from core.validation import as_int
from repositories import bookings, catalog, people
from services import reports

Item = dict[str, Any]

PAGE_SIZE = 4


def _type(feedback: Item) -> FeedbackType:
    return stored_enum(FeedbackType, feedback.get("type"), FeedbackType.Service)


def _response(feedback: Item, with_username: bool = False) -> Item:
    item = {
        "reservationId": feedback["reservationId"],
        "locationId": feedback.get("locationId", ""),
        "userId": feedback.get("userId") or None,
        "comment": feedback.get("comment"),
        "rating": dynamo.number(feedback.get("rating")),
        "createdAt": feedback.get("createdAt"),
        "type": int(_type(feedback)),
        "username": None,
    }
    if with_username:
        item["username"] = people.full_name(item["userId"]) or "Anonymous User"
    return item


def _rating(body: dict[str, Any]) -> int:
    rating = as_int(body.get("rating"), "rating")
    if not 1 <= rating <= 5:
        raise BadRequest(f"Rating ({rating}) must be between 1 and 5.")
    return rating


def _reservation_id(body: dict[str, Any]) -> str:
    reservation_id = body.get("reservationId")
    if not isinstance(reservation_id, str) or not reservation_id.strip():
        raise BadRequest("Reservation ID cannot be null or empty.")
    return reservation_id


def create(body: dict[str, Any], caller: Caller | None) -> Item:
    """Anonymous (QR code) or customer feedback; waiters and admins cannot rate."""
    if caller and caller.role != auth.CUSTOMER:
        raise Forbidden("Only customers can create feedback.")
    reservation_id = _reservation_id(body)
    feedback_type = parse_enum(FeedbackType, body.get("type", 0), "type")
    rating = _rating(body)
    reservation = bookings.get_reservation(reservation_id)
    if not reservation:
        raise BadRequest(f"Reservation with ID {reservation_id} not found.")
    if (
        stored_enum(ReservationStatus, reservation.get("status"), ReservationStatus.Reserved)
        != ReservationStatus.Completed
    ):
        raise BadRequest("Feedback is available after the waiter completes the visit.")
    if caller:
        if caller.user_id != reservation.get("customerId"):
            raise Forbidden("You can only review your own reservation.")
    else:
        token = body.get("token")
        if (
            not isinstance(token, str)
            or not reservation.get("feedbackToken")
            or not secrets.compare_digest(token, reservation["feedbackToken"])
        ):
            raise Forbidden("Open the feedback link provided by your waiter.")
        if int(reservation.get("feedbackTokenExpiresAt", 0)) <= timeutils.utcnow().timestamp():
            raise Forbidden("This feedback link has expired.")
    existing = people.feedback_by_reservation(reservation_id)
    if any(_type(f) == feedback_type for f in existing):
        raise Conflict(
            "Feedback of this type already exists for the reservation. Please consider editing the existing feedback."
        )
    table = catalog.get_table(reservation.get("tableId", "")) or {}
    location_id = reservation.get("locationId") or table.get("locationId")
    if not location_id:
        raise BadRequest(f"Table with ID {reservation.get('tableId')} not found.")
    created_at = timeutils.utcnow()
    used_dates = {f["createdAt"] for f in existing}
    while created_at.isoformat(timespec="microseconds").replace("+00:00", "Z") in used_dates:
        created_at += dt.timedelta(microseconds=1)
    feedback: Item = {
        "reservationId": reservation_id,
        "createdAt": created_at.isoformat(timespec="microseconds").replace("+00:00", "Z"),
        "locationId": location_id,
        "comment": body.get("comment"),
        "rating": rating,
        "type": int(feedback_type),
    }
    if caller and caller.user_id == reservation.get("customerId"):
        feedback["userId"] = caller.user_id
    reports.prepare_completed_reservation(reservation, [*existing, feedback])
    dynamo.transaction(
        [
            dynamo.put_action("feedback", feedback, new_key="reservationId"),
            dynamo.put_action("reservations", reservation),
        ]
    )
    reservation["version"] = int(reservation.get("version", 0)) + 1
    reports.publish_completed_reservation(reservation)
    return _response(feedback)


def update(caller: Caller, body: dict[str, Any]) -> None:
    if body.get("userId") and body["userId"] != caller.user_id:
        raise Forbidden("User ID in request does not match authenticated user.")
    reservation_id = _reservation_id(body)
    feedback_type = parse_enum(FeedbackType, body.get("type", 0), "type")
    rating = _rating(body)
    existing = people.feedback_by_reservation(reservation_id)
    if not existing:
        raise BadRequest(f"No feedback found for reservation '{reservation_id}'.")
    feedback = next((f for f in existing if _type(f) == feedback_type), None)
    if feedback is None:
        raise BadRequest(f"No feedback of type '{feedback_type.name}' found for reservation '{reservation_id}'.")
    if feedback.get("userId") != caller.user_id:
        raise Forbidden("You can only edit your own feedback.")
    feedback.update(comment=body.get("comment"), rating=rating)
    reservation = bookings.get_reservation(reservation_id)
    if (
        not reservation
        or stored_enum(ReservationStatus, reservation.get("status"), ReservationStatus.Reserved)
        != ReservationStatus.Completed
    ):
        raise BadRequest("Feedback can only be edited for a completed visit.")
    reports.prepare_completed_reservation(reservation, existing)
    dynamo.transaction([dynamo.put_action("feedback", feedback), dynamo.put_action("reservations", reservation)])
    reservation["version"] = int(reservation.get("version", 0)) + 1
    reports.publish_completed_reservation(reservation)


def feedback_token(caller: Caller, reservation_id: str) -> Item:
    reservation = bookings.get_reservation(reservation_id)
    if not reservation:
        raise BadRequest("Reservation not found.")
    if not caller.is_admin and caller.user_id not in (reservation.get("customerId"), reservation.get("waiterId")):
        raise Forbidden("Only the reservation owner or assigned waiter can get its feedback link.")
    if (
        stored_enum(ReservationStatus, reservation.get("status"), ReservationStatus.Reserved)
        != ReservationStatus.Completed
    ):
        raise BadRequest("Complete the visit before creating a feedback link.")
    if not reservation.get("feedbackToken"):
        reservation["feedbackToken"] = secrets.token_urlsafe(32)
        reservation["feedbackTokenExpiresAt"] = int((timeutils.utcnow() + dt.timedelta(days=7)).timestamp())
        bookings.save_reservation(reservation)
    return {
        "token": reservation["feedbackToken"],
        "expiresAt": timeutils.iso(
            dt.datetime.fromtimestamp(int(reservation["feedbackTokenExpiresAt"]), timeutils.UTC)
        ),
    }


_SORT_KEYS = {
    SortingOrder.TopRatedFirst: (lambda f: dynamo.number(f.get("rating")), True),
    SortingOrder.LowRatedFirst: (lambda f: dynamo.number(f.get("rating")), False),
    SortingOrder.NewestFirst: (lambda f: str(f.get("createdAt", "")), True),
    SortingOrder.OldestFirst: (lambda f: str(f.get("createdAt", "")), False),
}


def for_location(query: dict[str, str]) -> Item:
    location_id = (query.get("locationId") or "").strip()
    if not location_id:
        raise BadRequest("Location ID is required.")
    try:
        feedback_type = parse_enum(FeedbackType, query.get("type"), "type")
    except BadRequest as exc:
        raise BadRequest("Invalid or missing feedback type.") from exc
    try:
        sort = parse_enum(SortingOrder, query.get("sort"), "sort")
    except BadRequest as exc:
        raise BadRequest("Invalid or missing sorting order.") from exc
    try:
        page = as_int(query.get("page"), "page")
    except BadRequest:
        page = 0
    if page < 1:
        raise BadRequest("Invalid or missing page number.")
    items = [f for f in people.feedback_by_location(location_id) if _type(f) == feedback_type]
    key, reverse = _SORT_KEYS[sort]
    items.sort(key=key, reverse=reverse)
    page_items = items[(page - 1) * PAGE_SIZE : page * PAGE_SIZE]
    return {
        "items": [_response(f, with_username=True) for f in page_items],
        "totalPages": math.ceil(len(items) / PAGE_SIZE),
        "currentPage": page,
    }


def for_reservation(reservation_id: str) -> Item:
    by_type = {_type(f): f for f in people.feedback_by_reservation(reservation_id)}
    service = by_type.get(FeedbackType.Service)
    cuisine = by_type.get(FeedbackType.CuisineExperience)
    return {
        "service": _response(service, with_username=True) if service else None,
        "cuisineExperience": _response(cuisine, with_username=True) if cuisine else None,
    }
