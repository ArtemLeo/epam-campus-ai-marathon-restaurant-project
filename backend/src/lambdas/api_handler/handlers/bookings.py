"""Reservations, orders, feedback, notifications and reports endpoints."""

from __future__ import annotations

from typing import Any

from core import http, jwt_verifier
from core.auth import ADMIN, WAITER, require_caller, require_role
from core.enums import OrderItemState
from core.http import Request
from services import feedback, notifications, orders, reports, reservations

# --- Reservations ------------------------------------------------------------


def create_reservation(req: Request) -> dict[str, Any]:
    caller = require_caller(req.caller)
    return http.ok(reservations.create(caller, req.json()), status=201)


def list_reservations(req: Request) -> dict[str, Any]:
    return http.ok(reservations.list_for_caller(require_caller(req.caller)))


def get_reservation(req: Request) -> dict[str, Any]:
    return http.ok(reservations.get_for_caller(require_caller(req.caller), req.param("reservationId")))


def cancel_reservation(req: Request) -> dict[str, Any]:
    caller = require_caller(req.caller)
    body = req.json() if req.raw_body else dict(req.query)
    reservations.cancel(caller, body)
    return http.message("Reservation cancelled successfully")


def edit_reservation(req: Request) -> dict[str, Any]:
    return http.ok(reservations.edit(require_caller(req.caller), req.json()))


def update_reservation_status(req: Request) -> dict[str, Any]:
    caller = require_role(req.caller, WAITER)
    reservations.update_status(caller, req.param("reservationId"), req.json())
    return http.message("Reservation status updated successfully.")


def change_reservation_table(req: Request) -> dict[str, Any]:
    caller = require_role(req.caller, WAITER)
    return http.ok(reservations.change_table(caller, req.param("reservationId"), req.json()))


def reservation_feedback(req: Request) -> dict[str, Any]:
    return http.ok(feedback.for_reservation(req.param("reservationId")))


def feedback_token(req: Request) -> dict[str, Any]:
    return http.ok(feedback.feedback_token(require_caller(req.caller), req.param("reservationId")))


# --- Orders --------------------------------------------------------------------


def list_orders(req: Request) -> dict[str, Any]:
    return http.ok(orders.list_for_customer(require_caller(req.caller)))


def get_order(req: Request) -> dict[str, Any]:
    return http.ok(orders.get_for_reservation(require_caller(req.caller), req.param("reservationId")))


def create_order(req: Request) -> dict[str, Any]:
    return http.ok(orders.create(require_caller(req.caller), req.json()), status=201)


def edit_order(req: Request) -> dict[str, Any]:
    caller = require_caller(req.caller)
    return http.ok(orders.edit(caller, req.param("reservationId"), req.json()))


def cancel_order(req: Request) -> dict[str, Any]:
    orders.cancel(require_caller(req.caller), req.param("reservationId"))
    return http.ok("Pre-order canceled successfully.")


def submit_order(req: Request) -> dict[str, Any]:
    orders.submit(require_caller(req.caller), req.param("reservationId"))
    return http.ok("Pre-order submitted successfully.")


def unsubmit_order(req: Request) -> dict[str, Any]:
    orders.unsubmit(require_caller(req.caller), req.param("reservationId"))
    return http.ok("Pre-order unsubmitted successfully.")


def confirm_order_dish(req: Request) -> dict[str, Any]:
    caller = require_role(req.caller, WAITER)
    orders.set_dish_state(caller, req.param("reservationId"), req.param("dishId"), OrderItemState.Confirmed)
    return http.message("Pre order confirmed successfully")


def cancel_order_dish(req: Request) -> dict[str, Any]:
    caller = require_role(req.caller, WAITER)
    orders.set_dish_state(caller, req.param("reservationId"), req.param("dishId"), OrderItemState.Canceled)
    return http.message("Pre order dish canceled successfully")


# --- Feedback ------------------------------------------------------------------


def location_feedback(req: Request) -> dict[str, Any]:
    return http.ok(feedback.for_location(req.query))


def create_feedback(req: Request) -> dict[str, Any]:
    # Public route: anonymous guests (QR code) may rate; a signed-in customer is recognised by a verified token.
    caller = req.caller or jwt_verifier.optional_caller(req.bearer_token())
    return http.ok(feedback.create(req.json(), caller))


def update_feedback(req: Request) -> dict[str, Any]:
    feedback.update(require_caller(req.caller), req.json())
    return http.message("Feedback updated successfully.")


# --- Notifications -------------------------------------------------------------


def list_notifications(req: Request) -> dict[str, Any]:
    return http.ok(notifications.unread(require_caller(req.caller)))


def read_notification(req: Request) -> dict[str, Any]:
    notifications.mark_read(require_caller(req.caller), req.param("id"))
    return http.ok("Notification marked as read")


# --- Reports -------------------------------------------------------------------


def report_history(req: Request) -> dict[str, Any]:
    return http.ok(reports.history(require_role(req.caller, ADMIN)))


def generate_report(req: Request) -> dict[str, Any]:
    return http.ok(reports.generate(require_role(req.caller, ADMIN), req.query))


def download_report(req: Request) -> dict[str, Any]:
    content, file_name, content_type = reports.download(require_role(req.caller, ADMIN), req.query)
    return http.file(content, file_name, content_type)
