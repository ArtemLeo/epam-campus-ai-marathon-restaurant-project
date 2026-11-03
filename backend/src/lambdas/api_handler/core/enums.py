"""Domain enums. Values match the original .NET enums, which are stored in DynamoDB as numbers."""

from __future__ import annotations

from decimal import Decimal
from enum import IntEnum
from typing import Any, TypeVar

from core.errors import BadRequest

E = TypeVar("E", bound=IntEnum)


class DishType(IntEnum):
    Appetizer = 0
    MainCourse = 1
    Dessert = 2


class DishState(IntEnum):
    OnStop = 0
    Available = 1
    OutOfStock = 2


class ReservationStatus(IntEnum):
    Reserved = 0
    Cancelled = 1
    InProgress = 2
    Completed = 3


class OrderStatus(IntEnum):
    Created = 0
    Submitted = 1
    Cancelled = 2
    SubmittedByCustomer = 3


class OrderItemState(IntEnum):
    Pending = 0
    Confirmed = 1
    Canceled = 2


class GroupReservationStatus(IntEnum):
    Open = 0
    Submitted = 1
    Closed = 2


class FeedbackType(IntEnum):
    Service = 0
    CuisineExperience = 1


class SortingOrder(IntEnum):
    TopRatedFirst = 0
    LowRatedFirst = 1
    NewestFirst = 2
    OldestFirst = 3


class ReportType(IntEnum):
    Service = 0
    Sales = 1


DISH_TYPE_LABELS = {DishType.Appetizer: "Appetizer", DishType.MainCourse: "Main course", DishType.Dessert: "Dessert"}
DISH_STATE_LABELS = {
    DishState.OnStop: "On stop",
    DishState.Available: "Available",
    DishState.OutOfStock: "Out of stock",
}


def parse_enum(enum_type: type[E], value: Any, field: str) -> E:
    """Enum member from its number or (case-insensitive) name; labels like "Main course" are accepted too."""
    if isinstance(value, bool):
        raise BadRequest(f"Invalid {field}: {value}")
    if isinstance(value, (int, float, Decimal)) or (isinstance(value, str) and value.strip().lstrip("-").isdigit()):
        try:
            return enum_type(int(value))
        except ValueError:
            pass
    elif isinstance(value, str):
        normalized = value.replace(" ", "").replace("_", "").lower()
        for member in enum_type:
            if member.name.lower() == normalized:
                return member
    raise BadRequest(f"Invalid {field}: {value}")


def stored_enum(enum_type: type[E], value: Any, default: E) -> E:
    """Lenient read of a stored value (number or name); falls back to ``default``."""
    try:
        return parse_enum(enum_type, value, enum_type.__name__)
    except BadRequest:
        return default
