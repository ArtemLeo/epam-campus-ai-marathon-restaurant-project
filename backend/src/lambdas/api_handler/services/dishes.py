"""Menu dishes: browsing with filters/sorting, popularity and admin management."""

from __future__ import annotations

import uuid
from collections import Counter
from typing import Any

from core.enums import DishState, DishType, parse_enum
from core.errors import BadRequest, NotFound
from core.validation import as_decimal, catalog_translations
from repositories import bookings, catalog
from services import images, mappers

Item = dict[str, Any]

_TEXT_FIELDS = ("name", "description", "weight", "calories", "proteins", "fats", "carbohydrates", "vitamins")


def popularity() -> Counter[str]:
    """How many orders contain each dish."""
    counts: Counter[str] = Counter()
    for order in bookings.all_orders():
        counts.update(entry.get("dishId") for entry in order.get("dishes") or [] if entry.get("dishId"))
    return counts


def list_dishes(dish_type: str | None = None, sort_by: str | None = None, name: str | None = None) -> list[Item]:
    dishes = catalog.all_dishes()
    if dish_type:
        try:
            wanted = parse_enum(DishType, dish_type, "dishType")
        except BadRequest:
            wanted = None
        if wanted is not None:
            dishes = [d for d in dishes if mappers.dish_type(d) == wanted]
    if name:
        dishes = [d for d in dishes if name.lower() in str(d.get("name", "")).lower()]
    if sort_by in ("PriceAscending", "PriceDescending"):
        dishes.sort(key=lambda d: d.get("price", 0), reverse=sort_by == "PriceDescending")
    elif sort_by in ("PopularityAscending", "PopularityDescending"):
        counts = popularity()
        dishes.sort(key=lambda d: counts[d["id"]], reverse=sort_by == "PopularityDescending")
    memberships = {loc["id"]: set(loc.get("specialtyDishIds") or []) for loc in catalog.all_locations()}
    return [
        {**mappers.dish_response(d), "locationIds": [lid for lid, ids in memberships.items() if d["id"] in ids]}
        for d in dishes
    ]


def popular_dishes() -> list[Item]:
    return list_dishes(sort_by="PopularityDescending")


def require_dish(dish_id: str) -> Item:
    dish = catalog.get_dish(dish_id)
    if not dish:
        raise NotFound(f"Dish with id '{dish_id}' was not found.")
    return dish


def get_dish(dish_id: str) -> Item:
    return {
        **mappers.dish_response(require_dish(dish_id)),
        "locationIds": [loc["id"] for loc in catalog.all_locations() if dish_id in (loc.get("specialtyDishIds") or [])],
    }


def location_menu(location_id: str) -> list[Item]:
    location = catalog.get_location(location_id)
    if not location:
        raise NotFound(f"Location with id '{location_id}' was not found.")
    dishes = catalog.dishes_by_ids(list(location.get("specialtyDishIds") or []))
    return [mappers.dish_response(d) for d in dishes.values()]


def _location_ids(body: dict[str, Any], required: bool) -> list[str]:
    value = body.get("locationIds")
    if value is None and not required:
        return []
    if not isinstance(value, list) or not all(isinstance(i, str) for i in value):
        raise BadRequest("'locationIds' must be a list of location ids.")
    return value


def _apply(dish: Item, body: dict[str, Any]) -> None:
    if "translations" in body:
        dish["translations"] = catalog_translations(body["translations"], fields=("name", "description"))
    for field in _TEXT_FIELDS:
        value = body.get(field)
        if not isinstance(value, str) or (field == "name" and not value.strip()):
            raise BadRequest(f"'{field}' is required.")
        dish[field] = value
    dish["dishType"] = int(parse_enum(DishType, body.get("dishType", 0), "dishType"))
    dish["state"] = int(parse_enum(DishState, body.get("state", 0), "state"))
    price = as_decimal(body.get("price"), "price")
    if price < 0:
        raise BadRequest("'price' must not be negative.")
    dish["price"] = price
    if body.get("imageBase64"):
        dish["imageUrl"] = images.upload_public_image(body["imageBase64"], images.DISHES_FOLDER, f"dish_{dish['id']}")


def _add_to_menus(dish_id: str, location_ids: list[str]) -> None:
    for location_id in location_ids:
        location = catalog.get_location(location_id)
        if location is None:
            continue
        menu = list(location.get("specialtyDishIds") or [])
        if dish_id not in menu:
            location["specialtyDishIds"] = [*menu, dish_id]
            catalog.save_location(location)


def create_dish(body: dict[str, Any]) -> Item:
    location_ids = _location_ids(body, required=True)
    missing = [i for i in location_ids if not catalog.get_location(i)]
    if missing:
        raise NotFound(f"Location with id: {missing[0]} was not found")
    dish: Item = {"id": str(uuid.uuid4()), "locationIds": location_ids}
    _apply(dish, body)
    catalog.save_dish(dish)
    _add_to_menus(dish["id"], location_ids)
    return get_dish(dish["id"])


def update_dish(dish_id: str, body: dict[str, Any]) -> Item:
    dish = require_dish(dish_id)
    location_ids = _location_ids(body, required=False) if "locationIds" in body else None
    if location_ids is not None:
        for location_id in location_ids:
            if not catalog.get_location(location_id):
                raise NotFound(f"Location with id: {location_id} was not found")
        dish["locationIds"] = location_ids
    _apply(dish, body)
    catalog.save_dish(dish)
    if location_ids is not None:
        for location in catalog.all_locations():
            menu = list(location.get("specialtyDishIds") or [])
            updated = [d for d in menu if d != dish_id]
            if location["id"] in location_ids:
                updated.append(dish_id)
            if set(updated) != set(menu):
                location["specialtyDishIds"] = updated
                catalog.save_location(location)
    return get_dish(dish_id)


def delete_dish(dish_id: str, force: bool) -> None:
    require_dish(dish_id)
    linked = [loc for loc in catalog.all_locations() if dish_id in (loc.get("specialtyDishIds") or [])]
    if linked and not force:
        raise BadRequest(
            f"Cannot delete dish '{dish_id}' because it is currently on the menu of {len(linked)} location(s). "
            "To delete this dish and automatically remove it from all location menus, "
            "append '?force=true' to your request URL."
        )
    for location in linked:
        location["specialtyDishIds"] = [d for d in location["specialtyDishIds"] if d != dish_id]
        catalog.save_location(location)
    catalog.delete_dish(dish_id)
