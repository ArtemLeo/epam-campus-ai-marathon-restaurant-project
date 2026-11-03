"""Shared helpers for Group Pre-Order API tests (raw httpx).

Endpoint paths/param names for tables/locations/dishes are centralised here
so they can be adjusted in one place if the backend differs.
"""

import contextlib
import os

import httpx

from api.client import RestaurantApi
from api.flow import create_reservation


def pick(d, *keys, default=None):
    """Return first present key (tolerates camelCase/PascalCase variants)."""
    if not isinstance(d, dict):
        return default
    for k in keys:
        if k in d:
            return d[k]
        for alt in (k[:1].upper() + k[1:], k[:1].lower() + k[1:]):
            if alt in d:
                return d[alt]
    return default


def as_list(body):
    if isinstance(body, list):
        return body
    if isinstance(body, dict):
        for k in ("content", "items", "data", "results", "dishes", "tables", "locations"):
            if isinstance(body.get(k), list):
                return body[k]
    return []


def auth(token):
    return {"Authorization": f"Bearer {token}"}


class Env:
    """Thin wrapper bundling base url + httpx calls."""

    def __init__(self, api_url):
        self.url = api_url.rstrip("/")
        self.http = httpx.Client(base_url=self.url, timeout=30)

    def close(self):
        self.http.close()

    def req(self, method, path, token=None, **kw):
        headers = kw.pop("headers", {})
        if token:
            headers.update(auth(token))
        return self.http.request(method, path, headers=headers, **kw)

    # ---- user management
    def new_customer_token(self, uid):
        email = os.environ["GUEST_EMAIL"]
        pwd = os.environ["GUEST_PASSWORD"]
        r = self.req("POST", "/signin", json={"email": email, "password": pwd})
        assert r.status_code == 200, f"cannot sign in second customer: {r.status_code} {r.text}"
        return pick(r.json(), "idToken", "accessToken")

    # ---- reservation setup
    def create_reservation(self, token, guests=3):
        with RestaurantApi(self.url, token) as api:
            return create_reservation(api, guests)

    def cancel_reservation(self, token, reservation_id):
        with contextlib.suppress(Exception):
            self.req("DELETE", "/reservations", token, params={"reservationId": reservation_id})

    def group_id_for(self, token, reservation_id):
        r = self.req("GET", f"/reservations/{reservation_id}/invite-token", token)
        assert r.status_code == 200, f"invite-token: {r.status_code} {r.text}"
        invite = pick(r.json(), "token")
        r = self.req("GET", f"/guest/invites/{invite}")
        assert r.status_code == 200, f"invite info: {r.status_code} {r.text}"
        gid = pick(r.json(), "groupReservationId")
        assert gid, f"no GroupReservationId in {r.text}"
        return gid

    def join(self, group_id, name):
        r = self.req("POST", "/guest/sessions", json={"groupReservationId": group_id, "guestName": name})
        assert r.status_code in (200, 201), f"join: {r.status_code} {r.text}"
        b = r.json()
        return pick(b, "sessionId"), pick(b, "sessionToken")

    def dishes(self, token, n=3):
        location_id = os.environ.get("AQA_LOCATION_ID")
        path = f"/locations/{location_id}/dishes" if location_id else "/dishes"
        r = self.req("GET", path, token)
        assert r.status_code == 200, f"dishes: {r.status_code} {r.text}"
        ds = as_list(r.json())
        assert len(ds) >= n, "not enough dishes"
        return ds[:n]

    def add_dish(self, session_id, session_token, dish_id, qty):
        r = self.req(
            "POST", f"/guest/sessions/{session_id}/dishes", session_token, json={"dishId": dish_id, "quantity": qty}
        )
        assert r.status_code in (200, 201, 204), f"add dish: {r.status_code} {r.text}"

    def submit_guest(self, session_id, session_token):
        r = self.req("POST", f"/guest/sessions/{session_id}/submit", session_token)
        assert r.status_code in (200, 201, 204), f"guest submit: {r.status_code} {r.text}"

    def participants(self, token, group_id):
        return self.req("GET", f"/guest/groups/{group_id}/sessions", token)

    def create_order(self, token, reservation_id, items):
        r = self.req(
            "POST",
            "/orders",
            token,
            json={"reservationId": reservation_id, "orderItems": [{"dishId": d, "quantity": q} for d, q in items]},
        )
        assert r.status_code in (200, 201), f"order: {r.status_code} {r.text}"
        return r.json()


def dish_id(d):
    return pick(d, "id", "dishId")


def parts_by_name(body):
    return {pick(p, "guestName", "name"): p for p in pick(body, "participants", default=[])}


def items_of(p):
    return pick(p, "items", "cartItems", "dishes", default=[])


def qty_by_dish(items):
    out = {}
    for i in items:
        k = pick(i, "dishId", "id") or pick(i.get("dish"), "id")
        out[k] = out.get(k, 0) + int(pick(i, "quantity", default=0))
    return out
