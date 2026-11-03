"""Group pre-order: invite links, guest sessions (carts) and the owner's consolidated order.

Guests join a group reservation through an invite token and get a random session token;
only its SHA-256 hash is stored. The reservation owner sees every participant and sends one
consolidated pre-order to the restaurant (marathon homework, levels 1–3).
"""

from __future__ import annotations

import base64
import binascii
import datetime as dt
import hashlib
import logging
import secrets
import uuid
from typing import Any

from core import config, dynamo, timeutils
from core.auth import Caller
from core.enums import (
    DishState,
    DishType,
    GroupReservationStatus,
    OrderItemState,
    OrderStatus,
    ReservationStatus,
    stored_enum,
)
from core.errors import (
    BadRequest,
    Conflict,
    Forbidden,
    NotFound,
    Unauthorized,
    group_expired,
    group_submitted,
    guest_limit_exceeded,
    guest_session_expired,
)
from core.validation import as_int
from repositories import bookings, catalog, people
from services import mappers, notifications

logger = logging.getLogger(__name__)

Item = dict[str, Any]

# Owner sessions get a deterministic id per group so concurrent requests cannot create two of them.
_OWNER_SESSION_NAMESPACE = uuid.UUID("6f1d2a8e-6a3c-4b9f-9a51-3c1f0e7b2d40")
SUBMITTED_ORDER = (OrderStatus.Submitted, OrderStatus.SubmittedByCustomer)


# --- Group reservations ----------------------------------------------------


def group_status(group: Item) -> GroupReservationStatus:
    return stored_enum(GroupReservationStatus, group.get("status"), GroupReservationStatus.Open)


def create_group(reservation_id: str) -> Item:
    group = {
        "groupReservationId": f"group:{reservation_id}",
        "reservationId": reservation_id,
        "reservationToken": uuid.uuid4().hex,
        "status": int(GroupReservationStatus.Open),
    }
    try:
        dynamo.save_versioned("group_reservations", group, new_key="groupReservationId")
        return group
    except Conflict:
        return _require_group(group["groupReservationId"])


def ensure_group(reservation_id: str) -> Item:
    return bookings.group_by_reservation(reservation_id) or create_group(reservation_id)


def close_group(reservation_id: str) -> None:
    group = bookings.group_by_reservation(reservation_id)
    if group and group_status(group) != GroupReservationStatus.Closed:
        group["status"] = int(GroupReservationStatus.Closed)
        bookings.save_group(group)


def _require_group(group_id: str) -> Item:
    group = bookings.get_group(group_id)
    if not group:
        raise NotFound("Group reservation was not found")
    return group


def _validate_open(group: Item) -> None:
    status = group_status(group)
    if status == GroupReservationStatus.Closed:
        raise group_expired()
    if status == GroupReservationStatus.Submitted:
        raise group_submitted()
    reservation = bookings.get_reservation(group["reservationId"])
    if not reservation or mappers.reservation_status(reservation) != ReservationStatus.Reserved:
        raise group_expired()
    if timeutils.utcnow() > timeutils.parse_datetime(reservation["startTime"]) - dt.timedelta(minutes=30):
        raise group_expired("Group pre-orders close 30 minutes before the reservation starts.")


def is_open(group: Item) -> bool:
    try:
        _validate_open(group)
        return True
    except BadRequest:
        return False


def _is_owner(caller: Caller | None, reservation: Item) -> bool:
    return bool(caller and reservation.get("customerId") and caller.user_id == reservation["customerId"])


def _require_owner(caller: Caller, reservation: Item) -> None:
    if not _is_owner(caller, reservation):
        raise Forbidden("Only the reservation owner can perform this action.")


def _location_for_reservation(reservation: Item) -> tuple[Item, Item | None]:
    table = catalog.get_table(reservation.get("tableId", ""))
    if not table:
        raise BadRequest("Associated table not found.")
    return table, catalog.get_location(table["locationId"])


