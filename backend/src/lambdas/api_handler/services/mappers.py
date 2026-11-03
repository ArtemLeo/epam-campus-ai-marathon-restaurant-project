"""DynamoDB items → API response bodies (field names follow the original API contract)."""

from __future__ import annotations

from typing import Any

from core import config, dynamo
from core.enums import (
    DISH_STATE_LABELS,
    DISH_TYPE_LABELS,
    DishState,
    DishType,
    OrderItemState,
    OrderStatus,
    ReservationStatus,
    stored_enum,
)
from core.validation import sanitize_occupancy

Item = dict[str, Any]


def dish_type(dish: Item) -> DishType:
    return stored_enum(DishType, dish.get("dishType"), DishType.Appetizer)


def dish_state(dish: Item) -> DishState:
    return stored_enum(DishState, dish.get("state"), DishState.Available)


def dish_response(dish: Item) -> Item:
    return {
        "id": dish["id"],
        "name": dish.get("name", ""),
        "description": dish.get("description", ""),
        "dishType": DISH_TYPE_LABELS[dish_type(dish)],
        "price": dynamo.number(dish.get("price")),
        "weight": dish.get("weight", ""),
        "calories": dish.get("calories", ""),
        "proteins": dish.get("proteins", ""),
        "fats": dish.get("fats", ""),
        "carbohydrates": dish.get("carbohydrates", ""),
        "vitamins": dish.get("vitamins", ""),
        "imageUrl": dish.get("imageUrl") or None,
        "state": DISH_STATE_LABELS[dish_state(dish)],
        **({"translations": dish["translations"]} if "translations" in dish else {}),
    }


def location_response(location: Item, *, capacity: int | None = None, rating: float | None = None) -> Item:
    return {
        "id": location["id"],
        "address": location.get("address", ""),
        "description": location.get("description", ""),
        "totalCapacity": dynamo.number(location.get("totalCapacity")) if capacity is None else capacity,
        "averageOccupancy": sanitize_occupancy(location.get("averageOccupancy")),
        "imageUrl": location.get("imageUrl") or None,
        "rating": dynamo.number(location.get("rating")) if rating is None else rating,
        **({"translations": location["translations"]} if "translations" in location else {}),
    }


def table_response(table: Item) -> Item:
    return {
        "id": table["id"],
        "locationId": table.get("locationId", ""),
        "capacity": dynamo.number(table.get("capacity")),
        "tableNumber": dynamo.number(table.get("tableNumber")),
    }


def reservation_status(reservation: Item) -> ReservationStatus:
    return stored_enum(ReservationStatus, reservation.get("status"), ReservationStatus.Reserved)


def reservation_response(
    reservation: Item,
    address: str,
    order: Item | None = None,
    *,
    guest_invite_available: bool = False,
) -> Item:
    order_status = stored_enum(OrderStatus, order.get("status"), OrderStatus.Created) if order else None
    return {
        "id": reservation["id"],
        "tableId": reservation.get("tableId", ""),
        "locationId": reservation.get("locationId", ""),
        "startTime": reservation.get("startTime"),
        "endTime": reservation.get("endTime"),
        "guestCount": dynamo.number(reservation.get("guestCount")),
        "status": int(reservation_status(reservation)),
        "customerId": reservation.get("customerId") or None,
        "waiterId": reservation.get("waiterId", ""),
        "locationAddress": address,
        "restaurantName": config.RESTAURANT_NAME,
        "hasSubmittedPreOrder": order_status == OrderStatus.Submitted,
        "guestInviteLinkAvailable": guest_invite_available,
    }


def order_items(entries: list[Item], dishes: dict[str, Item]) -> list[Item]:
    """An order owns its price/name snapshot; later menu changes cannot rewrite a sale."""
    return [
        {
            "dish": dish_response(entry.get("dishSnapshot") or dishes[entry["dishId"]]),
            "quantity": dynamo.number(entry.get("quantity")),
            "state": int(stored_enum(OrderItemState, entry.get("state"), OrderItemState.Pending)),
        }
        for entry in entries or []
        if entry.get("dishSnapshot") or entry.get("dishId") in dishes
    ]


def order_response(order: Item, dishes: dict[str, Item]) -> Item:
    return {
        "orderId": order["orderId"],
        "reservationId": order.get("reservationId", ""),
        "reservationAddress": order.get("reservationAddress", ""),
        "reservationTime": order.get("reservationTime", ""),
        "reservationStartTime": order.get("reservationStartTime"),
        "reservationEndTime": order.get("reservationEndTime"),
        "orderItems": order_items(order.get("dishes") or [], dishes),
        "status": int(stored_enum(OrderStatus, order.get("status"), OrderStatus.Created)),
    }
