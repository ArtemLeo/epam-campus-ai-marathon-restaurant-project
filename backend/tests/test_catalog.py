"""Locations, dishes, tables, time slots and the waiter list."""

from __future__ import annotations

import datetime as dt
import unittest

from helpers import AwsTestCase, at, iso


class CatalogTest(AwsTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.r = self.seed_restaurant()
        self.admin, self.location = self.r["admin"], self.r["location"]
        self.caesar, self.tom_yum, self.cheesecake = self.r["dishes"]

    def test_locations_report_live_capacity_and_rating(self) -> None:
        locations = self.ok("GET", "/locations")
        self.assertEqual(1, len(locations))
        self.assertEqual(
            {"id", "address", "description", "totalCapacity", "averageOccupancy", "imageUrl", "rating"},
            set(locations[0]),
        )
        self.assertEqual(
            (2, 0, "60%"), (locations[0]["totalCapacity"], locations[0]["rating"], locations[0]["averageOccupancy"])
        )
        self.error(404, "GET", "/locations/unknown")

    def test_location_management_is_admin_only(self) -> None:
        body = {"address": "Abashidze 9", "description": "Cozy", "averageOccupancy": "45"}
        self.error(403, "POST", "/locations", body, user=self.r["customer"])
        created = self.ok("POST", "/locations", body, user=self.admin)
        self.assertEqual("45%", created["averageOccupancy"])
        self.error(400, "POST", "/locations", {**body, "averageOccupancy": "120"}, user=self.admin)
        updated = self.ok("PUT", f"/locations/{created['id']}", {**body, "address": "Abashidze 10"}, user=self.admin)
        self.assertEqual("Abashidze 10", updated["address"])
        self.ok("DELETE", f"/locations/{created['id']}", user=self.admin)

    def test_location_delete_requires_force_when_in_use(self) -> None:
        body = self.error(400, "DELETE", f"/locations/{self.location['id']}", user=self.admin)
        self.assertIn("?force=true", body["error"])
        self.ok("DELETE", f"/locations/{self.location['id']}", user=self.admin, query={"force": "true"})
        self.assertEqual([], self.ok("GET", "/locations"))
        groups = self.cognito.admin_list_groups_for_user(UserPoolId=self.pool_id, Username="waiter@mail.com")["Groups"]
        self.assertNotIn("Waiter", [g["GroupName"] for g in groups])

    def test_dish_listing_filters_and_sorting(self) -> None:
        dishes = self.ok("GET", "/dishes", query={"sortBy": "PriceDescending"})
        self.assertEqual(["Tom Yum", "Caesar Salad", "Cheesecake"], [d["name"] for d in dishes])
        self.assertEqual(["Tom Yum"], [d["name"] for d in self.ok("GET", "/dishes", query={"dishType": "MainCourse"})])
        self.assertEqual(["Cheesecake"], [d["name"] for d in self.ok("GET", "/dishes", query={"name": "cake"})])
        dish = self.ok("GET", f"/dishes/{self.tom_yum['id']}")
        self.assertEqual(("Main course", "Available", 220), (dish["dishType"], dish["state"], dish["price"]))
        self.assertEqual(95.5, self.cheesecake["price"])

    def test_popular_dishes_are_ordered_by_orders(self) -> None:
        customer = self.r["customer"]
        reservation = self.book(customer, self.r["tables"][0]["id"])
        self.ok(
            "POST",
            "/orders",
            {"reservationId": reservation["id"], "orderItems": [{"dishId": self.cheesecake["id"], "quantity": 1}]},
            user=customer,
        )
        self.assertEqual("Cheesecake", self.ok("GET", "/dishes/popular")[0]["name"])

    def test_location_menu_and_removing_a_dish(self) -> None:
        menu = self.ok("GET", f"/locations/{self.location['id']}/dishes")
        self.assertEqual(3, len(menu))
        self.error(
            403, "DELETE", f"/locations/{self.location['id']}/dishes/{self.caesar['id']}", user=self.r["customer"]
        )
        self.ok("DELETE", f"/locations/{self.location['id']}/dishes/{self.caesar['id']}", user=self.admin)
        self.assertEqual(2, len(self.ok("GET", f"/locations/{self.location['id']}/dishes")))
        self.error(400, "DELETE", f"/locations/{self.location['id']}/dishes/{self.caesar['id']}", user=self.admin)

    def test_dish_management(self) -> None:
        body = {
            **{
                k: self.tom_yum[k]
                for k in ("description", "weight", "calories", "proteins", "fats", "carbohydrates", "vitamins")
            }
        }
        body.update(name="Borscht", price="150.25", dishType=1, state="OnStop", locationIds=["missing"])
        self.error(404, "POST", "/dishes", body, user=self.admin)
        body["locationIds"] = [self.location["id"]]
        created = self.ok("POST", "/dishes", body, user=self.admin)
        self.assertEqual(("On stop", 150.25), (created["state"], created["price"]))
        updated = self.ok("PUT", f"/dishes/{created['id']}", {**body, "state": "Available"}, user=self.admin)
        self.assertEqual("Available", updated["state"])
        self.error(400, "DELETE", f"/dishes/{created['id']}", user=self.admin)
        self.ok("DELETE", f"/dishes/{created['id']}", user=self.admin, query={"force": "true"})
        self.error(404, "GET", f"/dishes/{created['id']}")

    def test_dish_translations_round_trip_preserve_replace_and_clear(self) -> None:
        body = {**self.caesar, "dishType": "Appetizer", "locationIds": [self.location["id"]]}
        translations = {"uk": {"name": " Салат Цезар ", "description": "Свіжий салат"}, "fr": {"name": "César"}}
        created = self.ok("POST", "/dishes", {**body, "translations": translations}, user=self.admin)
        expected = {**translations, "uk": {"name": "Салат Цезар", "description": "Свіжий салат"}}
        path = f"/dishes/{created['id']}"
        self.assertEqual(expected, created["translations"])
        self.assertEqual(expected, self.ok("GET", path)["translations"])
        self.assertEqual(expected, self.ok("PUT", path, body, user=self.admin)["translations"])
        for listing in ("/dishes", "/dishes/popular", f"/locations/{self.location['id']}/dishes"):
            found = next(dish for dish in self.ok("GET", listing) if dish["id"] == created["id"])
            self.assertEqual(expected, found["translations"])
        replacement = {"de": {"name": "Salat", "description": " "}}
        updated = self.ok("PUT", path, {**body, "translations": replacement}, user=self.admin)
        self.assertEqual({"de": {"name": "Salat"}}, updated["translations"])
        cleared = self.ok("PUT", path, {**body, "translations": {}}, user=self.admin)
        self.assertEqual({}, cleared["translations"])
        self.assertEqual(self.caesar["name"], cleared["name"])

    def test_location_translations_preserve_default_description_and_optional_metadata(self) -> None:
        body = {"address": "New Avenue 1", "description": "Cozy restaurant", "averageOccupancy": "0"}
        translations = {"uk": {"description": "Затишний ресторан"}, "es": {"description": "Restaurante acogedor"}}
        created = self.ok("POST", "/locations", {**body, "translations": translations}, user=self.admin)
        path = f"/locations/{created['id']}"
        self.assertEqual(translations, self.ok("GET", path)["translations"])
        updated = self.ok("PUT", path, {**body, "description": "Updated original"}, user=self.admin)
        self.assertEqual(translations, updated["translations"])
        self.assertEqual("Updated original", updated["description"])
        self.assertEqual({}, self.ok("PUT", path, {**body, "translations": {}}, user=self.admin)["translations"])

    def test_invalid_catalog_translations_are_rejected_without_overwriting_content(self) -> None:
        body = {**self.caesar, "dishType": "Appetizer"}
        invalid = [
            None,
            [],
            "text",
            {"it": {"name": "Insalata"}},
            {"uk": []},
            {"fr": {"price": "5"}},
            {"en": {"name": 123}},
            {"de": {"description": None}},
            {"uk": {"name": "a" * 201}},
            {"es": {"description": "a" * 2001}},
        ]
        for translations in invalid:
            with self.subTest(translations=translations):
                self.error(
                    400, "PUT", f"/dishes/{self.caesar['id']}", {**body, "translations": translations}, user=self.admin
                )
        unchanged = self.ok("GET", f"/dishes/{self.caesar['id']}")
        self.assertEqual(self.caesar["name"], unchanged["name"])
        self.assertNotIn("translations", unchanged)
        self.error(
            400,
            "PUT",
            f"/locations/{self.location['id']}",
            {
                **self.location,
                "translations": {"uk": {"name": "Адреса"}},
            },
            user=self.admin,
        )

    def test_tables_management(self) -> None:
        self.error(
            409,
            "POST",
            "/tables",
            {"locationId": self.location["id"], "capacity": 4, "tableNumber": 1},
            user=self.admin,
        )
        self.error(
            400,
            "POST",
            "/tables",
            {"locationId": self.location["id"], "capacity": 0, "tableNumber": 9},
            user=self.admin,
        )
        tables = self.ok("GET", f"/locations/{self.location['id']}/tables/all", user=self.r["waiter"])
        self.assertEqual([1, 2], [t["tableNumber"] for t in tables])
        self.error(403, "GET", f"/locations/{self.location['id']}/tables/all", user=self.r["customer"])
        table = self.ok("PUT", f"/tables/{tables[1]['id']}", {"capacity": 6, "tableNumber": 3}, user=self.admin)
        self.assertEqual((6, 3), (table["capacity"], table["tableNumber"]))

        self.book(self.r["customer"], tables[0]["id"])
        self.error(400, "DELETE", f"/tables/{tables[0]['id']}", user=self.admin)
        self.ok("DELETE", f"/tables/{tables[1]['id']}", user=self.admin)

    def test_time_slots_skip_booked_time(self) -> None:
        table_id = self.r["tables"][0]["id"]
        free = self.ok("GET", f"/tables/{table_id}/available-time-slots", query={"startTime": iso(at(days=3, hour=8))})
        self.assertEqual(7, len(free))
        self.assertTrue(free[0]["start"].endswith("T10:00:00.000Z"))
        self.assertTrue(free[-1]["end"].endswith("T22:00:00.000Z"))

        self.book(self.r["customer"], table_id, start=at(days=3, hour=11, minute=45))
        slots = self.ok("GET", f"/tables/{table_id}/available-time-slots", query={"startTime": iso(at(days=3, hour=8))})
        starts = [s["start"][11:16] for s in slots]
        self.assertNotIn("11:45", starts)
        self.assertEqual("13:30", starts[1])
        self.error(400, "GET", f"/tables/{table_id}/available-time-slots", query={"startTime": "nope"})

    def test_available_tables(self) -> None:
        start = iso(at(days=3, hour=12))
        tables = self.ok(
            "GET", "/available-tables", query={"locationId": self.location["id"], "capacity": "3", "startTime": start}
        )
        self.assertEqual([1], [t["tableNumber"] for t in tables])
        past = iso(dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=1))
        self.assertEqual(
            "Cannot query timeslots in the past.",
            self.error(400, "GET", "/available-tables", query={"startTime": past})["error"],
        )

    def test_waiter_list(self) -> None:
        waiter_id = self.r["waiter"]["id"]
        self.assertEqual({"locationId": self.location["id"]}, self.ok("GET", f"/waiters/{waiter_id}/location"))
        self.error(
            409, "POST", "/waiters", {"email": "waiter@mail.com", "locationId": self.location["id"]}, user=self.admin
        )
        self.error(
            404, "POST", "/waiters", {"email": "nobody@mail.com", "locationId": self.location["id"]}, user=self.admin
        )
        self.error(
            403,
            "POST",
            "/waiters",
            {"email": "owner@mail.com", "locationId": self.location["id"]},
            user=self.r["customer"],
        )
        self.ok("DELETE", "/waiters", {"email": "waiter@mail.com"}, user=self.admin)
        self.error(404, "GET", f"/waiters/{waiter_id}/location")
        self.error(404, "DELETE", "/waiters", {"email": "waiter@mail.com"}, user=self.admin)


if __name__ == "__main__":
    unittest.main()
