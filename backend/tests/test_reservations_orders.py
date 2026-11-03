"""Reservations, pre-orders/orders and waiter notifications."""

from __future__ import annotations

import datetime as dt
import json
import unittest
from unittest import mock

from helpers import AwsTestCase, at, iso


def now_plus(minutes: int) -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).replace(second=0, microsecond=0) + dt.timedelta(minutes=minutes)


class ReservationsTest(AwsTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.r = self.seed_restaurant()
        self.customer, self.waiter = self.r["customer"], self.r["waiter"]
        self.table4, self.table2 = self.r["tables"]

    def test_customer_booking_gets_least_busy_waiter_and_group(self) -> None:
        reservation = self.book(self.customer, self.table4["id"], guests=4)
        self.assertEqual(
            (0, 4, self.waiter["id"], "Rustaveli Avenue 48", "Green & Tasty", True, False),
            (
                reservation["status"],
                reservation["guestCount"],
                reservation["waiterId"],
                reservation["locationAddress"],
                reservation["restaurantName"],
                reservation["guestInviteLinkAvailable"],
                reservation["hasSubmittedPreOrder"],
            ),
        )
        waiter_item = self.table("Waiters").get_item(Key={"userId": self.waiter["id"]})["Item"]
        self.assertEqual([reservation["id"]], waiter_item["reservations"])

    def test_booking_validation(self) -> None:
        start = at(days=2, hour=12)

        def attempt(table_id: str, begin: dt.datetime, end: dt.datetime, guests: int = 2):
            body = {"tableId": table_id, "startTime": iso(begin), "endTime": iso(end), "guestCount": guests}
            return self.call("POST", "/reservations", body, user=self.customer)

        self.assertEqual(400, attempt(self.table2["id"], start, start + dt.timedelta(minutes=90), guests=3)[0])
        self.assertEqual(400, attempt(self.table4["id"], now_plus(5), now_plus(95))[0])
        self.assertEqual(400, attempt(self.table4["id"], start, start)[0])
        self.assertEqual(400, attempt("unknown", start, start + dt.timedelta(minutes=90))[0])
        self.book(self.customer, self.table4["id"], start=start)
        status, body = attempt(self.table4["id"], start + dt.timedelta(minutes=60), start + dt.timedelta(minutes=150))
        self.assertEqual(400, status)
        self.assertIn("overlaps", body["error"])
        self.assertEqual(
            201, attempt(self.table4["id"], start + dt.timedelta(minutes=105), start + dt.timedelta(minutes=195))[0]
        )

    def test_lists_and_access(self) -> None:
        reservation = self.book(self.customer, self.table4["id"])
        stranger = self.create_user("stranger@mail.com", "Sam", "Stranger")
        self.assertEqual([reservation["id"]], [r["id"] for r in self.ok("GET", "/reservations", user=self.customer)])
        self.assertEqual([reservation["id"]], [r["id"] for r in self.ok("GET", "/reservations", user=self.waiter)])
        self.assertEqual([], self.ok("GET", "/reservations", user=stranger))
        self.ok("GET", f"/reservations/{reservation['id']}", user=self.waiter)
        self.error(403, "GET", f"/reservations/{reservation['id']}", user=stranger)
        self.error(404, "GET", "/reservations/unknown", user=self.customer)

    def test_cancel_closes_group_cancels_order_and_frees_waiter(self) -> None:
        reservation = self.book(self.customer, self.table4["id"])
        dish = self.r["dishes"][0]["id"]
        self.ok(
            "POST",
            "/orders",
            {"reservationId": reservation["id"], "orderItems": [{"dishId": dish, "quantity": 1}]},
            user=self.customer,
        )
        stranger = self.create_user("stranger@mail.com", "Sam", "Stranger")
        self.error(403, "DELETE", "/reservations", {"id": reservation["id"]}, user=stranger)

        self.ok("DELETE", "/reservations", {"id": reservation["id"]}, user=self.customer)
        self.assertEqual(1, self.ok("GET", f"/reservations/{reservation['id']}", user=self.customer)["status"])
        self.error(404, "GET", f"/orders/{reservation['id']}", user=self.customer)
        self.assertEqual([], self.table("Waiters").get_item(Key={"userId": self.waiter["id"]})["Item"]["reservations"])
        self.error(400, "DELETE", "/reservations", {"id": reservation["id"]}, user=self.customer)

    def test_cancel_too_late(self) -> None:
        now = at(days=1, hour=11)
        with mock.patch("core.timeutils.utcnow", return_value=now):
            soon = self.book(self.customer, self.table4["id"], start=now + dt.timedelta(minutes=20))
            body = self.error(400, "DELETE", "/reservations", {"id": soon["id"]}, user=self.customer)
        self.assertIn("Too late to cancel", body["error"])

    def test_edit(self) -> None:
        reservation = self.book(self.customer, self.table4["id"])
        start = at(days=2, hour=15)
        edited = self.ok(
            "PUT",
            "/reservations",
            {
                "reservationId": reservation["id"],
                "startTime": iso(start),
                "endTime": iso(start + dt.timedelta(minutes=90)),
                "guestCount": 3,
            },
            user=self.customer,
        )
        self.assertEqual((3, iso(start)), (edited["guestCount"], edited["startTime"]))
        other = self.book(self.customer, self.table4["id"], start=at(days=2, hour=18))
        self.error(
            409,
            "PUT",
            "/reservations",
            {
                "reservationId": other["id"],
                "startTime": iso(start + dt.timedelta(minutes=30)),
                "endTime": iso(start + dt.timedelta(minutes=120)),
                "guestCount": 2,
            },
            user=self.customer,
        )

    def test_waiter_books_for_a_customer(self) -> None:
        start = at(days=2, hour=12)
        body = {
            "tableId": self.table4["id"],
            "startTime": iso(start),
            "endTime": iso(start + dt.timedelta(minutes=90)),
            "guestCount": 2,
            "customerEmail": "owner@mail.com",
        }
        reservation = self.ok("POST", "/reservations", body, user=self.waiter)
        stored = self.table("Reservations").get_item(Key={"id": reservation["id"]})["Item"]
        self.assertEqual(
            (self.customer["id"], self.waiter["id"], True),
            (stored["customerId"], stored["waiterId"], stored["createdByWaiter"]),
        )
        self.error(
            404,
            "POST",
            "/reservations",
            {
                **body,
                "customerEmail": "nobody@mail.com",
                "startTime": iso(at(days=3, hour=12)),
                "endTime": iso(at(days=3, hour=13, minute=30)),
            },
            user=self.waiter,
        )

    def test_status_transitions_publish_report_on_completion(self) -> None:
        reservation = self.book(self.customer, self.table4["id"])
        path = f"/reservations/{reservation['id']}/status"
        self.error(403, "PATCH", path, {"newStatus": 2}, user=self.customer)
        self.error(400, "PATCH", path, {"newStatus": 0}, user=self.waiter)
        self.ok("PATCH", path, {"newStatus": 2}, user=self.waiter)
        self.ok("PATCH", path, {"newStatus": "Completed"}, user=self.waiter)
        self.ok(
            "POST",
            "/feedback",
            {"reservationId": reservation["id"], "rating": 5, "type": 0, "comment": "Great"},
            user=self.customer,
        )
        self.error(400, "PATCH", path, {"newStatus": 1}, user=self.waiter)
        messages = self.sqs.receive_message(QueueUrl=self.queue_url, MaxNumberOfMessages=10).get("Messages", [])
        report = max((json.loads(m["Body"]) for m in messages), key=lambda r: r.get("Revision", 0))
        self.assertEqual(
            (reservation["id"], self.waiter["id"], 5, 0),
            (report["ReservationId"], report["WaiterId"], report["ServiceRating"], report["CuisineRating"]),
        )

    def test_change_table(self) -> None:
        reservation = self.book(self.customer, self.table4["id"], guests=4)
        path = f"/reservations/{reservation['id']}/table"
        self.error(400, "PATCH", path, {"tableId": self.table2["id"]}, user=self.waiter)  # capacity 2 < 4 guests
        big = self.ok(
            "POST",
            "/tables",
            {"locationId": self.r["location"]["id"], "capacity": 6, "tableNumber": 3},
            user=self.r["admin"],
        )
        moved = self.ok("PATCH", path, {"tableId": big["id"]}, user=self.waiter)
        self.assertEqual(big["id"], moved["tableId"])
        self.error(403, "PATCH", path, {"tableId": big["id"]}, user=self.customer)


class OrdersTest(AwsTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.r = self.seed_restaurant()
        self.customer, self.waiter = self.r["customer"], self.r["waiter"]
        self.caesar, self.tom_yum, _ = (d["id"] for d in self.r["dishes"])
        self.reservation = self.book(self.customer, self.r["tables"][0]["id"])
        self.rid = self.reservation["id"]

    def create(self, *items: tuple[str, int], user=None):
        body = {"reservationId": self.rid, "orderItems": [{"dishId": d, "quantity": q} for d, q in items]}
        return self.call("POST", "/orders", body, user=user or self.customer)

    def test_customer_pre_order_lifecycle(self) -> None:
        status, order = self.create((self.caesar, 2), (self.tom_yum, 1))
        self.assertEqual(201, status, order)
        self.assertEqual(0, order["status"])
        self.assertEqual(
            {"Caesar Salad": 2, "Tom Yum": 1}, {i["dish"]["name"]: i["quantity"] for i in order["orderItems"]}
        )
        self.assertIn(" - ", order["reservationTime"])
        self.assertEqual(400, self.create((self.caesar, 1))[0])  # one active order per reservation

        self.assertEqual(
            "Pre-order updated successfully.",
            self.ok(
                "PUT",
                f"/orders/{self.rid}",
                {"orderItems": [{"dishId": self.caesar, "quantity": 3}]},
                user=self.customer,
            ),
        )
        self.ok("POST", f"/orders/{self.rid}/submit", user=self.customer)
        self.assertEqual(3, self.ok("GET", f"/orders/{self.rid}", user=self.customer)["status"])
        self.ok("POST", f"/orders/{self.rid}/unsubmit", user=self.customer)
        self.assertEqual(0, self.ok("GET", f"/orders/{self.rid}", user=self.customer)["status"])
        self.assertEqual(1, len(self.ok("GET", "/orders", user=self.customer)))
        self.ok("DELETE", f"/orders/{self.rid}", user=self.customer)
        self.assertEqual([], self.ok("GET", "/orders", user=self.customer))

    def test_order_rules(self) -> None:
        stranger = self.create_user("stranger@mail.com", "Sam", "Stranger")
        self.assertEqual(403, self.create((self.caesar, 1), user=stranger)[0])
        self.assertEqual(400, self.create(("unknown", 1))[0])
        self.assertEqual(400, self.create((self.caesar, 0))[0])
        self.create((self.caesar, 1))
        self.error(403, "GET", f"/orders/{self.rid}", user=stranger)
        self.ok("GET", f"/orders/{self.rid}", user=self.waiter)

    def test_waiter_is_notified_and_confirms_dishes(self) -> None:
        self.create((self.caesar, 2), (self.tom_yum, 1))
        notifications = self.ok("GET", "/notifications", user=self.waiter)
        self.assertEqual(1, len(notifications))
        self.assertIn("2x Caesar Salad, 1x Tom Yum", notifications[0]["message"])
        self.error(403, "PATCH", f"/notifications/{notifications[0]['id']}/read", user=self.customer)
        self.ok("PATCH", f"/notifications/{notifications[0]['id']}/read", user=self.waiter)
        self.assertEqual([], self.ok("GET", "/notifications", user=self.waiter))

        self.ok("PATCH", f"/reservations/{self.rid}/order/confirmations/{self.caesar}", user=self.waiter)
        self.assertEqual(0, self.ok("GET", f"/orders/{self.rid}", user=self.customer)["status"])
        self.ok("PATCH", f"/reservations/{self.rid}/order/cancellations/{self.tom_yum}", user=self.waiter)
        order = self.ok("GET", f"/orders/{self.rid}", user=self.customer)
        self.assertEqual((1, {1, 2}), (order["status"], {i["state"] for i in order["orderItems"]}))
        self.assertTrue(self.ok("GET", f"/reservations/{self.rid}", user=self.customer)["hasSubmittedPreOrder"])
        self.error(404, "PATCH", f"/reservations/{self.rid}/order/confirmations/unknown", user=self.waiter)
        self.error(403, "PATCH", f"/reservations/{self.rid}/order/confirmations/{self.caesar}", user=self.customer)

    def test_waiter_orders_for_walk_in_guests_during_the_visit(self) -> None:
        start = at(days=1, hour=19)
        walk_in = self.ok(
            "POST",
            "/reservations",
            {
                "tableId": self.r["tables"][1]["id"],
                "startTime": iso(start),
                "endTime": iso(start + dt.timedelta(minutes=90)),
                "guestCount": 2,
            },
            user=self.waiter,
        )
        body = {"reservationId": walk_in["id"], "orderItems": [{"dishId": self.caesar, "quantity": 1}]}
        self.error(400, "POST", "/orders", body, user=self.waiter)  # visit not started yet
        self.ok("PATCH", f"/reservations/{walk_in['id']}/status", {"newStatus": 2}, user=self.waiter)
        order = self.ok("POST", "/orders", body, user=self.waiter)
        self.assertEqual(1, len(order["orderItems"]))
        self.assertEqual(
            "Order updated successfully.",
            self.ok(
                "PUT",
                f"/orders/{walk_in['id']}",
                {"orderItems": [{"dishId": self.tom_yum, "quantity": 2}]},
                user=self.waiter,
            ),
        )


if __name__ == "__main__":
    unittest.main()
