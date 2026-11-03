"""Test harness: a moto-backed AWS account built from deployment_resources.json plus API call helpers."""

from __future__ import annotations

import contextlib
import datetime as dt
import json
import os
import re
import sys
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

import boto3
from moto import mock_aws

BACKEND = Path(__file__).resolve().parents[1]
API_HANDLER = BACKEND / "src" / "lambdas" / "api_handler"
if str(API_HANDLER) not in sys.path:
    sys.path.insert(0, str(API_HANDLER))

from main import handler  # noqa: E402

from core import aws  # noqa: E402

REGION = "eu-north-1"
IMAGES_BUCKET = "test-images"
PROFILE_BUCKET = "test-profile-images"
QUEUE = "restaurant-reports-queue"
PASSWORD = "Passw0rd!"


def aliases() -> dict[str, str]:
    values = {}
    for line in (BACKEND / "syndicate" / "syndicate_aliases.yml").read_text().splitlines():
        match = re.match(r'^(\w+):\s*"?([^"#]*)"?', line.strip())
        if match:
            values[match.group(1)] = match.group(2).strip()
    return values


def dynamodb_tables() -> list[dict[str, Any]]:
    """Table definitions from deployment_resources.json with ${aliases} resolved."""
    names = aliases()
    resources = json.loads(
        re.sub(r"\$\{(\w+)\}", lambda m: names[m.group(1)], (BACKEND / "deployment_resources.json").read_text())
    )
    tables = []
    for name, spec in resources.items():
        if spec.get("resource_type") != "dynamodb_table":
            continue
        attributes = {spec["hash_key_name"]: spec["hash_key_type"]}
        keys = [{"AttributeName": spec["hash_key_name"], "KeyType": "HASH"}]
        if spec.get("sort_key_name"):
            attributes[spec["sort_key_name"]] = spec["sort_key_type"]
            keys.append({"AttributeName": spec["sort_key_name"], "KeyType": "RANGE"})
        indexes = []
        for index in spec.get("global_indexes", []):
            attributes[index["index_key_name"]] = index["index_key_type"]
            schema = [{"AttributeName": index["index_key_name"], "KeyType": "HASH"}]
            if index.get("index_sort_key_name"):
                attributes[index["index_sort_key_name"]] = index["index_sort_key_type"]
                schema.append({"AttributeName": index["index_sort_key_name"], "KeyType": "RANGE"})
            indexes.append({"IndexName": index["name"], "KeySchema": schema, "Projection": {"ProjectionType": "ALL"}})
        definition = {
            "TableName": name,
            "KeySchema": keys,
            "AttributeDefinitions": [{"AttributeName": k, "AttributeType": v} for k, v in attributes.items()],
            "BillingMode": "PAY_PER_REQUEST",
        }
        if indexes:
            definition["GlobalSecondaryIndexes"] = indexes
        tables.append(definition)
    return tables


