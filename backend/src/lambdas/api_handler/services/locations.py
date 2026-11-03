"""Restaurant locations: details enriched with live capacity and rating, menu membership."""

from __future__ import annotations

import uuid
from typing import Any

from core import dynamo
from core.errors import BadRequest, NotFound
from core.validation import as_decimal, as_int, catalog_translations, parse_occupancy, required_str
from repositories import catalog, people
from services import images, mappers, waiters
from services import tables as table_service

Item = dict[str, Any]


def capacity(location_id: str) -> int:
    """Number of tables at the location (the original reports this as ``totalCapacity``)."""
    return len(catalog.tables_by_location(location_id))


def rating(location_id: str) -> float:
    feedback = people.feedback_by_location(location_id)
    if not feedback:
        return 0
    return round(sum(dynamo.number(f.get("rating")) for f in feedback) / len(feedback), 2)


def _response(location: Item) -> Item:
    return mappers.location_response(location, capacity=capacity(location["id"]), rating=rating(location["id"]))


def list_locations() -> list[Item]:
    return [_response(location) for location in catalog.all_locations()]


def require_location(location_id: str) -> Item:
    location = catalog.get_location(location_id)
    if not location:
        raise NotFound(f"Location with id '{location_id}' was not found.")
    return location


def get_location(location_id: str) -> Item:
    return _response(require_location(location_id))


def location_by_table(table_id: str) -> Item:
    table = catalog.get_table(table_id)
    if not table:
        raise BadRequest(f"Table with ID {table_id} not found.")
    location = catalog.get_location(table["locationId"])
    if not location:
        raise BadRequest(f"Location with ID {table['locationId']} not found.")
    return location


def _apply(location: Item, body: dict[str, Any]) -> None:
    if "translations" in body:
        location["translations"] = catalog_translations(body["translations"], fields=("description",))
    location["address"] = required_str(body, "address")
    location["description"] = required_str(body, "description")
    location["totalCapacity"] = as_int(body.get("totalCapacity"), "totalCapacity", default=0)
    location["averageOccupancy"] = parse_occupancy(body.get("averageOccupancy"))
    if body.get("imageBase64"):
        location["imageUrl"] = images.upload_public_image(
            body["imageBase64"], images.LOCATIONS_FOLDER, f"location_{location['id']}"
        )


def create_location(body: dict[str, Any]) -> Item:
    location: Item = {
        "id": str(uuid.uuid4()),
        "rating": as_decimal(body.get("rating", 0), "rating"),
        "specialtyDishIds": [],
    }
    _apply(location, body)
    catalog.save_location(location)
    return mappers.location_response(location)


def update_location(location_id: str, body: dict[str, Any]) -> Item:
    location = require_location(location_id)
    _apply(location, body)
    catalog.save_location(location)
    return mappers.location_response(location)


def delete_location(location_id: str, force: bool) -> None:
    require_location(location_id)
    tables = catalog.tables_by_location(location_id)
    location_waiters = people.waiters_by_location(location_id)
    if (tables or location_waiters) and not force:
        raise BadRequest(
            f"Cannot delete location '{location_id}' because it has active tables or assigned waiters. "
            "Append '?force=true' to the URL to delete them automatically."
        )
    if any(table_service._active_reservations(table["id"]) for table in tables):
        raise BadRequest("Move or cancel all active reservations before deleting this location.")
    for table in tables:
        table_service.delete_table(table["id"])
    for waiter in location_waiters:
        waiters.remove_waiter_by_id(waiter["userId"])
    catalog.delete_location(location_id)


def remove_dish(location_id: str, dish_id: str) -> None:
    location = catalog.get_location(location_id)
    if not location:
        raise BadRequest(f"Location '{location_id}' not found.")
    dish_ids = list(location.get("specialtyDishIds") or [])
    if dish_id not in dish_ids:
        raise BadRequest(f"Dish '{dish_id}' is not currently on the menu for this location.")
    location["specialtyDishIds"] = [d for d in dish_ids if d != dish_id]
    catalog.save_location(location)
