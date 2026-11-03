"""Locations, dishes, tables and waiter-list endpoints."""

from __future__ import annotations

from typing import Any

from core import http
from core.auth import ADMIN, WAITER, require_role
from core.http import Request
from core.validation import as_bool
from services import dishes, locations, tables, waiters


def list_waiters(req: Request) -> dict[str, Any]:
    require_role(req.caller, ADMIN)
    return http.ok(waiters.list_waiters(req.query.get("locationId")))


# --- Locations ---------------------------------------------------------------


def list_locations(req: Request) -> dict[str, Any]:
    return http.ok(locations.list_locations())


def get_location(req: Request) -> dict[str, Any]:
    return http.ok(locations.get_location(req.param("id")))


def create_location(req: Request) -> dict[str, Any]:
    require_role(req.caller, ADMIN)
    return http.ok(locations.create_location(req.json()), status=201)


def update_location(req: Request) -> dict[str, Any]:
    require_role(req.caller, ADMIN)
    return http.ok(locations.update_location(req.param("id"), req.json()))


def delete_location(req: Request) -> dict[str, Any]:
    require_role(req.caller, ADMIN)
    location_id = req.param("id")
    locations.delete_location(location_id, as_bool(req.query.get("force")))
    return http.message(f"Location '{location_id}' deleted successfully.")


def location_dishes(req: Request) -> dict[str, Any]:
    return http.ok(dishes.location_menu(req.param("id")))


def remove_location_dish(req: Request) -> dict[str, Any]:
    require_role(req.caller, ADMIN)
    location_id, dish_id = req.param("locationId"), req.param("dishId")
    locations.remove_dish(location_id, dish_id)
    return http.message(f"Dish '{dish_id}' successfully removed from location '{location_id}'.")


def location_tables(req: Request) -> dict[str, Any]:
    require_role(req.caller, WAITER, ADMIN)
    return http.ok(tables.location_tables(req.param("locationId")))


# --- Dishes ------------------------------------------------------------------


def list_dishes(req: Request) -> dict[str, Any]:
    q = req.query
    return http.ok(dishes.list_dishes(q.get("dishType"), q.get("sortBy"), q.get("name")))


def popular_dishes(req: Request) -> dict[str, Any]:
    return http.ok(dishes.popular_dishes())


def get_dish(req: Request) -> dict[str, Any]:
    return http.ok(dishes.get_dish(req.param("id")))


def create_dish(req: Request) -> dict[str, Any]:
    require_role(req.caller, ADMIN)
    return http.ok(dishes.create_dish(req.json()), status=201)


def update_dish(req: Request) -> dict[str, Any]:
    require_role(req.caller, ADMIN)
    return http.ok(dishes.update_dish(req.param("id"), req.json()))


def delete_dish(req: Request) -> dict[str, Any]:
    require_role(req.caller, ADMIN)
    dish_id = req.param("id")
    dishes.delete_dish(dish_id, as_bool(req.query.get("force")))
    return http.message(f"Dish '{dish_id}' deleted successfully.")


# --- Tables ------------------------------------------------------------------


def create_table(req: Request) -> dict[str, Any]:
    require_role(req.caller, ADMIN)
    return http.ok(tables.create_table(req.json()), status=201)


def update_table(req: Request) -> dict[str, Any]:
    require_role(req.caller, ADMIN)
    return http.ok(tables.update_table(req.param("id"), req.json()))


def delete_table(req: Request) -> dict[str, Any]:
    require_role(req.caller, ADMIN)
    table_id = req.param("id")
    tables.delete_table(table_id)
    return http.message(f"Table '{table_id}' deleted successfully.")


def available_tables(req: Request) -> dict[str, Any]:
    q = req.query
    return http.ok(tables.available_tables(q.get("locationId"), q.get("capacity"), q.get("startTime")))


def time_slots(req: Request) -> dict[str, Any]:
    return http.ok(tables.time_slots(req.param("id"), req.query.get("startTime")))


# --- Waiters -----------------------------------------------------------------


def add_waiter(req: Request) -> dict[str, Any]:
    require_role(req.caller, ADMIN)
    body = req.json()
    waiters.add_waiter(body.get("email"), body.get("locationId"))
    return http.message("Email added successfully")


def remove_waiter(req: Request) -> dict[str, Any]:
    require_role(req.caller, ADMIN)
    waiters.remove_waiter(req.json().get("email"))
    return http.message("Email deleted successfully")


def waiter_location(req: Request) -> dict[str, Any]:
    return http.ok({"locationId": waiters.waiter_location(req.param("userId"))})
