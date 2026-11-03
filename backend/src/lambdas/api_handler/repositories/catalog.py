"""Locations, tables and dishes tables."""

from __future__ import annotations

from typing import Any

from boto3.dynamodb.conditions import Attr

from core import dynamo

Item = dict[str, Any]


# --- Locations -------------------------------------------------------------


def get_location(location_id: str) -> Item | None:
    return dynamo.get_item("locations", {"id": location_id})


def all_locations() -> list[Item]:
    return dynamo.scan_all("locations")


def save_location(location: Item) -> None:
    dynamo.put_item("locations", location)


def delete_location(location_id: str) -> None:
    dynamo.delete_item("locations", {"id": location_id})


# --- Tables ----------------------------------------------------------------


def get_table(table_id: str) -> Item | None:
    return dynamo.get_item("tables", {"id": table_id})


def all_tables() -> list[Item]:
    return dynamo.scan_all("tables")


def tables_by_location(location_id: str) -> list[Item]:
    return dynamo.query_index("tables", "tables_by_location", "locationId", location_id)


def save_table(table: Item) -> None:
    dynamo.save_versioned("tables", table)


def delete_table(table_id: str) -> None:
    dynamo.delete_item("tables", {"id": table_id})


# --- Dishes ----------------------------------------------------------------


def get_dish(dish_id: str) -> Item | None:
    return dynamo.get_item("dishes", {"id": dish_id})


def dishes_by_ids(dish_ids: list[str]) -> dict[str, Item]:
    return dynamo.batch_get("dishes", "id", dish_ids)


def all_dishes() -> list[Item]:
    return dynamo.scan_all("dishes")


def save_dish(dish: Item) -> None:
    dynamo.put_item("dishes", dish)


def delete_dish(dish_id: str) -> None:
    dynamo.delete_item("dishes", {"id": dish_id})


def dishes_for_location(location_id: str) -> list[Item]:
    """Only dishes explicitly assigned to this location; an empty menu stays empty."""
    found: dict[str, Item] = {}
    location = get_location(location_id) if location_id else None
    if location and location.get("specialtyDishIds"):
        found.update(dishes_by_ids(list(location["specialtyDishIds"])))
    if location_id:
        for dish in dynamo.scan_all("dishes", FilterExpression=Attr("locationId").eq(location_id)):
            found[dish["id"]] = dish
    return list(found.values())
