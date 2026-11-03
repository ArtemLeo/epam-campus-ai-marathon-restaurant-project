"""Waiter notifications about new pre-orders."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from core import config, dynamo, timeutils
from core.auth import Caller
from core.errors import Forbidden, NotFound
from repositories import catalog, people

logger = logging.getLogger(__name__)

Item = dict[str, Any]

MAX_UNREAD = 20


def _notification_dishes(entries: list[Item]) -> list[Item]:
    dishes = catalog.dishes_by_ids([e["dishId"] for e in entries])
    result = []
    for entry in entries:
        dish = entry.get("dishSnapshot") or dishes.get(entry["dishId"], {})
        result.append(
            {
                "id": entry["dishId"],
                "name": dish.get("name", "Unknown Dish"),
                "quantity": dynamo.number(entry.get("quantity")),
                **({"translations": dish["translations"]} if "translations" in dish else {}),
            }
        )
    return result


def notify_waiter(waiter_id: str | None, reservation: Item, order: Item, headline: str = "New order") -> None:
    """Tell the reservation's waiter about an order. Failures are logged, never raised."""
    if not waiter_id:
        return
    try:
        table = catalog.get_table(reservation.get("tableId", "")) or {}
        location = catalog.get_location(table.get("locationId", "")) or {}
        dishes = _notification_dishes(order.get("dishes") or [])
        dishes_summary = ", ".join(f"{dish['quantity']}x {dish['name']}" for dish in dishes) or "no dishes"
        start = timeutils.parse_datetime(reservation["startTime"]).astimezone(config.restaurant_timezone())
        message = (
            f"{headline} #{order['orderId']} for Table {dynamo.number(table.get('tableNumber'))} "
            f"({dynamo.number(reservation.get('guestCount'))} guests) at {timeutils.human(start)} ({config.restaurant_timezone().key}). "
            f"Ordered: {dishes_summary}."
        )
        people.save_notification(
            {
                "id": str(uuid.uuid4()),
                "userId": waiter_id,
                "message": message,
                "kind": "GroupOrder" if headline == "Group pre-order" else "NewOrder",
                "tableNumber": dynamo.number(table.get("tableNumber")),
                "guestCount": dynamo.number(reservation.get("guestCount")),
                "startTime": reservation["startTime"],
                "locationAddress": location.get("address", ""),
                "dishes": dishes,
                "orderId": order["orderId"],
                "reservationId": reservation["id"],
                "isRead": False,
                "createdAt": timeutils.iso(timeutils.utcnow()),
            }
        )
    except Exception:
        logger.exception("Failed to create notification for waiter %s", waiter_id)


def _response(notification: Item) -> Item:
    return {
        "id": notification["id"],
        "message": notification.get("message", ""),
        "orderId": notification.get("orderId"),
        "reservationId": notification.get("reservationId"),
        "createdAt": notification.get("createdAt"),
        "isRead": bool(notification.get("isRead")),
        **{
            key: notification[key]
            for key in ("kind", "tableNumber", "guestCount", "startTime", "locationAddress", "dishes")
            if key in notification
        },
    }


def unread(caller: Caller) -> list[Item]:
    items = [n for n in people.notifications_by_user(caller.user_id) if not n.get("isRead")]
    items.sort(key=lambda n: str(n.get("createdAt", "")), reverse=True)
    return [_response(n) for n in items[:MAX_UNREAD]]


def mark_read(caller: Caller, notification_id: str) -> None:
    notification = people.get_notification(notification_id)
    if not notification:
        raise NotFound("Notification not found")
    if str(notification.get("userId", "")).lower() != caller.user_id.lower():
        raise Forbidden("You are not authorized to modify this notification")
    notification["isRead"] = True
    people.save_notification(notification)
