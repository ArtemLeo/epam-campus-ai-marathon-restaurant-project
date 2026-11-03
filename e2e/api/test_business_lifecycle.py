"""Acceptance checks across real HTTP, storage and the local/cloud adapter."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
import pytest

from api.client import RestaurantApi
from api.flow import cleanup, create_reservation

pytestmark = pytest.mark.api


def test_catalog_has_usable_tables_and_demo_menu(api_url: str, admin_token: str) -> None:
    with RestaurantApi(api_url, admin_token) as api:
        locations = [loc for loc in api.get_locations() if not loc["address"].startswith("AQA")]
        assert locations, "Seed a demo restaurant before running acceptance tests."
        for location in locations:
            tables = api._request("GET", f"/locations/{location['id']}/tables/all")
            assert tables and all(table["capacity"] > 0 for table in tables)
            menu = api._request("GET", f"/locations/{location['id']}/dishes")
            assert menu, f"No menu at {location['address']}"
            assert all(dish["imageUrl"] and dish["calories"] for dish in menu)
        dishes = [dish for dish in api.get_dishes() if not dish["name"].startswith("AQA")]
        assert {dish["dishType"] for dish in dishes} >= {"Appetizer", "Main course", "Dessert"}


def test_booking_rejects_duplicate_and_other_customer_order_access(
    api_url: str, admin_token: str, customer_token: str, test_restaurant: dict
) -> None:
    with RestaurantApi(api_url, customer_token) as owner, RestaurantApi(api_url, admin_token) as admin:
        reservation = create_reservation(owner, 2)
        rid = reservation["id"]
        try:
            duplicate = owner.raw(
                "POST",
                "/reservations",
                json={key: reservation[key] for key in ("tableId", "startTime", "endTime", "guestCount")},
            )
            assert duplicate.status_code in (400, 409)
            owner._request(
                "POST",
                "/orders",
                json={"reservationId": rid, "orderItems": [{"dishId": test_restaurant["dish_ids"][0], "quantity": 1}]},
            )
            # An ordinary second customer cannot read or modify the order either.
            import os

            with RestaurantApi(api_url) as other:
                other.token = other.signin(os.environ["GUEST_EMAIL"], os.environ["GUEST_PASSWORD"])["idToken"]
                assert other.raw("GET", f"/orders/{rid}").status_code == 403
                assert other.raw("DELETE", f"/orders/{rid}").status_code == 403
            # Active reservations protect their table from deletion.
            assert admin.raw("DELETE", f"/tables/{reservation['tableId']}").status_code in (400, 409)
        finally:
            cleanup(owner, rid)


def test_submitted_order_preserves_price_and_item_after_menu_changes(
    api_url: str, admin_token: str, customer_token: str, test_restaurant: dict
) -> None:
    with RestaurantApi(api_url, admin_token) as admin, RestaurantApi(api_url, customer_token) as owner:
        body = {
            "name": "AQA historical price",
            "description": "Snapshot regression",
            "dishType": 1,
            "price": 12,
            "weight": "200 g",
            "state": 1,
            "calories": "200 kcal",
            "proteins": "10 g",
            "fats": "10 g",
            "carbohydrates": "20 g",
            "vitamins": "A",
            "locationIds": [test_restaurant["location"]["id"]],
        }
        dish = admin._request("POST", "/dishes", json=body)
        reservation = create_reservation(owner, 2)
        rid = reservation["id"]
        try:
            owner._request(
                "POST", "/orders", json={"reservationId": rid, "orderItems": [{"dishId": dish["id"], "quantity": 2}]}
            )
            owner._request("POST", f"/orders/{rid}/submit")
            admin._request("PUT", f"/dishes/{dish['id']}", json={**body, "name": "AQA renamed dish", "price": 99})
            order = owner.get_order(rid)
            assert order["orderItems"][0]["dish"]["price"] == 12
            assert order["orderItems"][0]["dish"]["name"] == body["name"]
            admin._request("DELETE", f"/dishes/{dish['id']}", params={"force": "true"})
            assert owner.get_order(rid)["orderItems"][0]["dish"]["price"] == 12
        finally:
            cleanup(owner, rid)
            admin.raw("DELETE", f"/dishes/{dish['id']}", params={"force": "true"})


def test_completed_visit_feedback_and_downloadable_reports(
    api_url: str, admin_token: str, customer_token: str, waiter_token: str, test_restaurant: dict
) -> None:
    with RestaurantApi(api_url, customer_token) as owner, RestaurantApi(api_url, waiter_token) as waiter:
        reservation = create_reservation(owner, 2)
        rid = reservation["id"]
        dish_id = test_restaurant["dish_ids"][0]
        try:
            early = owner.raw(
                "POST", "/feedback", json={"reservationId": rid, "type": 0, "rating": 5, "comment": "Too early"}
            )
            assert early.status_code in (400, 409)
            owner._request(
                "POST", "/orders", json={"reservationId": rid, "orderItems": [{"dishId": dish_id, "quantity": 2}]}
            )
            owner._request("POST", f"/orders/{rid}/submit")
            waiter._request("PATCH", f"/reservations/{rid}/order/confirmations/{dish_id}", json={})
            waiter._request("PATCH", f"/reservations/{rid}/status", json={"newStatus": "InProgress"})
            waiter._request("PATCH", f"/reservations/{rid}/status", json={"newStatus": "Completed"})
            assert owner.raw("DELETE", f"/orders/{rid}").status_code in (400, 409)
            owner._request(
                "POST", "/feedback", json={"reservationId": rid, "type": 0, "rating": 5, "comment": "Great service"}
            )
            token = waiter._request("GET", f"/reservations/{rid}/feedback-token")["token"]
            with RestaurantApi(api_url) as guest:
                denied = guest.raw("POST", "/feedback", json={"reservationId": rid, "type": 1, "rating": 4})
                assert denied.status_code in (401, 403)
                guest._request(
                    "POST",
                    "/feedback",
                    json={"reservationId": rid, "token": token, "type": 1, "rating": 4, "comment": "Tasty meal"},
                )
            # A real response must be a file, not a JSON string containing CSV/base64.
            now = datetime.now(UTC)
            params = {
                "type": 1,
                "locationId": test_restaurant["location"]["id"],
                "startDate": (now - timedelta(days=1)).date().isoformat(),
                "endDate": (now + timedelta(days=90)).date().isoformat(),
            }
            headers = {"Authorization": f"Bearer {admin_token}"}
            for file_format, mime, signature in [
                ("csv", "text/csv", None),
                ("pdf", "application/pdf", b"%PDF"),
                ("excel", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", b"PK"),
            ]:
                response = httpx.get(
                    f"{api_url}/reports/download", params={**params, "format": file_format}, headers=headers, timeout=30
                )
                assert response.status_code == 200, response.text
                assert response.headers["content-type"].startswith(mime)
                assert "attachment" in response.headers["content-disposition"]
                if signature:
                    assert response.content.startswith(signature)
                else:
                    assert "\\n" not in response.text and "\n" in response.text
        finally:
            cleanup(owner, rid)
