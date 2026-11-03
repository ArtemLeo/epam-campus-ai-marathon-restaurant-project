"""Pre-orders (customer cart before the visit) and orders placed by the waiter during the visit."""

from __future__ import annotations

import datetime as dt
import uuid
from decimal import Decimal
from typing import Any

from core import config, dynamo, timeutils
from core.auth import Caller
from core.enums import DishState, GroupReservationStatus, OrderItemState, OrderStatus, ReservationStatus, stored_enum
from core.errors import BadRequest, Forbidden, NotFound
from core.validation import as_int
from repositories import bookings, catalog
from services import groups, locations, mappers, notifications

Item = dict[str, Any]

EDIT_CUTOFF = dt.timedelta(minutes=30)


def _parse_items(raw: Any) -> list[Item]:
    """Validated ``[{dishId, quantity, state}]``; every dish must exist and be available."""
    if not isinstance(raw, list) or not raw:
        raise BadRequest("Invalid dish IDs in order items or some dishes aren't available.")
    items = []
    for entry in raw:
        if not isinstance(entry, dict) or not isinstance(entry.get("dishId"), str) or not entry["dishId"]:
            raise BadRequest("Invalid dish IDs in order items or some dishes aren't available.")
        items.append({"dishId": entry["dishId"], "quantity": as_int(entry.get("quantity"), "quantity")})
    dishes = catalog.dishes_by_ids([i["dishId"] for i in items])
    for item in items:
        dish = dishes.get(item["dishId"])
        if item["quantity"] <= 0 or not dish or mappers.dish_state(dish) != DishState.Available:
            raise BadRequest("Invalid dish IDs in order items or some dishes aren't available.")
        item["state"] = int(OrderItemState.Pending)
        item["dishSnapshot"] = dict(dish)
    if len({item["dishId"] for item in items}) != len(items):
        raise BadRequest("Each dish must appear once; use quantity for multiple portions.")
    return items


def _ensure_editable(reservation: Item) -> None:
    if mappers.reservation_status(reservation) != ReservationStatus.Reserved:
        raise BadRequest("Pre-orders can only be changed before the visit starts.")
    start = timeutils.parse_datetime(reservation["startTime"])
    if timeutils.utcnow() > start - EDIT_CUTOFF:
        raise BadRequest(
            f"Pre-orders can only be modified up to 30 minutes before the reservation start time ({start:%H:%M})."
        )
    group = bookings.group_by_reservation(reservation["id"])
    if (
        group
        and stored_enum(GroupReservationStatus, group.get("status"), GroupReservationStatus.Open)
        == GroupReservationStatus.Submitted
    ):
        raise BadRequest("The group order has already been sent to the restaurant.")


def _require_reservation(reservation_id: Any) -> Item:
    reservation = (
        bookings.get_reservation(reservation_id) if isinstance(reservation_id, str) and reservation_id else None
    )
    if not reservation:
        raise NotFound("Reservation not found.")
    return reservation


def _require_active_order(reservation_id: str) -> Item:
    order = bookings.active_order(reservation_id)
    if not order:
        raise BadRequest(f"Active pre-order for reservation '{reservation_id}' not found.")
    return order


def response(order: Item, caller: Caller | None = None) -> Item:
    reservation = bookings.get_reservation(order.get("reservationId", ""))
    displayed = dict(order)
    if reservation:
        displayed.update(
            reservationTime=reservation_time(reservation),
            reservationStartTime=reservation["startTime"],
            reservationEndTime=reservation["endTime"],
        )
    result = mappers.order_response(displayed, catalog.dishes_by_ids([d["dishId"] for d in order.get("dishes") or []]))
    reason = "Reservation not found." if not reservation else ""
    group = bookings.group_by_reservation(reservation["id"]) if reservation else None
    result["groupSubmitted"] = bool(group and group.get("submittedParticipants") is not None)
    if reservation:
        if caller and caller.is_waiter:
            if mappers.reservation_status(reservation) != ReservationStatus.InProgress:
                reason = "Orders can be edited by the waiter during the visit."
        else:
            try:
                _ensure_editable(reservation)
            except BadRequest as exc:
                reason = exc.message
    result.update(canEdit=not reason, editDisabledReason=reason or None)
    return result


def reservation_time(reservation: Item) -> str:
    zone = config.restaurant_timezone()
    start = timeutils.parse_datetime(reservation["startTime"]).astimezone(zone)
    end = timeutils.parse_datetime(reservation["endTime"]).astimezone(zone)
    return f"{timeutils.human(start)} - {timeutils.clock(end)} ({zone.key})"


