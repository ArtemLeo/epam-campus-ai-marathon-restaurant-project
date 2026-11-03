"""Reservations, orders, group reservations and guest sessions tables."""

from __future__ import annotations

import datetime as dt
from typing import Any

from boto3.dynamodb.conditions import Attr

from core import config, dynamo, timeutils
from core.enums import OrderStatus, ReservationStatus, stored_enum
from core.errors import Conflict

Item = dict[str, Any]


# --- Reservations ----------------------------------------------------------


def get_reservation(reservation_id: str) -> Item | None:
    item = dynamo.get_item("reservations", {"id": reservation_id})
    return item if item and not item.get("recordType") else None


def save_reservation(reservation: Item) -> None:
    """Atomically update a booking and the small, versioned schedule of its table/day.

    Schedule rows have no GSI keys, so they never appear in customer/waiter/table lists.
    Empty schedules are deleted; expiresAt lets DynamoDB TTL remove abandoned past days.
    """
    previous = get_reservation(reservation["id"])
    if previous and previous.get("version") != reservation.get("version"):
        raise Conflict("This reservation has changed. Refresh and try again.")
    schedule_ids = {_schedule_id(r) for r in (previous, reservation) if r}
    for attempt in range(5):
        actions = []
        if _is_active(reservation):
            waiter = dynamo.get_item("waiters", {"userId": reservation["waiterId"]})
            if not waiter:
                raise Conflict("The assigned waiter is no longer available. Choose another reservation.")
            actions.append(dynamo.put_action("waiters", waiter, existing_key="userId"))
        # Touch the table version too. Admin deletion/capacity changes use the same
        # version, so a scan followed by deletion cannot race a new booking.
        for table_id in {r["tableId"] for r in (previous, reservation) if r}:
            table = dynamo.get_item("tables", {"id": table_id})
            if (
                _is_active(reservation)
                and table_id == reservation["tableId"]
                and (not table or int(table.get("capacity", 0)) < int(reservation["guestCount"]))
            ):
                raise Conflict("The table was removed or its capacity changed. Choose another table.")
            if table:
                actions.append(dynamo.put_action("tables", table, existing_key="id"))
        now = timeutils.utcnow()
        for schedule_id in sorted(schedule_ids):
            source = next(r for r in (reservation, previous) if r and _schedule_id(r) == schedule_id)
            schedule = dynamo.get_item("reservations", {"id": schedule_id})
            if schedule is None:
                # Import pre-migration reservations with a strongly consistent read once per day.
                legacy = dynamo.scan_all(
                    "reservations", FilterExpression=Attr("tableId").eq(source["tableId"]), ConsistentRead=True
                )
                schedule = {
                    "id": schedule_id,
                    "recordType": "schedule",
                    "slots": {
                        r["id"]: {"start": r["startTime"], "end": r["endTime"]}
                        for r in legacy
                        if _is_active(r) and _schedule_id(r) == schedule_id
                    },
                }
            old_schedule = dict(schedule)
            slots = {
                rid: slot
                for rid, slot in schedule.get("slots", {}).items()
                if rid != reservation["id"] and timeutils.parse_datetime(slot["end"]) + dt.timedelta(minutes=15) > now
            }
            if _is_active(reservation) and _schedule_id(reservation) == schedule_id:
                start, end = (timeutils.parse_datetime(reservation[k]) for k in ("startTime", "endTime"))
                for slot in slots.values():
                    if start < timeutils.parse_datetime(slot["end"]) + dt.timedelta(
                        minutes=15
                    ) and end > timeutils.parse_datetime(slot["start"]) - dt.timedelta(minutes=15):
                        raise Conflict("This table is already booked for that time. Choose another time or table.")
                slots[reservation["id"]] = {"start": reservation["startTime"], "end": reservation["endTime"]}
            if slots:
                schedule["slots"] = slots
                schedule["expiresAt"] = (
                    int(max(timeutils.parse_datetime(s["end"]) for s in slots.values()).timestamp()) + 172800
                )
                actions.append(dynamo.put_action("reservations", schedule))
            elif "version" in old_schedule:
                actions.append(dynamo.delete_action("reservations", {"id": schedule_id}, old_schedule))
        actions.append(dynamo.put_action("reservations", reservation, new_key="id" if previous is None else None))
        try:
            dynamo.transaction(actions)
            reservation["version"] = int(reservation.get("version", 0)) + 1
            return
        except Conflict:
            if attempt == 4:
                raise


def _is_active(reservation: Item) -> bool:
    return stored_enum(ReservationStatus, reservation.get("status"), ReservationStatus.Reserved) in (
        ReservationStatus.Reserved,
        ReservationStatus.InProgress,
    )


