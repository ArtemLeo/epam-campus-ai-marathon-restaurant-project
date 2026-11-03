"""Group pre-order endpoints: invites, guest carts and the owner's review (homework levels 1–3)."""

from __future__ import annotations

from typing import Any

from core import errors, http, jwt_verifier
from core.auth import require_caller
from core.errors import ApiError
from core.http import Request
from services import groups

_CONFLICT_CODES = {errors.GROUP_RESERVATION_EXPIRED, errors.GROUP_RESERVATION_SUBMITTED}


def _as_conflict(exc: ApiError) -> ApiError:
    """Cart changes on a closed/submitted group answer 409, as in the original handlers."""
    return exc.with_status(409) if exc.error_code in _CONFLICT_CODES else exc


def invite_token(req: Request) -> dict[str, Any]:
    return http.ok(groups.invite_token(require_caller(req.caller), req.param("reservationId")))


def invite(req: Request) -> dict[str, Any]:
    token = req.bearer_token()
    caller = req.caller or jwt_verifier.optional_caller(token)
    return http.ok(groups.invite_details(req.param("token"), caller=caller, guest_token=None if caller else token))


def create_session(req: Request) -> dict[str, Any]:
    return http.ok(groups.create_session(req.json()))


def get_session(req: Request) -> dict[str, Any]:
    session_id = req.param("guestSessionId")
    groups.authorize_guest(req.bearer_token(), session_id)
    return http.ok(groups.session_info(session_id))


def menu(req: Request) -> dict[str, Any]:
    session_id = req.param("guestSessionId")
    groups.authorize_guest(req.bearer_token(), session_id)
    return http.ok(groups.menu(session_id))


def add_dish(req: Request) -> dict[str, Any]:
    session_id = req.param("guestSessionId")
    body = req.json()
    groups.authorize_guest(req.bearer_token(), session_id)
    try:
        groups.add_dish(session_id, body)
    except ApiError as exc:
        raise _as_conflict(exc) from exc
    return http.message("Dish added successfully.")


def remove_dish(req: Request) -> dict[str, Any]:
    session_id = req.param("guestSessionId")
    body = req.json() if req.raw_body else dict(req.query)
    groups.authorize_guest(req.bearer_token(), session_id)
    try:
        groups.remove_dish(session_id, body)
    except ApiError as exc:
        raise _as_conflict(exc) from exc
    return http.message("Dish removed successfully.")


def submit_cart(req: Request) -> dict[str, Any]:
    session_id = req.param("guestSessionId")
    groups.authorize_guest(req.bearer_token(), session_id)
    try:
        groups.submit_cart(session_id)
    except ApiError as exc:
        raise _as_conflict(exc) from exc
    return http.message("Cart submitted successfully.")


def status(req: Request) -> dict[str, Any]:
    return http.ok(groups.status(req.param("groupReservationId")))


def sessions(req: Request) -> dict[str, Any]:
    return http.ok(groups.sessions(require_caller(req.caller), req.param("groupReservationId")))


def owner_session(req: Request) -> dict[str, Any]:
    return http.ok(groups.owner_session_id(require_caller(req.caller), req.param("reservationId")))


def submit_group(req: Request) -> dict[str, Any]:
    caller = require_caller(req.caller)
    body = req.json() if req.raw_body else {}
    return http.ok(groups.submit_group(caller, req.param("groupReservationId"), body))


def remove_session(req: Request) -> dict[str, Any]:
    caller = require_caller(req.caller)
    return http.ok(groups.remove_session(caller, req.param("groupReservationId"), req.param("guestSessionId")))
