"""Route table: (HTTP method, path template) → handler. Mirrors RouteRegistry.cs plus the homework routes."""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from core.http import Request
from handlers import bookings, catalog, groups, users

Handler = Callable[[Request], dict[str, Any]]

_ROUTES: list[tuple[str, str, Handler]] = [
    # Auth and users
    ("POST", "/register", users.register),
    ("POST", "/signin", users.sign_in),
    ("POST", "/confirm-registration", users.confirm_registration),
    ("POST", "/resend-confirmation", users.resend_confirmation),
    ("POST", "/forgot-password", users.forgot_password),
    ("POST", "/reset-password", users.reset_password),
    ("GET", "/me", users.me),
    ("PUT", "/me", users.update_me),
    ("PUT", "/me/change-password", users.change_password),
    ("PUT", "/me/profile-image", users.upload_profile_image),
    ("GET", "/users", users.search),
    ("GET", "/users/{id}/profile-image", users.profile_image),
    ("GET", "/users/{id}/name", users.name),
    # Locations
    ("GET", "/locations", catalog.list_locations),
    ("POST", "/locations", catalog.create_location),
    ("GET", "/locations/{id}", catalog.get_location),
    ("PUT", "/locations/{id}", catalog.update_location),
    ("DELETE", "/locations/{id}", catalog.delete_location),
    ("GET", "/locations/{id}/dishes", catalog.location_dishes),
    ("DELETE", "/locations/{locationId}/dishes/{dishId}", catalog.remove_location_dish),
    ("GET", "/locations/{locationId}/tables/all", catalog.location_tables),
    # Tables
    ("POST", "/tables", catalog.create_table),
    ("PUT", "/tables/{id}", catalog.update_table),
    ("DELETE", "/tables/{id}", catalog.delete_table),
    ("GET", "/available-tables", catalog.available_tables),
    ("GET", "/tables/{id}/available-time-slots", catalog.time_slots),
    # Waiters
    ("GET", "/waiters", catalog.list_waiters),
    ("POST", "/waiters", catalog.add_waiter),
    ("DELETE", "/waiters", catalog.remove_waiter),
    ("GET", "/waiters/{userId}/location", catalog.waiter_location),
    # Dishes
    ("GET", "/dishes", catalog.list_dishes),
    ("POST", "/dishes", catalog.create_dish),
    ("GET", "/dishes/popular", catalog.popular_dishes),
    ("GET", "/dishes/{id}", catalog.get_dish),
    ("PUT", "/dishes/{id}", catalog.update_dish),
    ("DELETE", "/dishes/{id}", catalog.delete_dish),
    # Reservations
    ("POST", "/reservations", bookings.create_reservation),
    ("GET", "/reservations", bookings.list_reservations),
    ("PUT", "/reservations", bookings.edit_reservation),
    ("DELETE", "/reservations", bookings.cancel_reservation),
    ("GET", "/reservations/{reservationId}", bookings.get_reservation),
    ("PATCH", "/reservations/{reservationId}/status", bookings.update_reservation_status),
    ("PATCH", "/reservations/{reservationId}/table", bookings.change_reservation_table),
    ("GET", "/reservations/{reservationId}/feedback", bookings.reservation_feedback),
    ("GET", "/reservations/{reservationId}/feedback-token", bookings.feedback_token),
    # Orders
    ("GET", "/orders", bookings.list_orders),
    ("POST", "/orders", bookings.create_order),
    ("GET", "/orders/{reservationId}", bookings.get_order),
    ("PUT", "/orders/{reservationId}", bookings.edit_order),
    ("DELETE", "/orders/{reservationId}", bookings.cancel_order),
    ("POST", "/orders/{reservationId}/submit", bookings.submit_order),
    ("POST", "/orders/{reservationId}/unsubmit", bookings.unsubmit_order),
    ("PATCH", "/reservations/{reservationId}/order/confirmations/{dishId}", bookings.confirm_order_dish),
    ("PATCH", "/reservations/{reservationId}/order/cancellations/{dishId}", bookings.cancel_order_dish),
    # Group pre-order: invites and guest carts
    ("GET", "/reservations/{reservationId}/invite-token", groups.invite_token),
    ("GET", "/guest/invites/{token}", groups.invite),
    ("POST", "/guest/sessions", groups.create_session),
    ("GET", "/guest/sessions/{guestSessionId}", groups.get_session),
    ("GET", "/guest/sessions/{guestSessionId}/menu", groups.menu),
    ("POST", "/guest/sessions/{guestSessionId}/dishes", groups.add_dish),
    ("DELETE", "/guest/sessions/{guestSessionId}/dishes", groups.remove_dish),
    ("POST", "/guest/sessions/{guestSessionId}/submit", groups.submit_cart),
    ("GET", "/guest/groups/{groupReservationId}/status", groups.status),
    # Group pre-order: owner review (homework levels 1–3)
    ("GET", "/guest/groups/{groupReservationId}/sessions", groups.sessions),
    ("GET", "/reservations/{reservationId}/guest-session-id", groups.owner_session),
    ("POST", "/group-reservations/{groupReservationId}/submit", groups.submit_group),
    ("DELETE", "/guest/groups/{groupReservationId}/sessions/{guestSessionId}", groups.remove_session),
    # Feedback, notifications, reports
    ("GET", "/feedback", bookings.location_feedback),
    ("POST", "/feedback", bookings.create_feedback),
    ("PUT", "/feedback", bookings.update_feedback),
    ("GET", "/notifications", bookings.list_notifications),
    ("PATCH", "/notifications/{id}/read", bookings.read_notification),
    ("GET", "/reports", bookings.report_history),
    ("GET", "/reports/generate", bookings.generate_report),
    ("GET", "/reports/download", bookings.download_report),
]


def _compile(template: str) -> re.Pattern[str]:
    return re.compile("^" + re.sub(r"\{(\w+)\}", r"(?P<\1>[^/]+)", template) + "$")


ROUTES: list[tuple[str, str, re.Pattern[str], Handler]] = [
    (method, template, _compile(template), handler) for method, template, handler in _ROUTES
]


def resolve(method: str, path: str) -> tuple[Handler, dict[str, str]] | None:
    for route_method, _template, pattern, handler in ROUTES:
        if route_method == method:
            match = pattern.match(path)
            if match:
                return handler, match.groupdict()
    return None