def at(days: int = 1, hour: int = 12, minute: int = 0) -> dt.datetime:
    """UTC datetime ``days`` from today at ``hour:minute``."""
    today = dt.datetime.now(dt.timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    return today + dt.timedelta(days=days, hours=hour, minutes=minute)


def iso(value: dt.datetime) -> str:
    return value.strftime("%Y-%m-%dT%H:%M:%S.000Z")


class AwsTestCase(unittest.TestCase):
    """Fresh, empty AWS account (DynamoDB, Cognito, S3, SQS) for every test."""

    def setUp(self) -> None:
        self._mock = mock_aws()
        self._mock.start()
        self.addCleanup(self._mock.stop)
        env = mock.patch.dict(
            os.environ,
            {
                "AWS_ACCESS_KEY_ID": "testing",
                "AWS_SECRET_ACCESS_KEY": "testing",
                "AWS_DEFAULT_REGION": REGION,
                "REGION": REGION,
                "RESTAURANT_TIMEZONE": "UTC",
                "imagesBucketName": IMAGES_BUCKET,
                "profileImagesBucketName": PROFILE_BUCKET,
                "reports_queue_name": QUEUE,
            },
        )
        env.start()
        self.addCleanup(env.stop)
        aws.reset_clients()
        self.addCleanup(aws.reset_clients)

        dynamodb = boto3.client("dynamodb", region_name=REGION)
        for definition in dynamodb_tables():
            dynamodb.create_table(**definition)

        self.cognito = boto3.client("cognito-idp", region_name=REGION)
        self.pool_id = self.cognito.create_user_pool(PoolName="pool")["UserPool"]["Id"]
        self.client_id = self.cognito.create_user_pool_client(
            UserPoolId=self.pool_id, ClientName="client", ExplicitAuthFlows=["ALLOW_USER_PASSWORD_AUTH"]
        )["UserPoolClient"]["ClientId"]
        os.environ["COGNITO_USER_POOL_ID"] = self.pool_id
        os.environ["COGNITO_USER_POOL_CLIENT_ID"] = self.client_id

        s3 = boto3.client("s3", region_name=REGION)
        for bucket in (IMAGES_BUCKET, PROFILE_BUCKET):
            s3.create_bucket(Bucket=bucket, CreateBucketConfiguration={"LocationConstraint": REGION})
        self.sqs = boto3.client("sqs", region_name=REGION)
        self.queue_url = self.sqs.create_queue(QueueName=QUEUE)["QueueUrl"]

    # --- API calls -------------------------------------------------------------

    def call(
        self,
        method: str,
        path: str,
        body: Any = None,
        *,
        user: dict[str, Any] | None = None,
        query: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, Any]:
        event: dict[str, Any] = {
            "httpMethod": method,
            "path": path,
            "headers": headers or {},
            "queryStringParameters": query,
            "body": None if body is None else json.dumps(body),
            "requestContext": {"authorizer": {"claims": user["claims"]}} if user else {},
        }
        response = handler(event)
        text = response.get("body") or ""
        try:
            parsed = json.loads(text) if text else None
        except ValueError:
            parsed = text
        return response["statusCode"], parsed

    def ok(self, method: str, path: str, body: Any = None, **kwargs: Any) -> Any:
        status, data = self.call(method, path, body, **kwargs)
        self.assertLess(status, 300, f"{method} {path} -> {status}: {data}")
        return data

    def error(self, expected_status: int, method: str, path: str, body: Any = None, **kwargs: Any) -> Any:
        status, data = self.call(method, path, body, **kwargs)
        self.assertEqual(expected_status, status, f"{method} {path}: {data}")
        return data

    # --- Users -------------------------------------------------------------------

    def create_user(
        self, email: str, first: str = "John", last: str = "Doe", groups: tuple[str, ...] = ("Customer",)
    ) -> dict[str, Any]:
        self.cognito.sign_up(
            ClientId=self.client_id,
            Username=email,
            Password=PASSWORD,
            UserAttributes=[
                {"Name": "email", "Value": email},
                {"Name": "given_name", "Value": first},
                {"Name": "family_name", "Value": last},
            ],
        )
        self.cognito.admin_confirm_sign_up(UserPoolId=self.pool_id, Username=email)
        for group in groups:
            with contextlib.suppress(self.cognito.exceptions.GroupExistsException):
                self.cognito.create_group(UserPoolId=self.pool_id, GroupName=group)
            self.cognito.admin_add_user_to_group(UserPoolId=self.pool_id, Username=email, GroupName=group)
        attrs = {
            a["Name"]: a["Value"]
            for a in self.cognito.admin_get_user(UserPoolId=self.pool_id, Username=email)["UserAttributes"]
        }
        claims = {"sub": attrs["sub"], "email": email, "cognito:username": email, "cognito:groups": ",".join(groups)}
        return {"id": attrs["sub"], "email": email, "claims": claims}

    def as_role(self, user: dict[str, Any], *groups: str) -> dict[str, Any]:
        """Same user with different groups in the token claims."""
        return {**user, "claims": {**user["claims"], "cognito:groups": ",".join(groups)}}

    # --- Catalog seed --------------------------------------------------------------

    def seed_restaurant(self) -> dict[str, Any]:
        """One location with two tables, three dishes on its menu, an admin, a waiter and a customer."""
        admin = self.create_user("admin@mail.com", "Anna", "Admin", groups=("Admin", "Customer"))
        location = self.ok(
            "POST",
            "/locations",
            {
                "address": "Rustaveli Avenue 48",
                "description": "Main hall",
                "totalCapacity": 40,
                "averageOccupancy": "60%",
            },
            user=admin,
        )
        tables = [
            self.ok("POST", "/tables", {"locationId": location["id"], "capacity": 4, "tableNumber": 1}, user=admin),
            self.ok("POST", "/tables", {"locationId": location["id"], "capacity": 2, "tableNumber": 2}, user=admin),
        ]
        dish_body = {
            "description": "Fresh",
            "weight": "300 g",
            "calories": "200",
            "proteins": "5",
            "fats": "3",
            "carbohydrates": "20",
            "vitamins": "A, C",
            "state": "Available",
            "locationIds": [location["id"]],
        }
        dishes = [
            self.ok(
                "POST",
                "/dishes",
                {**dish_body, "name": "Caesar Salad", "price": 180, "dishType": "Appetizer"},
                user=admin,
            ),
            self.ok(
                "POST", "/dishes", {**dish_body, "name": "Tom Yum", "price": 220, "dishType": "MainCourse"}, user=admin
            ),
            self.ok(
                "POST", "/dishes", {**dish_body, "name": "Cheesecake", "price": 95.5, "dishType": "Dessert"}, user=admin
            ),
        ]
        waiter = self.create_user("waiter@mail.com", "Walter", "Waiter", groups=("Customer",))
        self.ok("POST", "/waiters", {"email": waiter["email"], "locationId": location["id"]}, user=admin)
        waiter = self.as_role(waiter, "Customer", "Waiter")
        customer = self.create_user("owner@mail.com", "Yevhenii", "Owner")
        return {
            "admin": admin,
            "location": location,
            "tables": tables,
            "dishes": dishes,
            "waiter": waiter,
            "customer": customer,
        }

    def book(
        self, user: dict[str, Any], table_id: str, guests: int = 4, start: dt.datetime | None = None
    ) -> dict[str, Any]:
        start = start or at(days=2, hour=12)
        return self.ok(
            "POST",
            "/reservations",
            {
                "tableId": table_id,
                "startTime": iso(start),
                "endTime": iso(start + dt.timedelta(minutes=90)),
                "guestCount": guests,
            },
            user=user,
        )

    def table(self, name: str) -> Any:
        return boto3.resource("dynamodb", region_name=REGION).Table(name)
