"""Typed HTTP client for the restaurant API (group pre-order flows)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Self

import httpx

JSON = dict[str, Any]


class ApiError(Exception):
    """Raised for any non-2xx response or transport failure."""

    def __init__(self, status_code: int, body: Any, method: str = "", url: str = "") -> None:
        self.status_code = status_code
        self.body = body
        self.method = method
        self.url = url
        super().__init__(f"{method} {url} -> {status_code}: {body!r}")

    @property
    def message(self) -> str:
        if isinstance(self.body, dict):
            return str(self.body.get("message") or self.body.get("error") or "")
        return str(self.body)


@dataclass(frozen=True, slots=True)
class ApiResponse:
    """Raw response, returned by `RestaurantApi.raw` for negative tests."""

    status_code: int
    body: Any


class RestaurantApi:
    """Thin wrapper over the REST API.

    Methods return parsed JSON and raise `ApiError` on non-2xx. Use `raw()` to
    get `(status_code, body)` without raising. Guest-session methods take a
    `session_token`, sent as `Authorization: Bearer <token>`; the client's own
    token is used otherwise.
    """

    def __init__(self, base_url: str, token: str | None = None, timeout: float = 30.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self._client = httpx.Client(base_url=self.base_url, timeout=timeout)

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    def with_token(self, token: str | None) -> RestaurantApi:
        """Return a new client for the same API with a different token."""
        return RestaurantApi(self.base_url, token, self._client.timeout.read or 30.0)

    # ---- transport -------------------------------------------------------

    def raw(
        self,
        method: str,
        path: str,
        *,
        json: JSON | None = None,
        params: dict[str, Any] | None = None,
        token: str | None = None,
    ) -> ApiResponse:
        """Send a request and return status and body without raising on HTTP errors."""
        bearer = token or self.token
        headers = {"Authorization": f"Bearer {bearer}"} if bearer else {}
        clean_params = {k: v for k, v in (params or {}).items() if v is not None}
        try:
            resp = self._client.request(method, path, json=json, params=clean_params or None, headers=headers)
        except httpx.HTTPError as exc:
            raise ApiError(0, str(exc), method, f"{self.base_url}{path}") from exc
        try:
            body: Any = resp.json() if resp.content else None
        except ValueError:
            body = resp.text
        return ApiResponse(resp.status_code, body)

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: JSON | None = None,
        params: dict[str, Any] | None = None,
        token: str | None = None,
    ) -> Any:
        resp = self.raw(method, path, json=json, params=params, token=token)
        if not 200 <= resp.status_code < 300:
            raise ApiError(resp.status_code, resp.body, method, f"{self.base_url}{path}")
        return resp.body

    # ---- auth ------------------------------------------------------------

    def signin(self, email: str, password: str) -> JSON:
        """POST /signin -> {idToken, accessToken, message}."""
        return self._request("POST", "/signin", json={"email": email, "password": password})

    # ---- catalog ---------------------------------------------------------

    def get_locations(self) -> list[JSON]:
        return self._request("GET", "/locations")

    def get_dishes(self) -> JSON | list[JSON]:
        return self._request("GET", "/dishes")

    def get_available_tables(self, location_id: str, start_time: str, capacity: int | None = None) -> list[JSON]:
        """GET /available-tables; `start_time` is the ISO datetime the backend expects."""
        return self._request(
            "GET",
            "/available-tables",
            params={"locationId": location_id, "startTime": start_time, "capacity": capacity},
        )

    # ---- reservations / orders -------------------------------------------

    def get_time_slots(self, table_id: str, date: str) -> list[JSON]:
        return self._request("GET", f"/tables/{table_id}/available-time-slots", params={"startTime": date})

    def create_reservation(self, table_id: str, start_time: str, end_time: str, guest_count: int) -> JSON:
        return self._request(
            "POST",
            "/reservations",
            json={"tableId": table_id, "startTime": start_time, "endTime": end_time, "guestCount": guest_count},
        )

    def get_reservations(self) -> list[JSON]:
        return self._request("GET", "/reservations")

    def cancel_reservation(self, reservation_id: str) -> JSON:
        return self._request("DELETE", "/reservations", params={"reservationId": reservation_id})

    def get_order(self, reservation_id: str) -> JSON:
        return self._request("GET", f"/orders/{reservation_id}")

    # ---- group pre-order: owner side --------------------------------------

    def get_invite_token(self, reservation_id: str) -> str:
        """GET /reservations/{id}/invite-token; returns the token string."""
        body = self._request("GET", f"/reservations/{reservation_id}/invite-token")
        if isinstance(body, dict):
            return str(body.get("token") or body.get("inviteToken") or body.get("Token"))
        return str(body)

    def get_owner_session_id(self, reservation_id: str) -> str:
        body = self._request("GET", f"/reservations/{reservation_id}/guest-session-id")
        if isinstance(body, dict):
            return str(body.get("guestSessionId"))
        return str(body)

    def get_group_sessions(self, group_reservation_id: str) -> JSON:
        return self._request("GET", f"/guest/groups/{group_reservation_id}/sessions")

    def submit_group_preorder(self, group_reservation_id: str, reservation_id: str | None = None) -> list[JSON]:
        payload: JSON = {"reservationId": reservation_id} if reservation_id else {}
        return self._request("POST", f"/group-reservations/{group_reservation_id}/submit", json=payload)

    def remove_guest_session(self, group_reservation_id: str, session_id: str) -> JSON:
        return self._request("DELETE", f"/guest/groups/{group_reservation_id}/sessions/{session_id}")

    # ---- group pre-order: guest side ---------------------------------------

    def get_invite_info(self, token: str, bearer: str | None = None) -> JSON:
        """GET /guest/invites/{token}; optional bearer (user or guest-session token)."""
        return self._request("GET", f"/guest/invites/{token}", token=bearer)

    def create_guest_session(self, group_reservation_id: str, guest_name: str) -> JSON:
        return self._request(
            "POST",
            "/guest/sessions",
            json={"groupReservationId": group_reservation_id, "guestName": guest_name},
        )

    def get_guest_session(self, session_id: str, session_token: str | None = None) -> JSON:
        return self._request("GET", f"/guest/sessions/{session_id}", token=session_token)

    def get_guest_menu(self, session_id: str, session_token: str | None = None) -> JSON:
        return self._request("GET", f"/guest/sessions/{session_id}/menu", token=session_token)

    def add_guest_dish(
        self, session_id: str, dish_id: str, quantity: int = 1, session_token: str | None = None
    ) -> JSON:
        return self._request(
            "POST",
            f"/guest/sessions/{session_id}/dishes",
            json={"dishId": dish_id, "quantity": quantity},
            token=session_token,
        )

    def remove_guest_dish(
        self, session_id: str, dish_id: str, quantity: int = 1, session_token: str | None = None
    ) -> JSON:
        return self._request(
            "DELETE",
            f"/guest/sessions/{session_id}/dishes",
            params={"dishId": dish_id, "quantity": quantity},
            token=session_token,
        )

    def submit_guest_session(self, session_id: str, session_token: str | None = None) -> JSON:
        return self._request("POST", f"/guest/sessions/{session_id}/submit", token=session_token)

    def get_group_status(self, group_reservation_id: str) -> JSON:
        """Public (no auth) status of a group reservation."""
        return self._request("GET", f"/guest/groups/{group_reservation_id}/status")