def _schedule_id(reservation: Item) -> str:
    day = timeutils.parse_datetime(reservation["startTime"]).astimezone(config.restaurant_timezone()).date()
    return f"schedule:{reservation['tableId']}:{day.isoformat()}"


def all_reservations() -> list[Item]:
    return [r for r in dynamo.scan_all("reservations", ConsistentRead=True) if not r.get("recordType")]


def current_reservations_by_table(table_id: str) -> list[Item]:
    """Strong read for destructive admin actions, where a lagging index is unsafe."""
    return dynamo.scan_all("reservations", FilterExpression=Attr("tableId").eq(table_id), ConsistentRead=True)


def reservations_by_table(table_id: str) -> list[Item]:
    return dynamo.query_index("reservations", "reservations_by_table", "tableId", table_id)


def reservations_by_customer(customer_id: str) -> list[Item]:
    return dynamo.query_index("reservations", "reservations_by_customer", "customerId", customer_id)


def reservations_by_waiter(waiter_id: str) -> list[Item]:
    return dynamo.query_index("reservations", "reservations_by_waiter", "waiterId", waiter_id)


# --- Orders ----------------------------------------------------------------


def order_status(order: Item) -> OrderStatus:
    return stored_enum(OrderStatus, order.get("status"), OrderStatus.Created)


def active_order(reservation_id: str) -> Item | None:
    """The reservation's order that is not cancelled (there is at most one)."""
    reservation = get_reservation(reservation_id)
    if reservation and reservation.get("activeOrderId"):
        order = get_order(
            reservation["activeOrderId"], reservation.get("orderCustomerId") or reservation.get("customerId", "")
        )
        return order if order and order_status(order) != OrderStatus.Cancelled else None
    orders = dynamo.query_index("orders", "orders_by_reservation", "reservationId", reservation_id)
    return next((o for o in orders if order_status(o) != OrderStatus.Cancelled), None)


def orders_by_customer(customer_id: str) -> list[Item]:
    return dynamo.query_index("orders", "orders_by_customer", "customerId", customer_id)


def get_order(order_id: str, customer_id: str) -> Item | None:
    return dynamo.get_item("orders", {"orderId": order_id, "customerId": customer_id})


def save_order(order: Item, reservation: Item | None = None, group: Item | None = None) -> None:
    actions = [dynamo.put_action("orders", order)]
    if reservation:
        actions.append(dynamo.put_action("reservations", reservation))
    if group:
        actions.append(dynamo.put_action("group_reservations", group))
    dynamo.transaction(actions)
    order["version"] = int(order.get("version", 0)) + 1
    if reservation:
        reservation["version"] = int(reservation.get("version", 0)) + 1


def create_order(order: Item, reservation: Item, group: Item | None = None) -> None:
    reservation.update(activeOrderId=order["orderId"], orderCustomerId=order["customerId"])
    actions = [dynamo.put_action("reservations", reservation), dynamo.put_action("orders", order, new_key="orderId")]
    if group:
        actions.append(dynamo.put_action("group_reservations", group))
    dynamo.transaction(actions)
    reservation["version"] = int(reservation.get("version", 0)) + 1
    order["version"] = 1


def all_orders() -> list[Item]:
    return dynamo.scan_all("orders")


# --- Group reservations ----------------------------------------------------


def get_group(group_id: str) -> Item | None:
    return dynamo.get_item("group_reservations", {"groupReservationId": group_id})


def group_by_reservation(reservation_id: str) -> Item | None:
    direct = get_group(f"group:{reservation_id}")
    if direct:
        return direct
    items = dynamo.query_index("group_reservations", "groups_by_reservation", "reservationId", reservation_id)
    return items[0] if items else None


def group_by_token(token: str) -> Item | None:
    items = dynamo.query_index("group_reservations", "groups_by_token", "reservationToken", token)
    return items[0] if items else None


def save_group(group: Item) -> None:
    dynamo.save_versioned("group_reservations", group)


# --- Guest sessions --------------------------------------------------------


def get_session(session_id: str) -> Item | None:
    return dynamo.get_item("guest_sessions", {"guestSessionId": session_id})


def sessions_by_group(group_id: str) -> list[Item]:
    sessions = dynamo.scan_all(
        "guest_sessions", FilterExpression=Attr("groupReservationId").eq(group_id), ConsistentRead=True
    )
    return sorted(sessions, key=lambda s: str(s.get("createdAt", "")))


def session_by_token_hash(token_hash: str) -> Item | None:
    items = dynamo.query_index("guest_sessions", "sessions_by_token_hash", "guestSessionTokenHash", token_hash)
    return items[0] if items else None


def save_session(session: Item) -> None:
    dynamo.save_versioned("guest_sessions", session)


def delete_session(session_id: str) -> None:
    dynamo.delete_item("guest_sessions", {"guestSessionId": session_id})