def invite_token(caller: Caller, reservation_id: str) -> Item:
    """Invite token for the reservation owner (or its waiter); also used by the owner's group page."""
    reservation = bookings.get_reservation(reservation_id)
    if not reservation:
        raise NotFound(f"Reservation {reservation_id} was not found.")
    if not _is_owner(caller, reservation) and reservation.get("waiterId") != caller.user_id:
        raise Forbidden("Only the reservation owner can get its invite link.")
    if dynamo.number(reservation.get("guestCount")) < 2:
        raise BadRequest("Retrieving invitation token for the reservation with only one guest is not permitted.")
    group = bookings.group_by_reservation(reservation_id)
    if group is None:
        if mappers.reservation_status(reservation) != ReservationStatus.Reserved:
            raise group_expired("The group reservation is expired.")
        group = create_group(reservation_id)
    return {"token": group["reservationToken"]}


def invite_details(token: str, *, caller: Caller | None, guest_token: str | None) -> Item:
    """Public invite info. Guests get the original expiry/limit errors; the owner and joined guests always see it."""
    group = bookings.group_by_token(token)
    if not group:
        raise NotFound("Group reservation was not found")
    reservation = bookings.get_reservation(group["reservationId"])
    if not reservation:
        raise BadRequest("Associated reservation not found.")
    member = _is_owner(caller, reservation) or _session_for_token(guest_token, group["groupReservationId"]) is not None
    if not member:
        _validate_open(group)
        if _joined_guests(group["groupReservationId"]) + 1 >= dynamo.number(reservation.get("guestCount")):
            raise guest_limit_exceeded()
    table, location = _location_for_reservation(reservation)
    return {
        "GroupReservationId": group["groupReservationId"],
        "LocationId": table["locationId"],
        "RestaurantName": config.RESTAURANT_NAME,
        "LocationAddress": (location or {}).get("address", "Unknown Address"),
        "StartTime": reservation["startTime"],
        "EndTime": reservation["endTime"],
        "MaxGuestCount": dynamo.number(reservation.get("guestCount")),
        "TableNumber": dynamo.number(table.get("tableNumber")),
        "InviterName": people.full_name(reservation.get("customerId")) or "Unknown",
    }


def status(group_id: str) -> Item:
    group = _require_group(group_id)
    reservation = bookings.get_reservation(group["reservationId"])
    if not reservation:
        raise BadRequest("Associated reservation not found.")
    current_status = group_status(group)
    if current_status == GroupReservationStatus.Open and not is_open(group):
        current_status = GroupReservationStatus.Closed
    return {
        "currentParticipants": _joined_guests(group_id) + 1,
        "maxCapacity": dynamo.number(reservation.get("guestCount")),
        "status": current_status.name,
    }


# --- Guest sessions --------------------------------------------------------


def _hash_token(token: str) -> str | None:
    try:
        raw = base64.b64decode(token, validate=True)
    except (binascii.Error, ValueError):
        return None
    return base64.b64encode(hashlib.sha256(raw).digest()).decode()


def _session_for_token(token: str | None, group_id: str | None = None) -> Item | None:
    token_hash = _hash_token(token) if token else None
    session = bookings.session_by_token_hash(token_hash) if token_hash else None
    if session and group_id and session.get("groupReservationId") != group_id:
        return None
    return session


def authorize_guest(token: str | None, session_id: str) -> None:
    session = _session_for_token(token)
    if not session or session["guestSessionId"] != session_id:
        raise Unauthorized("Invalid guest session token")


def _guest_sessions(group_id: str) -> list[Item]:
    return [s for s in bookings.sessions_by_group(group_id) if not s.get("isOwnerSession")]


def _joined_guests(group_id: str) -> int:
    return len(_guest_sessions(group_id))