def create(caller: Caller, body: dict[str, Any]) -> Item:
    items = _parse_items(body.get("orderItems"))
    reservation = bookings.get_reservation(body.get("reservationId") or "")
    if not reservation:
        raise BadRequest("Reservation not found.")
    menu_ids = {d["id"] for d in catalog.dishes_for_location(locations.location_by_table(reservation["tableId"])["id"])}
    if any(item["dishId"] not in menu_ids for item in items):
        raise BadRequest("A selected dish is not on this location's menu.")
    status = mappers.reservation_status(reservation)
    if caller.is_waiter:
        if reservation.get("waiterId", "").lower() != caller.user_id.lower():
            raise Forbidden("You are not authorized to modify orders for this reservation.")
        if status != ReservationStatus.InProgress:
            raise BadRequest(
                "Order is allowed for modification only for reservations which have in 'InProgress' status."
            )
        customer_id = reservation.get("customerId") or f"walk-in:{reservation['id']}"
    else:
        if reservation.get("customerId", "").lower() != caller.user_id.lower():
            raise Forbidden("You are not authorized to modify orders for this reservation.")
        if status != ReservationStatus.Reserved:
            raise BadRequest("Pre-order is allowed only for reservations in 'Reserved' status.")
        _ensure_editable(reservation)
        customer_id = caller.user_id
    if bookings.active_order(reservation["id"]):
        raise BadRequest(f"Active order already exists for reservation {reservation['id']}.")
    group = bookings.group_by_reservation(reservation["id"])
    if group:
        groups.pin_dish_prices(group, items)
    order = {
        "orderId": str(uuid.uuid4()),
        "customerId": customer_id,
        "reservationId": reservation["id"],
        "reservationAddress": locations.location_by_table(reservation["tableId"]).get("address", ""),
        "reservationTime": reservation_time(reservation),
        "reservationStartTime": reservation["startTime"],
        "reservationEndTime": reservation["endTime"],
        "dishes": items,
        "status": int(OrderStatus.Created),
    }
    bookings.create_order(order, reservation, group)
    if not caller.is_waiter:
        notifications.notify_waiter(reservation.get("waiterId"), reservation, order)
    return response(order, caller)


def get_for_reservation(caller: Caller, reservation_id: str) -> Item:
    order = bookings.active_order(reservation_id)
    if not order:
        raise NotFound("Order not found.")
    reservation = _require_reservation(reservation_id)
    if not caller.is_admin and caller.user_id not in (reservation.get("waiterId"), reservation.get("customerId")):
        raise Forbidden("Only the assigned waiter or reservation owner can access this order.")
    return response(order, caller)


def list_for_customer(caller: Caller) -> list[Item]:
    orders = [
        o for o in bookings.orders_by_customer(caller.user_id) if bookings.order_status(o) != OrderStatus.Cancelled
    ]
    return [response(order, caller) for order in orders]


def edit(caller: Caller, reservation_id: str, body: dict[str, Any]) -> str:
    raw = body.get("orderItems")
    if not isinstance(raw, list) or not raw:
        raise BadRequest("Invalid request body.")
    reservation = _require_reservation(reservation_id)
    status = mappers.reservation_status(reservation)
    if caller.is_waiter:
        if reservation.get("waiterId", "").lower() != caller.user_id.lower():
            raise Forbidden(
                f"Waiter '{caller.user_id}' is not authorized to edit pre-order for reservation '{reservation_id}'."
            )
        if status != ReservationStatus.InProgress:
            raise BadRequest(
                f"Pre-order can be edited only if reservation status is 'InProgress'. Current status: '{status.name}'."
            )
    else:
        if reservation.get("customerId", "").lower() != caller.user_id.lower():
            raise Forbidden(
                f"User '{caller.user_id}' is not authorized to edit pre-order for reservation '{reservation_id}'."
            )
        if status != ReservationStatus.Reserved:
            raise BadRequest(
                f"Pre-order can be edited only if reservation status is 'Reserved'. Current status: '{status.name}'."
            )
        _ensure_editable(reservation)
    try:
        items = _parse_items(raw)
    except BadRequest as exc:
        raise BadRequest(
            "One or more dishes in the request are invalid, unavailable, or have a quantity of 0."
        ) from exc
    order = _require_active_order(reservation_id)
    if not caller.is_waiter and bookings.order_status(order) != OrderStatus.Created:
        raise BadRequest("Unsubmit the pre-order before changing its dishes.")
    old_items = {d["dishId"]: d for d in order.get("dishes") or []}
    for item in items:
        old = old_items.get(item["dishId"], {})
        if old.get("dishSnapshot"):
            item["dishSnapshot"] = old["dishSnapshot"]
        if old.get("state") == int(OrderItemState.Confirmed):
            item["state"] = old["state"]
    group = bookings.group_by_reservation(reservation_id)
    if group:
        groups.pin_dish_prices(group, items)
    order["dishes"] = items
    bookings.save_order(order, reservation, group)
    return "Order updated successfully." if caller.is_waiter else "Pre-order updated successfully."


