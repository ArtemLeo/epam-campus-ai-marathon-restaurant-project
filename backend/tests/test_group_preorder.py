"""Group pre-order: the marathon backend homework (levels 1–3) and the guest flow it builds on."""

from __future__ import annotations

import unittest

from helpers import AwsTestCase, at


class GroupPreOrderTestCase(AwsTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.r = self.seed_restaurant()
        self.owner = self.r["customer"]
        self.caesar, self.tom_yum, self.cheesecake = (d["id"] for d in self.r["dishes"])
        self.reservation = self.book(self.owner, self.r["tables"][0]["id"], guests=4)
        self.token = self.ok("GET", f"/reservations/{self.reservation['id']}/invite-token", user=self.owner)["token"]
        self.group_id = self.ok("GET", f"/guest/invites/{self.token}")["GroupReservationId"]

    # --- helpers ---------------------------------------------------------------

    def join(self, name: str) -> tuple[str, dict[str, str]]:
        session = self.ok("POST", "/guest/sessions", {"groupReservationId": self.group_id, "guestName": name})
        return session["SessionId"], {"Authorization": f"Bearer {session['SessionToken']}"}

    def guest_cart(self, name: str, dish_id: str, quantity: int, submit: bool) -> str:
        session_id, headers = self.join(name)
        self.ok(
            "POST", f"/guest/sessions/{session_id}/dishes", {"dishId": dish_id, "quantity": quantity}, headers=headers
        )
        if submit:
            self.ok("POST", f"/guest/sessions/{session_id}/submit", headers=headers)
        return session_id

    def owner_preorder(self, dish_id: str, quantity: int = 1, submit: bool = True) -> None:
        self.ok(
            "POST",
            "/orders",
            {"reservationId": self.reservation["id"], "orderItems": [{"dishId": dish_id, "quantity": quantity}]},
            user=self.owner,
        )
        if submit:
            self.ok("POST", f"/orders/{self.reservation['id']}/submit", user=self.owner)

    def homework_group(self) -> tuple[str, str]:
        """Owner Caesar ×1 (submitted), Andrii Caesar ×2 (submitted), Olena Tom Yum ×1 (still choosing)."""
        self.owner_preorder(self.caesar)
        andrii = self.guest_cart("Andrii", self.caesar, 2, submit=True)
        olena = self.guest_cart("Olena", self.tom_yum, 1, submit=False)
        return andrii, olena


class Level1SessionsTest(GroupPreOrderTestCase):
    def test_lists_owner_and_guests_with_totals(self) -> None:
        andrii, olena = self.homework_group()
        data = self.ok("GET", f"/guest/groups/{self.group_id}/sessions", user=self.owner)

        self.assertEqual(760, data["total"])
        owner, first, second = data["participants"]
        self.assertEqual(
            ("Owner", "Yevhenii", 180, True), (owner["type"], owner["name"], owner["total"], owner["isSubmitted"])
        )
        self.assertEqual(
            (andrii, "Guest", "Andrii", 360, True),
            (first["id"], first["type"], first["name"], first["total"], first["isSubmitted"]),
        )
        self.assertEqual(
            (olena, "Olena", 220, False), (second["id"], second["name"], second["total"], second["isSubmitted"])
        )
        self.assertEqual(
            {"id": self.caesar, "name": "Caesar Salad", "price": 180},
            {k: first["items"][0]["dish"][k] for k in ("id", "name", "price")},
        )
        self.assertEqual(2, first["items"][0]["quantity"])

    def test_empty_group_shows_only_the_owner(self) -> None:
        data = self.ok("GET", f"/guest/groups/{self.group_id}/sessions", user=self.owner)
        self.assertEqual(0, data["total"])
        self.assertEqual(
            [("Owner", [], False)], [(p["type"], p["items"], p["isSubmitted"]) for p in data["participants"]]
        )

    def test_only_the_owner_can_see_sessions(self) -> None:
        stranger = self.create_user("stranger@mail.com", "Sam", "Stranger")
        self.error(403, "GET", f"/guest/groups/{self.group_id}/sessions", user=stranger)
        self.error(401, "GET", f"/guest/groups/{self.group_id}/sessions")
        self.error(404, "GET", "/guest/groups/unknown/sessions", user=self.owner)


class Level2OwnerSessionTest(GroupPreOrderTestCase):
    def test_returns_the_owner_participant_id(self) -> None:
        first = self.ok("GET", f"/reservations/{self.reservation['id']}/guest-session-id", user=self.owner)
        again = self.ok("GET", f"/reservations/{self.reservation['id']}/guest-session-id", user=self.owner)
        sessions = self.ok("GET", f"/guest/groups/{self.group_id}/sessions", user=self.owner)
        self.assertEqual(first, again)
        self.assertEqual(first["guestSessionId"], sessions["participants"][0]["id"])

    def test_owner_only_and_not_found(self) -> None:
        stranger = self.create_user("stranger@mail.com", "Sam", "Stranger")
        self.error(403, "GET", f"/reservations/{self.reservation['id']}/guest-session-id", user=stranger)
        self.error(404, "GET", "/reservations/unknown/guest-session-id", user=self.owner)


class Level2SubmitTest(GroupPreOrderTestCase):
    def submit(self, user=None, reservation_id=None):
        return self.call(
            "POST",
            f"/group-reservations/{self.group_id}/submit",
            {"reservationId": reservation_id or self.reservation["id"]},
            user=user or self.owner,
        )

    def test_consolidates_only_submitted_carts_by_dish(self) -> None:
        self.homework_group()
        self.guest_cart("Mariia", self.tom_yum, 1, submit=True)
        status, body = self.submit()
        self.assertEqual(200, status, body)
        self.assertEqual(
            sorted([{"dishId": self.caesar, "quantity": 3}, {"dishId": self.tom_yum, "quantity": 1}], key=str),
            sorted(body, key=str),
        )

        order = self.ok("GET", f"/orders/{self.reservation['id']}", user=self.owner)
        self.assertEqual(3, order["status"])  # SubmittedByCustomer
        self.assertEqual(
            {self.caesar: 3, self.tom_yum: 1}, {i["dish"]["id"]: i["quantity"] for i in order["orderItems"]}
        )
        self.assertEqual("Submitted", self.ok("GET", f"/guest/groups/{self.group_id}/status")["status"])
        notifications = self.ok("GET", "/notifications", user=self.r["waiter"])
        self.assertTrue(any(n["message"].startswith("Group pre-order") for n in notifications))

    def test_second_submit_is_rejected(self) -> None:
        self.homework_group()
        self.assertEqual(200, self.submit()[0])
        status, body = self.submit()
        self.assertEqual((400, "Group reservation was submitted."), (status, body["error"]))

    def test_guests_can_order_when_owner_does_not_want_food(self) -> None:
        self.guest_cart("Andrii", self.caesar, 2, submit=True)
        status, body = self.submit()
        self.assertEqual(200, status)
        self.assertEqual([{"dishId": self.caesar, "quantity": 2}], body)

    def test_needs_a_submitted_cart(self) -> None:
        self.owner_preorder(self.caesar, submit=False)
        self.guest_cart("Olena", self.tom_yum, 1, submit=False)
        status, body = self.submit()
        self.assertEqual((400, "No submitted guest sessions found to consolidate."), (status, body["error"]))

    def test_needs_dishes_in_submitted_carts(self) -> None:
        self.owner_preorder(self.caesar, submit=False)
        self.guest_cart("Andrii", self.cheesecake, 1, submit=True)
        self.ok("DELETE", f"/dishes/{self.cheesecake}", user=self.r["admin"], query={"force": "true"})
        status, body = self.submit()
        self.assertEqual(400, status)
        self.assertIn("no longer available", body["error"])

    def test_owner_only_and_not_found(self) -> None:
        self.homework_group()
        stranger = self.create_user("stranger@mail.com", "Sam", "Stranger")
        self.assertEqual(403, self.submit(user=stranger)[0])
        self.assertEqual(400, self.submit(reservation_id="unknown")[0])
        self.assertEqual(
            404,
            self.call(
                "POST", "/group-reservations/unknown/submit", {"reservationId": self.reservation["id"]}, user=self.owner
            )[0],
        )

    def test_guests_cannot_change_carts_after_submit(self) -> None:
        self.owner_preorder(self.caesar)
        session_id, headers = self.join("Late")
        self.assertEqual(200, self.submit()[0])
        body = self.error(
            409, "POST", f"/guest/sessions/{session_id}/dishes", {"dishId": self.caesar, "quantity": 1}, headers=headers
        )
        self.assertEqual("GroupReservationSubmitted", body["errorCode"])


class Level3RemoveGuestTest(GroupPreOrderTestCase):
    def test_removes_guest_and_returns_updated_snapshot(self) -> None:
        andrii, olena = self.homework_group()
        data = self.ok("DELETE", f"/guest/groups/{self.group_id}/sessions/{andrii}", user=self.owner)
        self.assertEqual(
            [("Owner", 180), ("Olena", 220)],
            [(p["name"] if p["type"] == "Guest" else "Owner", p["total"]) for p in data["participants"]],
        )
        self.assertEqual(400, data["total"])
        self.assertEqual(olena, data["participants"][1]["id"])

    def test_rules(self) -> None:
        andrii, _ = self.homework_group()
        owner_session = self.ok("GET", f"/reservations/{self.reservation['id']}/guest-session-id", user=self.owner)[
            "guestSessionId"
        ]
        stranger = self.create_user("stranger@mail.com", "Sam", "Stranger")
        other = self.book(stranger, self.r["tables"][0]["id"], guests=3, start=self.reservation_start_plus_hours(4))
        other_token = self.ok("GET", f"/reservations/{other['id']}/invite-token", user=stranger)["token"]
        other_group = self.ok("GET", f"/guest/invites/{other_token}")["GroupReservationId"]

        self.error(403, "DELETE", f"/guest/groups/{self.group_id}/sessions/{andrii}", user=stranger)
        self.error(404, "DELETE", f"/guest/groups/{self.group_id}/sessions/unknown", user=self.owner)
        self.error(400, "DELETE", f"/guest/groups/{other_group}/sessions/{andrii}", user=stranger)
        self.error(400, "DELETE", f"/guest/groups/{self.group_id}/sessions/{owner_session}", user=self.owner)

    def reservation_start_plus_hours(self, hours: int):
        return at(days=2, hour=12 + hours)


class GuestFlowTest(GroupPreOrderTestCase):
    def test_invite_details_use_pascal_case(self) -> None:
        invite = self.ok("GET", f"/guest/invites/{self.token}")
        self.assertEqual(
            {
                "GroupReservationId",
                "LocationId",
                "RestaurantName",
                "LocationAddress",
                "StartTime",
                "EndTime",
                "MaxGuestCount",
                "TableNumber",
                "InviterName",
            },
            set(invite),
        )
        self.assertEqual(
            ("Rustaveli Avenue 48", 4, 1, "Yevhenii Owner"),
            (invite["LocationAddress"], invite["MaxGuestCount"], invite["TableNumber"], invite["InviterName"]),
        )

    def test_guest_limit_applies_to_new_guests_only(self) -> None:
        small = self.book(self.owner, self.r["tables"][1]["id"], guests=2)
        token = self.ok("GET", f"/reservations/{small['id']}/invite-token", user=self.owner)["token"]
        group_id = self.ok("GET", f"/guest/invites/{token}")["GroupReservationId"]
        session = self.ok("POST", "/guest/sessions", {"groupReservationId": group_id, "guestName": "Kateryna"})

        body = self.error(400, "GET", f"/guest/invites/{token}")
        self.assertEqual("GuestLimitExceeded", body["errorCode"])
        self.error(400, "POST", "/guest/sessions", {"groupReservationId": group_id, "guestName": "Extra"})
        # The guest who already joined (and the owner) can still open the invite.
        self.ok("GET", f"/guest/invites/{token}", headers={"Authorization": f"Bearer {session['SessionToken']}"})
        self.ok("GET", f"/guest/invites/{token}", user=self.owner)

    def test_cart_operations(self) -> None:
        session_id, headers = self.join("Kateryna")
        self.error(401, "POST", f"/guest/sessions/{session_id}/dishes", {"dishId": self.caesar, "quantity": 1})
        self.error(
            400, "POST", f"/guest/sessions/{session_id}/dishes", {"dishId": self.caesar, "quantity": 0}, headers=headers
        )
        self.error(
            400, "POST", f"/guest/sessions/{session_id}/dishes", {"dishId": "unknown", "quantity": 1}, headers=headers
        )
        self.error(400, "POST", f"/guest/sessions/{session_id}/submit", headers=headers)  # empty cart

        self.ok("POST", f"/guest/sessions/{session_id}/dishes", {"dishId": self.caesar, "quantity": 3}, headers=headers)
        self.ok(
            "DELETE", f"/guest/sessions/{session_id}/dishes", {"dishId": self.caesar, "quantity": 1}, headers=headers
        )
        info = self.ok("GET", f"/guest/sessions/{session_id}", headers=headers)
        self.assertEqual(
            ("Kateryna", 2, 360, False),
            (info["name"], info["items"][0]["quantity"], info["total"], info["isSubmitted"]),
        )

        self.ok("POST", f"/guest/sessions/{session_id}/submit", headers=headers)
        self.error(409, "POST", f"/guest/sessions/{session_id}/submit", headers=headers)

    def test_menu_is_grouped_by_dish_type(self) -> None:
        session_id, headers = self.join("Kateryna")
        menu = self.ok("GET", f"/guest/sessions/{session_id}/menu", headers=headers)["dishes"]
        self.assertEqual({"Appetizer", "MainCourse", "Dessert"}, set(menu))
        self.assertEqual(
            ("Caesar Salad", "Available", True),
            (menu["Appetizer"][0]["name"], menu["Appetizer"][0]["state"], menu["Appetizer"][0]["selectable"]),
        )

    def test_status_counts_owner_and_guests(self) -> None:
        self.join("Kateryna")
        self.assertEqual(
            {"currentParticipants": 2, "maxCapacity": 4, "status": "Open"},
            self.ok("GET", f"/guest/groups/{self.group_id}/status"),
        )

    def test_cancelled_reservation_closes_the_group(self) -> None:
        self.ok("DELETE", "/reservations", {"id": self.reservation["id"]}, user=self.owner)
        self.assertEqual("Closed", self.ok("GET", f"/guest/groups/{self.group_id}/status")["status"])
        body = self.error(400, "GET", f"/guest/invites/{self.token}")
        self.assertEqual("GroupReservationExpired", body["errorCode"])


if __name__ == "__main__":
    unittest.main()
