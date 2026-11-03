"""Test-data builder for group pre-order scenarios (shared by API and UI suites)."""

from __future__ import annotations

import contextlib
import os
import random
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from api.client import ApiError, RestaurantApi


@dataclass
class Guest:
    name: str
    session_id: str
    token: str
    dishes: list[tuple[dict[str, Any], int]] = field(default_factory=list)
    submitted: bool = False

    @property
    def total(self) -> float:
        return round(sum(float(d["price"]) * q for d, q in self.dishes), 2)


@dataclass
class Group:
    reservation_id: str
    group_id: str
    invite_token: str
    owner_session_id: str
    owner_dish: dict[str, Any]
    guests: list[Guest]
    dishes: list[dict[str, Any]]


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def create_reservation(api: RestaurantApi, guest_count: int) -> dict[str, Any]:
    """Book a free table for `guest_count` people on a random future slot (retries on conflicts)."""
    locations = api.get_locations()
    if location_id := os.getenv("AQA_LOCATION_ID"):
        locations = [location for location in locations if location["id"] == location_id]
    if not locations:
        raise AssertionError("No test restaurant is available. Check the admin test-data fixture.")
    last_conflict = None
    for _ in range(12):
        day = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(
            days=random.randint(3, 80)
        )
        location = random.choice(locations)
        loc_id = location.get("id") or location.get("locationId")
        tables = api.get_available_tables(loc_id, _iso(day), guest_count)
        tables = [t for t in tables if int(t.get("capacity", 0)) >= guest_count]
        if not tables:
            continue
        table = random.choice(tables)
        slots = api.get_time_slots(table["id"], _iso(day))
        if not slots:
            continue
        slot = random.choice(slots)
        try:
            body = api.create_reservation(table["id"], slot["start"], slot["end"], guest_count)
        except ApiError as exc:
            if exc.status_code != 409:
                raise
            last_conflict = exc
            continue
        if isinstance(body, dict) and "reservation" in body:
            body = body["reservation"]
        return body
    raise AssertionError(
        f"No bookable table for {guest_count} guests after 12 attempts; last conflict: {last_conflict}"
    )


def selectable_dishes(api: RestaurantApi, session_id: str, token: str) -> list[dict[str, Any]]:
    menu = api.get_guest_menu(session_id, token)["dishes"]
    dishes = [d for group in menu.values() for d in group if d.get("selectable", True)]
    if len(dishes) < 3:
        raise RuntimeError("Need at least 3 selectable dishes")
    return dishes


def build_group(
    owner_api: RestaurantApi,
    guest_names: list[str],
    *,
    guest_count: int | None = None,
    submit_carts: tuple[bool, ...] | None = None,
    add_dishes: bool = True,
) -> Group:
    """Create reservation + invite + guest sessions (+ dishes, + submitted carts) + owner's order."""
    reservation = create_reservation(owner_api, guest_count or max(len(guest_names) + 1, 3))
    rid = reservation["id"]
    token = owner_api.get_invite_token(rid)
    group_id = owner_api.get_invite_info(token, owner_api.token)["GroupReservationId"]
    owner_session = owner_api.get_owner_session_id(rid)

    guests: list[Guest] = []
    with RestaurantApi(owner_api.base_url) as anon:
        for name in guest_names:
            s = anon.create_guest_session(group_id, name)
            guests.append(Guest(name, s["SessionId"], s["SessionToken"]))
    dishes = selectable_dishes(owner_api, guests[0].session_id, guests[0].token) if guests else []

    if add_dishes:
        for i, g in enumerate(guests):
            dish = dishes[i % len(dishes)]
            qty = i + 1
            owner_api.add_guest_dish(g.session_id, dish["id"], qty, g.token)
            g.dishes.append((dish, qty))
    flags = submit_carts or (False,) * len(guests)
    for g, flag in zip(guests, flags, strict=False):
        if flag and g.dishes:
            owner_api.submit_guest_session(g.session_id, g.token)
            g.submitted = True

    owner_dish = dishes[-1] if dishes else {}
    if owner_dish:
        owner_api.raw(
            "POST", "/orders", json={"reservationId": rid, "orderItems": [{"dishId": owner_dish["id"], "quantity": 1}]}
        )
    return Group(rid, group_id, token, owner_session, owner_dish, guests, dishes)


def unique_name(prefix: str = "Guest") -> str:
    return f"{prefix}{uuid.uuid4().hex[:5]}"


def cleanup(api: RestaurantApi, reservation_id: str) -> None:
    with contextlib.suppress(ApiError):
        api.cancel_reservation(reservation_id)
