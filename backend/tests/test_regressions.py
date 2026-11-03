"""Business regressions reproduced during the audit, including concurrent requests."""

from __future__ import annotations

import datetime as dt
import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from unittest import mock

from helpers import AwsTestCase, at, iso
from test_feedback_reports import reports_handler
from test_group_preorder import GroupPreOrderTestCase

from core import dynamo, timeutils
from repositories import bookings, catalog
from services import groups, reports, reservations


class BusinessRegressionTest(AwsTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.r = self.seed_restaurant()
        self.customer, self.waiter, self.admin = self.r["customer"], self.r["waiter"], self.r["admin"]
        self.table_id = self.r["tables"][0]["id"]
        self.dish_id = self.r["dishes"][0]["id"]

    def complete(self, rid: str) -> None:
        self.ok("PATCH", f"/reservations/{rid}/status", {"newStatus": "InProgress"}, user=self.waiter)
        self.ok("PATCH", f"/reservations/{rid}/status", {"newStatus": "Completed"}, user=self.waiter)

    def order(self, rid: str) -> dict:
        return self.ok(
            "POST",
            "/orders",
            {"reservationId": rid, "orderItems": [{"dishId": self.dish_id, "quantity": 2}]},
            user=self.customer,
        )

    def test_parallel_bookings_cannot_double_book_a_table(self) -> None:
        barrier = threading.Barrier(2)
        original = reservations._ensure_no_overlap

        def checked(*args, **kwargs):
            original(*args, **kwargs)
            barrier.wait(timeout=10)

        body = {"tableId": self.table_id, "guestCount": 2, "startTime": iso(at(2, 12)), "endTime": iso(at(2, 13, 30))}
        with mock.patch.object(reservations, "_ensure_no_overlap", side_effect=checked), ThreadPoolExecutor(2) as pool:
            result = list(pool.map(lambda _: self.call("POST", "/reservations", body, user=self.customer)[0], range(2)))
        self.assertEqual([201, 409], sorted(result))
        self.assertEqual(1, len(bookings.current_reservations_by_table(self.table_id)))

    def test_edit_and_cancel_release_old_slot_and_internal_rows_are_hidden(self) -> None:
        reservation = self.book(self.customer, self.table_id, start=at(2, 12))
        self.ok(
            "PUT",
            "/reservations",
            {
                "reservationId": reservation["id"],
                "guestCount": 2,
                "startTime": iso(at(2, 15)),
                "endTime": iso(at(2, 16, 30)),
            },
            user=self.customer,
        )
        self.book(self.customer, self.table_id, start=at(2, 12))
        self.ok("DELETE", "/reservations", {"id": reservation["id"]}, user=self.customer)
        self.book(self.customer, self.table_id, start=at(2, 15))
        self.assertEqual(3, len(self.ok("GET", "/reservations", user=self.customer)))
        self.assertEqual(3, len(bookings.all_reservations()))
        self.error(404, "GET", f"/reservations/schedule:{self.table_id}:{at(2).date()}", user=self.admin)

    def test_advertised_time_slots_respect_booking_buffer(self) -> None:
        self.book(self.customer, self.table_id, start=at(2, 11, 30))
        slots = self.ok("GET", f"/tables/{self.table_id}/available-time-slots", query={"startTime": iso(at(2, 10))})
        self.assertNotIn("10:00", [slot["start"][11:16] for slot in slots])
        first = slots[0]
        self.ok(
            "POST",
            "/reservations",
            {"tableId": self.table_id, "guestCount": 2, "startTime": first["start"], "endTime": first["end"]},
            user=self.customer,
        )

    def test_restaurant_timezone_and_working_hours(self) -> None:
        with mock.patch.dict(os.environ, {"RESTAURANT_TIMEZONE": "Asia/Tbilisi"}):
            slots = self.ok("GET", f"/tables/{self.table_id}/available-time-slots", query={"startTime": iso(at(2, 5))})
            self.assertTrue(slots[0]["start"].endswith("T06:00:00.000Z"))
            self.error(
                400,
                "POST",
                "/reservations",
                {"tableId": self.table_id, "guestCount": 2, "startTime": iso(at(2, 5)), "endTime": iso(at(2, 6, 30))},
                user=self.customer,
            )
            self.book(self.customer, self.table_id, start=at(2, 6))

    def test_today_slots_do_not_offer_past_or_immediate_bookings(self) -> None:
        with mock.patch.object(timeutils, "utcnow", return_value=at(2, 12, 7)):
            slots = self.ok("GET", f"/tables/{self.table_id}/available-time-slots", query={"startTime": iso(at(2, 0))})
            self.assertTrue(slots[0]["start"].endswith("T12:30:00.000Z"))
        with mock.patch.object(timeutils, "utcnow", return_value=at(2, 21)):
            self.assertEqual(
                [], self.ok("GET", f"/tables/{self.table_id}/available-time-slots", query={"startTime": iso(at(2, 0))})
            )

    def test_order_snapshot_survives_price_change_and_dish_deletion(self) -> None:
        reservation = self.book(self.customer, self.table_id)
        self.order(reservation["id"])
        self.ok("POST", f"/orders/{reservation['id']}/submit", user=self.customer)
        dish = catalog.get_dish(self.dish_id)
        dish["price"] = 999
        catalog.save_dish(dish)
        self.ok("DELETE", f"/dishes/{self.dish_id}", user=self.admin, query={"force": "true"})
        items = self.ok("GET", f"/orders/{reservation['id']}", user=self.customer)["orderItems"]
        self.assertEqual(
            ("Caesar Salad", 180, 2), (items[0]["dish"]["name"], items[0]["dish"]["price"], items[0]["quantity"])
        )
        self.complete(reservation["id"])
        self.assertEqual(360, bookings.get_reservation(reservation["id"])["reportEvent"]["Revenue"])

    def test_unassigned_waiter_and_terminal_order_mutations_are_rejected(self) -> None:
        reservation = self.book(self.customer, self.table_id)
        rid = reservation["id"]
        self.order(rid)
        stranger = self.create_user("other-waiter@mail.com", groups=("Waiter",))
        self.error(403, "GET", f"/orders/{rid}", user=stranger)
        self.complete(rid)
        locked = self.ok("GET", f"/orders/{rid}", user=self.customer)
        self.assertFalse(locked["canEdit"])
        self.assertTrue(locked["editDisabledReason"])
        for method, path in [
            ("DELETE", f"/orders/{rid}"),
            ("POST", f"/orders/{rid}/submit"),
            ("POST", f"/orders/{rid}/unsubmit"),
        ]:
            self.error(400, method, path, user=self.customer)
        self.error(400, "PATCH", f"/reservations/{rid}/order/confirmations/{self.dish_id}", user=self.waiter)
        self.error(400, "PATCH", f"/reservations/{rid}/table", {"tableId": self.table_id}, user=self.waiter)

    def test_active_visit_blocks_table_location_waiter_deletion_and_capacity_reduction(self) -> None:
        reservation = self.book(self.customer, self.table_id, guests=4)
        self.ok("PATCH", f"/reservations/{reservation['id']}/status", {"newStatus": "InProgress"}, user=self.waiter)
        self.error(400, "DELETE", f"/tables/{self.table_id}", user=self.admin)
        self.error(400, "DELETE", f"/locations/{self.r['location']['id']}", user=self.admin, query={"force": "true"})
        self.error(409, "PUT", f"/tables/{self.table_id}", {"tableNumber": 1, "capacity": 2}, user=self.admin)
        self.error(409, "DELETE", "/waiters", {"email": self.waiter["email"]}, user=self.admin)
        self.error(403, "DELETE", f"/tables/{self.table_id}", user=self.waiter)

    def test_table_delete_cannot_race_a_new_booking(self) -> None:
        ready, proceed = threading.Event(), threading.Event()
        transaction = dynamo.transaction

        def paused(actions):
            if any(action.get("Delete", {}).get("TableName") == "Tables" for action in actions):
                ready.set()
                self.assertTrue(proceed.wait(10))
            return transaction(actions)

        with mock.patch.object(dynamo, "transaction", side_effect=paused), ThreadPoolExecutor(1) as pool:
            deletion = pool.submit(self.call, "DELETE", f"/tables/{self.table_id}", user=self.admin)
            self.assertTrue(ready.wait(10))
            self.book(self.customer, self.table_id)
            proceed.set()
            self.assertEqual(409, deletion.result()[0])
        self.assertIsNotNone(catalog.get_table(self.table_id))

    def test_booking_cannot_recreate_a_deleted_legacy_table(self) -> None:
        self.table("Tables").update_item(
            Key={"id": self.table_id}, UpdateExpression="REMOVE #v", ExpressionAttributeNames={"#v": "version"}
        )
        original = dynamo.transaction

        def delete_before_write(actions):
            if any(action.get("Put", {}).get("TableName") == "Tables" for action in actions):
                catalog.delete_table(self.table_id)
            return original(actions)

        body = {"tableId": self.table_id, "guestCount": 2, "startTime": iso(at(2, 12)), "endTime": iso(at(2, 13, 30))}
        with mock.patch.object(dynamo, "transaction", side_effect=delete_before_write):
            self.error(409, "POST", "/reservations", body, user=self.customer)
        self.assertIsNone(catalog.get_table(self.table_id))
        self.assertEqual([], bookings.current_reservations_by_table(self.table_id))

    def test_feedback_requires_completed_visit_owner_or_unexpired_qr(self) -> None:
        rid = self.book(self.customer, self.table_id)["id"]
        body = {"reservationId": rid, "rating": 5, "type": 0}
        self.error(400, "POST", "/feedback", body, user=self.customer)
        self.error(400, "GET", f"/reservations/{rid}/feedback-token", user=self.waiter)
        self.complete(rid)
        self.error(403, "POST", "/feedback", body)
        stranger = self.create_user("stranger@mail.com")
        self.error(403, "POST", "/feedback", body, user=stranger)
        self.error(403, "GET", f"/reservations/{rid}/feedback-token", user=stranger)
        token = self.ok("GET", f"/reservations/{rid}/feedback-token", user=self.waiter)["token"]
        with mock.patch.object(
            timeutils, "utcnow", return_value=dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=8)
        ):
            self.error(403, "POST", "/feedback", {**body, "token": token})
        self.ok("POST", "/feedback", {**body, "token": token})
        self.error(409, "POST", "/feedback", body, user=self.customer)

    def test_failed_report_delivery_is_durable_and_replayed(self) -> None:
        rid = self.book(self.customer, self.table_id)["id"]
        with mock.patch.object(reports, "deliver_report", side_effect=RuntimeError("queue unavailable")):
            self.complete(rid)
        pending = bookings.get_reservation(rid)
        self.assertEqual(3, pending["status"])
        self.assertIn("reportEvent", pending)
        self.assertNotIn("reportDeliveredRevision", pending)
        reports.replay_pending_reports()
        stored = bookings.get_reservation(rid)
        self.assertEqual(stored["reportRevision"], stored["reportDeliveredRevision"])
        self.assertEqual(1, len(self.sqs.receive_message(QueueUrl=self.queue_url).get("Messages", [])))

    def test_report_revisions_update_ratings_without_double_counting(self) -> None:
        table = self.table("Reports")
        event = {
            "ReservationId": "visit",
            "Revision": 1,
            "WaiterId": "waiter",
            "LocationId": "location",
            "ReservationStart": iso(at(2, 12)),
            "ReservationEnd": iso(at(2, 13, 30)),
            "Revenue": 20,
            "ServiceRating": 0,
            "CuisineRating": 0,
        }
        for message in [
            event,
            {**event, "Revision": 2, "ServiceRating": 5},
            event,
            {**event, "Revision": 3, "ServiceRating": 2},
        ]:
            reports_handler.process(json.dumps(message), table)
        aggregate = table.scan()["Items"][0]
        self.assertEqual(
            (1, 20, 2), (aggregate["ordersProcessed"], aggregate["totalRevenue"], aggregate["averageServiceRating"])
        )

    def test_report_concurrent_events_are_not_lost(self) -> None:
        table = self.table("Reports")
        original_get = table.get_item
        barrier = threading.Barrier(2)
        calls = threading.local()

        def simultaneous_read(**kwargs):
            result = original_get(**kwargs)
            if "#" in kwargs["Key"]["date"] and not getattr(calls, "read", False):
                calls.read = True
                barrier.wait(10)
            return result

        event = {
            "Revision": 1,
            "WaiterId": "waiter",
            "LocationId": "location",
            "ReservationStart": iso(at(2, 12)),
            "ReservationEnd": iso(at(2, 13, 30)),
            "Revenue": 20,
        }
        with mock.patch.object(table, "get_item", side_effect=simultaneous_read), ThreadPoolExecutor(2) as pool:
            list(
                pool.map(
                    lambda rid: reports_handler.process(json.dumps({**event, "ReservationId": rid}), table),
                    ("one", "two"),
                )
            )
        aggregate = table.scan()["Items"][0]
        self.assertEqual((2, 40), (aggregate["ordersProcessed"], aggregate["totalRevenue"]))

    def test_unicode_profile_and_complete_menu_membership_replacement(self) -> None:
        self.ok("PUT", "/me", {"firstName": "Олена", "lastName": "Ковальчук"}, user=self.customer)
        self.assertEqual("Олена", self.ok("GET", "/me", user=self.customer)["firstName"])
        body = self.ok("GET", f"/dishes/{self.dish_id}")
        self.assertEqual([self.r["location"]["id"]], body["locationIds"])
        self.ok("PUT", f"/dishes/{self.dish_id}", {**body, "locationIds": []}, user=self.admin)
        self.assertNotIn(
            self.dish_id, [d["id"] for d in self.ok("GET", f"/locations/{self.r['location']['id']}/dishes")]
        )
        self.assertEqual([], self.ok("GET", f"/dishes/{self.dish_id}")["locationIds"])
        self.assertEqual(self.waiter["email"], self.ok("GET", "/waiters", user=self.admin)[0]["email"])
        self.error(403, "GET", "/waiters", user=self.customer)