def _owned_reservation(caller: Caller, reservation_id: str, action: str) -> Item:
    reservation = _require_reservation(reservation_id)
    if reservation.get("customerId", "").lower() != caller.user_id.lower():
        raise Forbidden(f"You are not authorized to {action} this pre-order.")
    return reservation


def cancel(caller: Caller, reservation_id: str) -> None:
    reservation = _owned_reservation(caller, reservation_id, "cancel")
    _ensure_editable(reservation)
    order = _require_active_order(reservation_id)
    order["status"] = int(OrderStatus.Cancelled)
    bookings.save_order(order, reservation)


def submit(caller: Caller, reservation_id: str) -> None:
    reservation = _owned_reservation(caller, reservation_id, "submit")
    _ensure_editable(reservation)
    order = _require_active_order(reservation_id)
    if bookings.order_status(order) != OrderStatus.Created:
        raise BadRequest("This pre-order is already submitted.")
    available = catalog.dishes_by_ids([d["dishId"] for d in order.get("dishes", [])])
    if any(
        d["dishId"] not in available or mappers.dish_state(available[d["dishId"]]) != DishState.Available
        for d in order.get("dishes", [])
    ):
        raise BadRequest("A selected dish is no longer available. Update the pre-order first.")
    order["status"] = int(OrderStatus.SubmittedByCustomer)
    bookings.save_order(order, reservation)


def unsubmit(caller: Caller, reservation_id: str) -> None:
    reservation = _owned_reservation(caller, reservation_id, "submit")
    order = bookings.active_order(reservation_id)
    if not order:
        raise BadRequest("No pre-order found for the given reservation.")
    _ensure_editable(reservation)
    order["status"] = int(OrderStatus.Created)
    bookings.save_order(order, reservation)


def set_dish_state(caller: Caller, reservation_id: str, dish_id: str, state: OrderItemState) -> None:
    """Waiter confirms/cancels a pre-ordered dish; once nothing is pending (and something is confirmed) the order is Submitted."""
    reservation = _require_reservation(reservation_id)
    if not reservation.get("waiterId"):
        raise BadRequest(f"Reservation '{reservation_id}' has no assigned waiter.")
    if reservation["waiterId"].lower() != caller.user_id.lower():
        raise Forbidden(
            f"Action forbidden: You '{caller.user_id}' are not the assigned waiter "
            f"'{reservation['waiterId']}' for reservation '{reservation_id}'."
        )
    if mappers.reservation_status(reservation) not in (ReservationStatus.Reserved, ReservationStatus.InProgress):
        raise BadRequest("Dishes cannot be changed after the visit is finished.")
    order = bookings.active_order(reservation_id)
    if not order:
        raise BadRequest("Order not found.")
    entry = next((d for d in order.get("dishes") or [] if d.get("dishId") == dish_id), None)
    if entry is None:
        raise NotFound(f"Dish {dish_id} not found in order {order['orderId']}.")
    entry["state"] = int(state)
    states = [stored_enum(OrderItemState, d.get("state"), OrderItemState.Pending) for d in order["dishes"]]
    if OrderItemState.Confirmed in states and OrderItemState.Pending not in states:
        order["status"] = int(OrderStatus.Submitted)
    bookings.save_order(order, reservation)


def revenue(order: Item | None) -> Decimal:
    """Sum of price × quantity for dishes that were not cancelled by the waiter."""
    if not order:
        return Decimal(0)
    entries = [
        d
        for d in order.get("dishes") or []
        if stored_enum(OrderItemState, d.get("state"), OrderItemState.Pending) != OrderItemState.Canceled
    ]
    dishes = catalog.dishes_by_ids([d["dishId"] for d in entries])
    return sum(
        (
            dynamo.decimal((d.get("dishSnapshot") or dishes.get(d["dishId"], {})).get("price", 0))
            * int(d.get("quantity", 0))
            for d in entries
        ),
        Decimal(0),
    )