def create_session(body: dict[str, Any]) -> Item:
    group_id = body.get("groupReservationId")
    guest_name = body.get("guestName")
    if not isinstance(group_id, str) or not group_id.strip():
        raise BadRequest("The GroupReservationId field is required.")
    if not isinstance(guest_name, str) or not guest_name.strip() or len(guest_name.strip()) > 50:
        raise BadRequest("The GuestName field is required and must be at most 50 characters long.")
    group = _require_group(group_id)
    _validate_open(group)
    reservation = bookings.get_reservation(group["reservationId"])
    if not reservation:
        raise group_expired(f"Associated reservation for group '{group_id}' not found.")
    reservation_status = mappers.reservation_status(reservation)
    if reservation_status != ReservationStatus.Reserved:
        raise guest_session_expired(
            "This pre-order session has expired or is no longer active. "
            f"Current reservation status: '{reservation_status.name}'."
        )
    joined = _joined_guests(group_id)
    capacity = dynamo.number(reservation.get("guestCount"))
    if joined + 1 >= capacity:
        raise guest_limit_exceeded(
            f"Guest limit exceeded. Maximum capacity is {capacity}, but {joined} guests have already joined."
        )
    token = secrets.token_bytes(32)
    session = {
        "guestSessionId": str(uuid.uuid4()),
        "groupReservationId": group_id,
        "guestName": guest_name.strip(),
        "dishes": [],
        "guestSessionTokenHash": base64.b64encode(hashlib.sha256(token).digest()).decode(),
        "isOwnerSession": False,
        "isSubmitted": False,
        "createdAt": timeutils.iso(timeutils.utcnow()),
    }
    # Changing the group version serializes joins/removals with submission. A strong
    # reservation check also prevents a concurrent capacity reduction or cancellation.
    group["memberIds"] = [s["guestSessionId"] for s in _guest_sessions(group_id)] + [session["guestSessionId"]]
    dynamo.transaction(
        [
            dynamo.put_action("group_reservations", group),
            dynamo.put_action("guest_sessions", session, new_key="guestSessionId"),
            dynamo.put_action("reservations", reservation),
        ]
    )
    return {"SessionId": session["guestSessionId"], "SessionToken": base64.b64encode(token).decode()}


def _editable_session(session_id: str) -> Item:
    session = bookings.get_session(session_id)
    if not session:
        raise BadRequest(f"Guest session {session_id} not found.")
    if session.get("isSubmitted"):
        raise Conflict("Guest session is already submitted.")
    _validate_open(_require_group(session["groupReservationId"]))
    return session


def _save_editable_session(session: Item) -> None:
    group = _require_group(session["groupReservationId"])
    _validate_open(group)
    pin_dish_prices(group, session.get("dishes") or [])
    reservation = bookings.get_reservation(group["reservationId"])
    dynamo.transaction(
        [
            dynamo.put_action("guest_sessions", session),
            dynamo.put_action("group_reservations", group),
            dynamo.check_action("reservations", {"id": reservation["id"]}, reservation),
        ]
    )


def pin_dish_prices(group: Item, entries: list[Item]) -> None:
    """One agreed price per dish for the entire group, fixed at its first selection.

    The caller commits the changed group and cart/order together, so two first
    selections cannot race and establish different prices for the same dish.
    """
    snapshots = dict(group.get("dishSnapshots") or {})
    for entry in entries:
        snapshot = entry.get("dishSnapshot")
        if snapshot:
            snapshots.setdefault(entry["dishId"], dict(snapshot))
            entry["dishSnapshot"] = dict(snapshots[entry["dishId"]])
    group["dishSnapshots"] = snapshots


def _location_id_for_group(group_id: str) -> str:
    reservation = bookings.get_reservation(_require_group(group_id)["reservationId"])
    if not reservation:
        raise NotFound("Parent reservation not found.")
    table, _ = _location_for_reservation(reservation)
    return table["locationId"]


def menu(session_id: str) -> Item:
    session = bookings.get_session(session_id)
    if not session:
        raise BadRequest(f"Guest session '{session_id}' not found.")
    group = _require_group(session["groupReservationId"])
    _validate_open(group)
    grouped: dict[str, list[Item]] = {}
    for dish in catalog.dishes_for_location(_location_id_for_group(session["groupReservationId"])):
        state = mappers.dish_state(dish)
        grouped.setdefault(stored_enum(DishType, dish.get("dishType"), DishType.Appetizer).name, []).append(
            {
                "id": dish["id"],
                "name": dish.get("name", ""),
                "description": dish.get("description", ""),
                "price": dynamo.number(group.get("dishSnapshots", {}).get(dish["id"], dish).get("price")),
                "weight": dish.get("weight", ""),
                "calories": dish.get("calories", ""),
                "proteins": dish.get("proteins", ""),
                "fats": dish.get("fats", ""),
                "carbohydrates": dish.get("carbohydrates", ""),
                "vitamins": dish.get("vitamins", ""),
                "imageUrl": dish.get("imageUrl") or None,
                "state": state.name,
                "selectable": state == DishState.Available,
                **({"translations": dish["translations"]} if "translations" in dish else {}),
            }
        )
    return {"dishes": grouped}


