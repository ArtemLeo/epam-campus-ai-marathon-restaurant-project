"""Feedback, the reporting pipeline (API → SQS → reports-handler → reports) and token verification."""

from __future__ import annotations

import base64
import csv
import datetime as dt
import gzip
import importlib.util
import io
import json
import os
import unittest
import zipfile
from unittest import mock

import boto3
import moto.cognitoidp
from helpers import BACKEND, PASSWORD, REGION, AwsTestCase, at, handler

from core import jwt_verifier


def load_lambda(name: str):
    path = BACKEND / "src" / "lambdas" / name / "main.py"
    spec = importlib.util.spec_from_file_location(f"{name}_main", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


reports_handler = load_lambda("reports_handler")
report_sender = load_lambda("report_sender")

with gzip.open(os.path.join(os.path.dirname(moto.cognitoidp.__file__), "resources", "jwks-public.json.gz")) as _jwks:
    MOTO_JWKS = json.loads(_jwks.read())["keys"]


class PipelineTestCase(AwsTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.r = self.seed_restaurant()
        self.customer, self.waiter, self.admin = (
            self.r["customer"],
            self.r["waiter"],
            self.r["admin"],
        )
        jwt_verifier.set_jwks(MOTO_JWKS)

    def id_token(self, email: str) -> str:
        return self.cognito.initiate_auth(
            ClientId=self.client_id,
            AuthFlow="USER_PASSWORD_AUTH",
            AuthParameters={"USERNAME": email, "PASSWORD": PASSWORD},
        )["AuthenticationResult"]["IdToken"]

    def visit(
        self,
        start: dt.datetime,
        service: int,
        cuisine: int,
        dishes: dict[str, int] | None = None,
    ) -> str:
        """Book, pre-order, rate and complete a reservation; returns its id."""
        reservation = self.book(self.customer, self.r["tables"][0]["id"], start=start)
        rid = reservation["id"]
        if dishes:
            items = [{"dishId": d, "quantity": q} for d, q in dishes.items()]
            self.ok(
                "POST",
                "/orders",
                {"reservationId": rid, "orderItems": items},
                user=self.customer,
            )
        self.ok("PATCH", f"/reservations/{rid}/status", {"newStatus": 2}, user=self.waiter)
        self.ok("PATCH", f"/reservations/{rid}/status", {"newStatus": 3}, user=self.waiter)
        for kind, rating in ((0, service), (1, cuisine)):
            if rating:
                self.ok(
                    "POST",
                    "/feedback",
                    {"reservationId": rid, "rating": rating, "type": kind},
                    user=self.customer,
                )
        return rid

    def drain_queue(self) -> None:
        """Deliver queued report messages to the reports-handler Lambda."""
        messages = self.sqs.receive_message(QueueUrl=self.queue_url, MaxNumberOfMessages=10).get("Messages", [])
        records = [{"messageId": m["MessageId"], "body": m["Body"]} for m in messages]
        with mock.patch.dict(os.environ, {"ReportsTableName": "Reports", "AwsRegion": REGION}):
            self.assertEqual({"batchItemFailures": []}, reports_handler.handler({"Records": records}))


class FeedbackTest(PipelineTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.rid = self.book(self.customer, self.r["tables"][0]["id"])["id"]
        self.ok(
            "PATCH",
            f"/reservations/{self.rid}/status",
            {"newStatus": 2},
            user=self.waiter,
        )
        self.ok(
            "PATCH",
            f"/reservations/{self.rid}/status",
            {"newStatus": 3},
            user=self.waiter,
        )
        self.qr_token = self.ok("GET", f"/reservations/{self.rid}/feedback-token", user=self.waiter)["token"]

    def test_anonymous_and_signed_in_feedback(self) -> None:
        anonymous = self.ok(
            "POST",
            "/feedback",
            {
                "reservationId": self.rid,
                "token": self.qr_token,
                "rating": 4,
                "type": 0,
                "comment": "Nice",
            },
        )
        self.assertIsNone(anonymous["userId"])
        token = self.id_token(self.customer["email"])
        signed = self.ok(
            "POST",
            "/feedback",
            {"reservationId": self.rid, "rating": 5, "type": "CuisineExperience"},
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual((self.customer["id"], 1), (signed["userId"], signed["type"]))
        self.error(
            409,
            "POST",
            "/feedback",
            {"reservationId": self.rid, "token": self.qr_token, "rating": 3, "type": 0},
        )
        self.error(
            400,
            "POST",
            "/feedback",
            {"reservationId": self.rid, "rating": 6, "type": 1},
        )
        self.cognito.admin_add_user_to_group(UserPoolId=self.pool_id, Username=self.waiter["email"], GroupName="Waiter")
        waiter_token = self.id_token(self.waiter["email"])
        self.error(
            403,
            "POST",
            "/feedback",
            {"reservationId": self.rid, "rating": 5, "type": 0},
            headers={"Authorization": f"Bearer {waiter_token}"},
        )

        both = self.ok("GET", f"/reservations/{self.rid}/feedback")
        self.assertEqual(
            ("Anonymous User", "Yevhenii Owner"),
            (both["service"]["username"], both["cuisineExperience"]["username"]),
        )

    def test_update_own_feedback(self) -> None:
        token = self.id_token(self.customer["email"])
        self.ok(
            "POST",
            "/feedback",
            {"reservationId": self.rid, "rating": 2, "type": 0},
            headers={"Authorization": f"Bearer {token}"},
        )
        self.ok(
            "PUT",
            "/feedback",
            {"reservationId": self.rid, "rating": 4, "type": 0, "comment": "Better"},
            user=self.customer,
        )
        self.assertEqual(
            (4, "Better"),
            tuple(self.ok("GET", f"/reservations/{self.rid}/feedback")["service"][k] for k in ("rating", "comment")),
        )
        stranger = self.create_user("stranger@mail.com", "Sam", "Stranger")
        self.error(
            403,
            "PUT",
            "/feedback",
            {"reservationId": self.rid, "rating": 1, "type": 0},
            user=stranger,
        )
        self.error(
            400,
            "PUT",
            "/feedback",
            {"reservationId": self.rid, "rating": 1, "type": 1},
            user=self.customer,
        )

    def test_location_feedback_pages_and_sorting(self) -> None:
        ratings = [3, 5, 1, 4, 2]
        for index, rating in enumerate(ratings):
            rid = self.book(
                self.customer,
                self.r["tables"][0]["id"],
                start=at(days=3 + index, hour=12),
            )["id"]
            self.ok(
                "PATCH",
                f"/reservations/{rid}/status",
                {"newStatus": 2},
                user=self.waiter,
            )
            self.ok(
                "PATCH",
                f"/reservations/{rid}/status",
                {"newStatus": 3},
                user=self.waiter,
            )
            self.ok(
                "POST",
                "/feedback",
                {"reservationId": rid, "rating": rating, "type": 0},
                user=self.customer,
            )
        query = {
            "locationId": self.r["location"]["id"],
            "type": "Service",
            "sort": "TopRatedFirst",
            "page": "1",
        }
        first = self.ok("GET", "/feedback", query=query)
        self.assertEqual(
            ([5, 4, 3, 2], 2, 1),
            (
                [f["rating"] for f in first["items"]],
                first["totalPages"],
                first["currentPage"],
            ),
        )
        second = self.ok("GET", "/feedback", query={**query, "page": "2"})
        self.assertEqual([1], [f["rating"] for f in second["items"]])
        self.assertEqual(3, self.ok("GET", f"/locations/{self.r['location']['id']}")["rating"])
        self.error(400, "GET", "/feedback", query={**query, "sort": "Random"})
        self.error(400, "GET", "/feedback", query={**query, "page": "0"})


class ReportsTest(PipelineTestCase):
    def test_completed_visits_build_admin_reports(self) -> None:
        caesar, tom_yum, _ = (d["id"] for d in self.r["dishes"])
        day = at(days=1, hour=12)
        self.visit(day, service=5, cuisine=4, dishes={caesar: 2})
        self.visit(day + dt.timedelta(hours=2), service=3, cuisine=0, dishes={tom_yum: 1})
        self.drain_queue()

        aggregate = self.table("Reports").scan()["Items"][0]
        self.assertEqual(
            (2, 2, 1),
            (
                aggregate["ordersProcessed"],
                aggregate["serviceRatingsCount"],
                aggregate["cuisineRatingsCount"],
            ),
        )
        self.assertEqual(580, aggregate["totalRevenue"])

        date = day.date().isoformat()
        query = {
            "locationId": self.r["location"]["id"],
            "startDate": date,
            "endDate": date,
            "type": "0",
        }
        self.error(403, "GET", "/reports/generate", user=self.customer, query=query)
        service = self.ok("GET", "/reports/generate", user=self.admin, query=query)
        self.assertEqual(
            ("Walter Waiter", 2, 4.0, 3.0, 3.0),
            (
                service[0]["waiterName"],
                service[0]["totalOrders"],
                service[0]["avgServiceFeedback"],
                service[0]["minServiceFeedback"],
                service[0]["workingHours"],
            ),
        )
        sales = self.ok(
            "GET",
            "/reports/generate",
            user=self.admin,
            query={**query, "type": "Sales"},
        )
        self.assertEqual(
            (580, 4.0, 2),
            (
                sales[0]["revenue"],
                sales[0]["avgCuisineFeedback"],
                sales[0]["totalOrders"],
            ),
        )

        history = self.ok("GET", "/reports", user=self.admin)
        self.assertEqual({0, 1}, {h["reportType"] for h in history})

        status, text = self.call(
            "GET",
            "/reports/download",
            user=self.admin,
            query={**query, "format": "csv"},
        )
        rows = list(csv.reader(io.StringIO(text)))
        self.assertEqual((200, "Waiter Name", "Walter Waiter"), (status, rows[0][1], rows[1][1]))

    def test_downloads_are_valid_files(self) -> None:
        self.visit(
            at(days=1, hour=12),
            service=5,
            cuisine=5,
            dishes={self.r["dishes"][0]["id"]: 1},
        )
        self.drain_queue()
        date = at(days=1).date().isoformat()
        event = {
            "httpMethod": "GET",
            "path": "/reports/download",
            "headers": {},
            "queryStringParameters": {
                "locationId": self.r["location"]["id"],
                "startDate": date,
                "endDate": date,
                "type": "1",
            },
            "requestContext": {"authorizer": {"claims": self.admin["claims"]}},
        }
        xlsx = handler(
            {
                **event,
                "queryStringParameters": {
                    **event["queryStringParameters"],
                    "format": "excel",
                },
            }
        )
        self.assertTrue(xlsx["isBase64Encoded"])
        with zipfile.ZipFile(io.BytesIO(base64.b64decode(xlsx["body"]))) as archive:
            self.assertIn("Rustaveli Avenue 48", archive.read("xl/worksheets/sheet1.xml").decode())
        pdf = handler(
            {
                **event,
                "queryStringParameters": {
                    **event["queryStringParameters"],
                    "format": "pdf",
                },
            }
        )
        content = base64.b64decode(pdf["body"])
        self.assertTrue(content.startswith(b"%PDF-1.4") and content.rstrip().endswith(b"%%EOF"))
        self.assertIn('attachment; filename="report_', pdf["headers"]["Content-Disposition"])

        localized = handler(
            {
                **event,
                "queryStringParameters": {
                    **event["queryStringParameters"],
                    "format": "csv",
                    "locale": "uk",
                },
            }
        )
        self.assertEqual(200, localized["statusCode"])
        self.assertTrue(localized["body"].startswith("Локація,"))
        self.error(
            400,
            "GET",
            "/reports/download",
            user=self.admin,
            query={**event["queryStringParameters"], "locale": "unsupported"},
        )

        empty = {
            "locationId": self.r["location"]["id"],
            "startDate": "2020-01-01",
            "endDate": "2020-01-02",
        }
        self.error(404, "GET", "/reports/download", user=self.admin, query=empty)
        self.error(
            400,
            "GET",
            "/reports/generate",
            user=self.admin,
            query={**empty, "startDate": "2020-02-01"},
        )

    def test_reports_handler_is_idempotent_and_drops_bad_messages(self) -> None:
        body = json.dumps(
            {
                "ReservationId": "r1",
                "WaiterId": "w1",
                "LocationId": "l1",
                "ReservationStart": "2026-01-10T12:00:00Z",
                "ReservationEnd": "2026-01-10T13:30:00Z",
                "ServiceRating": 4,
                "CuisineRating": 5,
                "Revenue": 100.5,
            }
        )
        records = [
            {"messageId": "1", "body": body},
            {"messageId": "2", "body": body},
            {"messageId": "3", "body": "{bad"},
        ]
        with mock.patch.dict(os.environ, {"ReportsTableName": "Reports", "AwsRegion": REGION}):
            self.assertEqual({"batchItemFailures": []}, reports_handler.handler({"Records": records}))
        item = self.table("Reports").get_item(Key={"waiterId": "w1", "date": "2026-01-10T00:00:00.000Z#l1"})["Item"]
        self.assertEqual((1, 1.5), (item["ordersProcessed"], float(item["hoursWorked"])))

    def test_weekly_report_email(self) -> None:
        self.visit(
            at(days=1, hour=12),
            service=4,
            cuisine=4,
            dishes={self.r["dishes"][0]["id"]: 1},
        )
        self.drain_queue()
        with mock.patch.object(report_sender.dt, "datetime", wraps=dt.datetime) as fake:
            fake.now.return_value = at(days=2, hour=8)
            env = {
                "ReportTableName": "Reports",
                "LocationTableName": "Locations",
                "CognitoUserPoolId": self.pool_id,
                "Region": REGION,
            }
            with mock.patch.dict(os.environ, {**env, "EmailFrom": ""}):
                self.assertFalse(report_sender.handler()["sent"])
            boto3.client("ses", region_name=REGION).verify_email_identity(EmailAddress="reports@example.com")
            with mock.patch.dict(os.environ, {**env, "EmailFrom": "reports@example.com"}):
                summary = report_sender.handler()
        self.assertEqual(
            (True, 1, 1),
            (summary["sent"], summary["recipients"], summary["aggregates"]),
        )
        email = report_sender.build_email("a@b.c", ["x@y.z"], {"r.csv": b"a,b\n"})
        self.assertIn(b'filename="r.csv"', email)


class InviteOwnerTokenTest(PipelineTestCase):
    def test_owner_opens_full_group_with_a_verified_token(self) -> None:
        reservation = self.book(self.customer, self.r["tables"][1]["id"], guests=2)
        token = self.ok("GET", f"/reservations/{reservation['id']}/invite-token", user=self.customer)["token"]
        group_id = self.ok("GET", f"/guest/invites/{token}")["GroupReservationId"]
        self.ok(
            "POST",
            "/guest/sessions",
            {"groupReservationId": group_id, "guestName": "Kateryna"},
        )
        self.error(400, "GET", f"/guest/invites/{token}")
        forged = self.id_token(self.customer["email"])[:-4] + "AAAA"
        self.error(
            400,
            "GET",
            f"/guest/invites/{token}",
            headers={"Authorization": f"Bearer {forged}"},
        )
        invite = self.ok(
            "GET",
            f"/guest/invites/{token}",
            headers={"Authorization": f"Bearer {self.id_token(self.customer['email'])}"},
        )
        self.assertEqual(group_id, invite["GroupReservationId"])


if __name__ == "__main__":
    unittest.main()