class GroupRegressionTest(GroupPreOrderTestCase):
    def test_catalog_translations_reach_guests_and_remain_in_historical_order_snapshots(self) -> None:
        dish = catalog.get_dish(self.caesar)
        translated = {"uk": {"name": "Салат Цезар", "description": "Свіжий салат"}}
        dish["translations"] = translated
        catalog.save_dish(dish)
        guest_id, headers = self.join("Olena")
        menu = self.ok("GET", f"/guest/sessions/{guest_id}/menu", headers=headers)
        menu_dish = next(item for category in menu["dishes"].values() for item in category if item["id"] == self.caesar)
        self.assertEqual(translated, menu_dish["translations"])
        self.ok("POST", f"/guest/sessions/{guest_id}/dishes", {"dishId": self.caesar, "quantity": 1}, headers=headers)
        self.ok("POST", f"/guest/sessions/{guest_id}/submit", headers=headers)
        self.owner_preorder(self.caesar)
        notification = self.ok("GET", "/notifications", user=self.r["waiter"])[0]
        self.assertEqual("NewOrder", notification["kind"])
        self.assertEqual(translated, notification["dishes"][0]["translations"])
        self.assertEqual("Caesar Salad", notification["dishes"][0]["name"])
        self.assertEqual(1, notification["dishes"][0]["quantity"])
        self.assertEqual(4, notification["guestCount"])
        self.assertEqual(1, notification["tableNumber"])
        self.assertEqual(self.reservation["startTime"], notification["startTime"])
        self.assertEqual(self.r["location"]["address"], notification["locationAddress"])
        dish["translations"] = {"uk": {"name": "Змінена назва"}}
        catalog.save_dish(dish)
        session = self.ok("GET", f"/guest/sessions/{guest_id}", headers=headers)
        self.assertEqual(translated, session["items"][0]["dish"]["translations"])
        participants = self.ok("GET", f"/guest/groups/{self.group_id}/sessions", user=self.owner)["participants"]
        self.assertTrue(all(person["items"][0]["dish"]["translations"] == translated for person in participants))
        self.ok(
            "POST",
            f"/group-reservations/{self.group_id}/submit",
            {"reservationId": self.reservation["id"]},
            user=self.owner,
        )
        order = self.ok("GET", f"/orders/{self.reservation['id']}", user=self.owner)
        self.assertEqual(translated, order["orderItems"][0]["dish"]["translations"])
        self.assertEqual(2, order["orderItems"][0]["quantity"])
        group_notification = next(
            item for item in self.ok("GET", "/notifications", user=self.r["waiter"]) if item["kind"] == "GroupOrder"
        )
        self.assertEqual(translated, group_notification["dishes"][0]["translations"])
        self.assertEqual(2, group_notification["dishes"][0]["quantity"])

    def test_group_uses_the_owners_original_price_after_menu_price_changes(self) -> None:
        self.owner_preorder(self.caesar)
        dish = catalog.get_dish(self.caesar)
        dish["price"] = 999
        catalog.save_dish(dish)
        session_id, headers = self.join("Andrii")
        menu = self.ok("GET", f"/guest/sessions/{session_id}/menu", headers=headers)
        offered = next(d for category in menu["dishes"].values() for d in category if d["id"] == self.caesar)
        self.assertEqual(180, offered["price"])
        self.ok("POST", f"/guest/sessions/{session_id}/dishes", {"dishId": self.caesar, "quantity": 2}, headers=headers)
        self.ok("POST", f"/guest/sessions/{session_id}/submit", headers=headers)
        self.ok("POST", f"/group-reservations/{self.group_id}/submit", user=self.owner)
        review = self.ok("GET", f"/guest/groups/{self.group_id}/sessions", user=self.owner)
        order = self.ok("GET", f"/orders/{self.reservation['id']}", user=self.owner)
        self.assertEqual(540, review["total"])
        self.assertEqual(540, sum(item["dish"]["price"] * item["quantity"] for item in order["orderItems"]))

    def test_group_uses_the_first_guests_price_when_owner_orders_later(self) -> None:
        self.guest_cart("Andrii", self.caesar, 2, submit=True)
        dish = catalog.get_dish(self.caesar)
        dish["price"] = 999
        catalog.save_dish(dish)
        self.owner_preorder(self.caesar)
        self.ok("POST", f"/group-reservations/{self.group_id}/submit", user=self.owner)
        review = self.ok("GET", f"/guest/groups/{self.group_id}/sessions", user=self.owner)
        order = self.ok("GET", f"/orders/{self.reservation['id']}", user=self.owner)
        self.assertEqual((540, [180, 360]), (review["total"], [p["total"] for p in review["participants"]]))
        self.assertEqual(540, sum(item["dish"]["price"] * item["quantity"] for item in order["orderItems"]))

    def test_group_total_is_not_double_counted_after_send(self) -> None:
        self.owner_preorder(self.caesar)
        self.guest_cart("Andrii", self.caesar, 2, submit=True)
        self.ok("POST", f"/group-reservations/{self.group_id}/submit", user=self.owner)
        data = self.ok("GET", f"/guest/groups/{self.group_id}/sessions", user=self.owner)
        self.assertEqual((540, [180, 360]), (data["total"], [p["total"] for p in data["participants"]]))
        order = self.ok("GET", f"/orders/{self.reservation['id']}", user=self.owner)
        self.assertTrue(order["groupSubmitted"])
        self.assertFalse(order["canEdit"])
        self.error(400, "DELETE", f"/orders/{self.reservation['id']}", user=self.owner)

    def test_group_deadline_matches_individual_preorder_deadline(self) -> None:
        self.owner_preorder(self.caesar)
        session_id, headers = self.join("Andrii")
        with mock.patch.object(
            timeutils,
            "utcnow",
            return_value=timeutils.parse_datetime(self.reservation["startTime"]) - dt.timedelta(minutes=20),
        ):
            self.error(400, "POST", f"/group-reservations/{self.group_id}/submit", user=self.owner)
            self.error(
                409,
                "POST",
                f"/guest/sessions/{session_id}/dishes",
                {"dishId": self.caesar, "quantity": 1},
                headers=headers,
            )
            self.error(400, "POST", "/guest/sessions", {"groupReservationId": self.group_id, "guestName": "Late"})

    def test_parallel_joins_cannot_exceed_capacity(self) -> None:
        self.guest_cart("First", self.caesar, 1, submit=False)
        self.guest_cart("Second", self.caesar, 1, submit=False)
        barrier = threading.Barrier(2)
        original = groups._joined_guests

        def counted(group_id):
            count = original(group_id)
            barrier.wait(10)
            return count

        with mock.patch.object(groups, "_joined_guests", side_effect=counted), ThreadPoolExecutor(2) as pool:
            result = list(
                pool.map(
                    lambda name: self.call(
                        "POST", "/guest/sessions", {"groupReservationId": self.group_id, "guestName": name}
                    )[0],
                    ("Third", "Fourth"),
                )
            )
        self.assertEqual([200, 409], sorted(result))
        self.assertEqual(3, len([s for s in bookings.sessions_by_group(self.group_id) if not s.get("isOwnerSession")]))

    def test_parallel_group_submissions_do_not_multiply_quantities(self) -> None:
        self.owner_preorder(self.caesar)
        self.guest_cart("Andrii", self.caesar, 2, submit=True)
        self.ok("GET", f"/guest/groups/{self.group_id}/sessions", user=self.owner)
        barrier = threading.Barrier(2)
        original = groups._participants

        def reviewed(*args, **kwargs):
            result = original(*args, **kwargs)
            barrier.wait(10)
            return result

        with mock.patch.object(groups, "_participants", side_effect=reviewed), ThreadPoolExecutor(2) as pool:
            result = list(
                pool.map(
                    lambda _: self.call("POST", f"/group-reservations/{self.group_id}/submit", user=self.owner)[0],
                    range(2),
                )
            )
        self.assertEqual([200, 409], sorted(result))
        order = self.ok("GET", f"/orders/{self.reservation['id']}", user=self.owner)
        self.assertEqual(3, order["orderItems"][0]["quantity"])