def _dish_and_quantity(body: dict[str, Any]) -> tuple[str, int]:
    dish_id = body.get("dishId")
    try:
        quantity = as_int(body.get("quantity"), "quantity")
    except BadRequest:
        quantity = 0
    if not isinstance(dish_id, str) or not dish_id.strip() or quantity <= 0:
        raise BadRequest("DishId is required and Quantity must be greater than zero.")
    return dish_id, quantity


def add_dish(session_id: str, body: dict[str, Any]) -> None:
    dish_id, quantity = _dish_and_quantity(body)
    session = _editable_session(session_id)
    menu_dishes = {
        d["id"]: d for d in catalog.dishes_for_location(_location_id_for_group(session["groupReservationId"]))
    }
    dish = menu_dishes.get(dish_id)
    if not dish:
        raise BadRequest(f"Dish '{dish_id}' does not exist or is not available at this location.")
    if mappers.dish_state(dish) != DishState.Available:
        raise BadRequest(f"Dish '{dish_id}' is currently unavailable. State: '{mappers.dish_state(dish).name}'.")
    dishes = list(session.get("dishes") or [])
    entry = next((d for d in dishes if d.get("dishId") == dish_id), None)
    if entry:
        entry["quantity"] = int(dynamo.number(entry.get("quantity"))) + quantity
    else:
        dishes.append(
            {"dishId": dish_id, "quantity": quantity, "state": int(OrderItemState.Pending), "dishSnapshot": dict(dish)}
        )
    session["dishes"] = dishes
    _save_editable_session(session)


def remove_dish(session_id: str, body: dict[str, Any]) -> None:
    dish_id, quantity = _dish_and_quantity(body)
    session = _editable_session(session_id)
    dishes = list(session.get("dishes") or [])
    entry = next((d for d in dishes if d.get("dishId") == dish_id), None)
    if entry is None:
        raise BadRequest(f"Dish {dish_id} not found in guest session.")
    entry["quantity"] = int(dynamo.number(entry.get("quantity"))) - quantity
    session["dishes"] = [d for d in dishes if d is not entry or entry["quantity"] > 0]
    _save_editable_session(session)


def submit_cart(session_id: str) -> None:
    session = _editable_session(session_id)
    dishes = session.get("dishes") or []
    if not dishes:
        raise BadRequest("The cart is empty")
    found = catalog.dishes_by_ids([d["dishId"] for d in dishes])
    for entry in dishes:
        dish = found.get(entry["dishId"])
        if not dish or mappers.dish_state(dish) != DishState.Available:
            name = dish.get("name", entry["dishId"]) if dish else entry["dishId"]
            raise BadRequest(f"The dish '{name}' ({entry['dishId']}) is not available.")
    session["isSubmitted"] = True
    _save_editable_session(session)


# --- Participants and the owner's view (homework) --------------------------


def _short_dish(dish: Item) -> Item:
    return {
        "id": dish["id"],
        "name": dish.get("name", ""),
        "price": dynamo.number(dish.get("price")),
        "imageUrl": dish.get("imageUrl") or None,
        "weight": dish.get("weight") or None,
        **({"translations": dish["translations"]} if "translations" in dish else {}),
    }


def _items(entries: list[Item], dishes: dict[str, Item]) -> list[Item]:
    return [
        {
            "dish": _short_dish(e.get("dishSnapshot") or dishes[e["dishId"]]),
            "quantity": int(dynamo.number(e.get("quantity"))),
        }
        for e in entries
        if (e.get("dishSnapshot") or e.get("dishId") in dishes) and int(dynamo.number(e.get("quantity"))) > 0
    ]


def _total(items: list[Item]) -> int | float:
    return dynamo.number(sum((dynamo.decimal(i["dish"]["price"]) * i["quantity"] for i in items), dynamo.decimal(0)))


def _owner_entries(order: Item | None) -> list[Item]:
    if not order:
        return []
    return [
        d
        for d in order.get("dishes") or []
        if stored_enum(OrderItemState, d.get("state"), OrderItemState.Pending) != OrderItemState.Canceled
    ]


def _owner_session(group: Item, reservation: Item) -> Item:
    session_id = str(uuid.uuid5(_OWNER_SESSION_NAMESPACE, group["groupReservationId"]))
    session = bookings.get_session(session_id)
    if session is None:
        first_name = people.attributes(people.user_by_id(reservation.get("customerId", ""))).get("given_name")
        session = {
            "guestSessionId": session_id,
            "groupReservationId": group["groupReservationId"],
            "guestName": first_name or "Owner",
            "dishes": [],
            "isOwnerSession": True,
            "ownerUserId": reservation.get("customerId"),
            "isSubmitted": False,
            "createdAt": timeutils.iso(timeutils.utcnow()),
        }
        try:
            dynamo.save_versioned("guest_sessions", session, new_key="guestSessionId")
        except Conflict:
            session = bookings.get_session(session_id)
    return session


def _participants(
    group: Item, reservation: Item, *, source_order: Item | None = None, source_guests: list[Item] | None = None
) -> list[Item]:
    """Owner first (their cart is the reservation's pre-order), then guests in joining order."""
    if group.get("submittedParticipants") is not None:
        return group["submittedParticipants"]
    owner = _owner_session(group, reservation)
    order = source_order if source_order is not None else bookings.active_order(reservation["id"])
    guests = source_guests if source_guests is not None else _guest_sessions(group["groupReservationId"])
    owner_entries = _owner_entries(order)
    dish_ids = [e["dishId"] for e in owner_entries] + [d["dishId"] for s in guests for d in s.get("dishes") or []]
    dishes = catalog.dishes_by_ids(dish_ids)

    owner_items = _items(owner_entries, dishes)
    participants = [
        {
            "id": owner["guestSessionId"],
            "type": "Owner",
            "name": owner.get("guestName") or "Owner",
            "items": owner_items,
            "total": _total(owner_items),
            "isSubmitted": bool(order) and bookings.order_status(order) in SUBMITTED_ORDER,
        }
    ]
    for session in guests:
        items = _items(session.get("dishes") or [], dishes)
        participants.append(
            {
                "id": session["guestSessionId"],
                "type": "Guest",
                "name": session.get("guestName", "Guest"),
                "items": items,
                "total": _total(items),
                "isSubmitted": bool(session.get("isSubmitted")),
            }
        )
    return participants


def _snapshot(group: Item, reservation: Item) -> Item:
    participants = _participants(group, reservation)
    return {"participants": participants, "total": dynamo.number(sum(dynamo.decimal(p["total"]) for p in participants))}


def _owner_group(caller: Caller, group_id: str) -> tuple[Item, Item]:
    group = _require_group(group_id)
    reservation = bookings.get_reservation(group["reservationId"])
    if not reservation:
        raise NotFound("Parent reservation not found.")
    _require_owner(caller, reservation)
    return group, reservation


def sessions(caller: Caller, group_id: str) -> Item:
    """Level 1: every participant's cart with per-person and overall totals."""
    group, reservation = _owner_group(caller, group_id)
    return _snapshot(group, reservation)


def owner_session_id(caller: Caller, reservation_id: str) -> Item:
    """Level 2: the owner's own session id (to label their card "My Pre-Order")."""
    reservation = bookings.get_reservation(reservation_id)
    if not reservation:
        raise NotFound(f"Reservation {reservation_id} was not found.")
    _require_owner(caller, reservation)
    group = bookings.group_by_reservation(reservation_id)
    if group is None:
        if (
            mappers.reservation_status(reservation) != ReservationStatus.Reserved
            or dynamo.number(reservation.get("guestCount")) < 2
        ):
            raise NotFound("Group reservation was not found")
        group = create_group(reservation_id)
    return {"guestSessionId": _owner_session(group, reservation)["guestSessionId"]}


def submit_group(caller: Caller, group_id: str, body: dict[str, Any]) -> list[Item]:
    """Freeze the participant review and consolidated order in one conditional transaction."""
    group, reservation = _owner_group(caller, group_id)
    if body.get("reservationId") and body["reservationId"] != reservation["id"]:
        raise BadRequest("The reservation does not belong to this group.")
    _validate_open(group)
    order = bookings.active_order(reservation["id"])
    guests = _guest_sessions(group_id)
    participants = _participants(group, reservation, source_order=order, source_guests=guests)
    submitted = [p for p in participants if p["isSubmitted"]]
    if not submitted:
        raise BadRequest("No submitted guest sessions found to consolidate.")
    merged: dict[str, int] = {}
    snapshots: dict[str, Item] = {}
    for participant in submitted:
        for item in participant["items"]:
            dish_id = item["dish"]["id"]
            merged[dish_id] = merged.get(dish_id, 0) + item["quantity"]
            snapshots.setdefault(dish_id, item["dish"])
    if not merged:
        raise BadRequest("No dishes selected in the submitted guest sessions.")
    available = {d["id"]: d for d in catalog.dishes_for_location(_location_id_for_group(group_id))}
    if any(d not in available or mappers.dish_state(available[d]) != DishState.Available for d in merged):
        raise BadRequest("A selected dish is no longer available at this location. Update the pre-order first.")
    new_order = order is None
    if order is None:
        from services.orders import reservation_time

        _, location = _location_for_reservation(reservation)
        order = {
            "orderId": str(uuid.uuid4()),
            "customerId": reservation["customerId"],
            "reservationId": reservation["id"],
            "reservationAddress": (location or {}).get("address", ""),
            "reservationTime": reservation_time(reservation),
        }
    order["dishes"] = [
        {
            "dishId": d,
            "quantity": q,
            "state": int(OrderItemState.Pending),
            "dishSnapshot": {**available[d], **snapshots[d]},
        }
        for d, q in merged.items()
    ]
    order["status"] = int(OrderStatus.SubmittedByCustomer)
    group["status"] = int(GroupReservationStatus.Submitted)
    # Only carts actually sent are counted in the final review; a draft guest remains
    # visible as not submitted, with no charge and no misleading final total.
    group["submittedParticipants"] = [p if p["isSubmitted"] else {**p, "items": [], "total": 0} for p in participants]
    actions = [
        dynamo.put_action("orders", order, new_key="orderId" if new_order else None),
        dynamo.put_action("group_reservations", group),
    ]
    if new_order:
        reservation.update(activeOrderId=order["orderId"], orderCustomerId=order["customerId"])
        actions.append(dynamo.put_action("reservations", reservation))
    else:
        actions.append(dynamo.check_action("reservations", {"id": reservation["id"]}, reservation))
    actions.extend(
        dynamo.check_action("guest_sessions", {"guestSessionId": guest["guestSessionId"]}, guest) for guest in guests
    )
    dynamo.transaction(actions)
    notifications.notify_waiter(reservation.get("waiterId"), reservation, order, headline="Group pre-order")
    logger.info("Group %s submitted %d dishes into order %s", group_id, len(merged), order["orderId"])
    return [{"dishId": d, "quantity": q} for d, q in merged.items()]


def remove_session(caller: Caller, group_id: str, session_id: str) -> Item:
    """Level 3: drop a guest (and their cart) from the group and return the updated snapshot."""
    group, reservation = _owner_group(caller, group_id)
    session = bookings.get_session(session_id)
    if not session:
        raise NotFound(f"Guest session with id {session_id} not found.")
    if session.get("groupReservationId") != group_id:
        raise BadRequest("Guest session does not belong to this group reservation.")
    if session.get("isOwnerSession"):
        raise BadRequest("Owner session cannot be removed.")
    if group_status(group) != GroupReservationStatus.Open:
        raise group_submitted("Guests cannot be removed after the pre-order was sent to the restaurant.")
    _validate_open(group)
    group["memberIds"] = [s["guestSessionId"] for s in _guest_sessions(group_id) if s["guestSessionId"] != session_id]
    dynamo.transaction(
        [
            dynamo.put_action("group_reservations", group),
            dynamo.delete_action("guest_sessions", {"guestSessionId": session_id}, session),
            dynamo.check_action("reservations", {"id": reservation["id"]}, reservation),
        ]
    )
    return _snapshot(group, reservation)


def session_info(session_id: str) -> Item:
    session = bookings.get_session(session_id)
    if not session:
        raise NotFound("Guest session was not found.")
    entries = session.get("dishes") or []
    dishes = catalog.dishes_by_ids([d["dishId"] for d in entries])
    items = [
        {
            "dish": mappers.dish_response(e.get("dishSnapshot") or dishes[e["dishId"]]),
            "quantity": int(dynamo.number(e.get("quantity"))),
        }
        for e in entries
        if e.get("dishSnapshot") or e.get("dishId") in dishes
    ]
    return {
        "name": session.get("guestName", ""),
        "items": items,
        "total": _total(items),
        "isSubmitted": bool(session.get("isSubmitted")),
    }
