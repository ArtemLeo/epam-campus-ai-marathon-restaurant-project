"""Delete all demo seed data from AWS so a fresh seed can recreate everything.

Clears: DynamoDB tables (dishes, locations, tables, waiters, etc.), S3 images,
and Cognito demo users.  Run from the project root with .venv-cloud.

Usage:
    .venv-cloud/bin/python backend/scripts/clean_seed.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import boto3

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

REGION = "eu-north-1"

# Tables to wipe completely (all items)
TABLES_TO_WIPE = [
    "Dishes",
    "Locations",
    "Tables",
    "Waiters",
    "Reservations",
    "Orders",
    "Feedback",
    "Notifications",
    "Reports",
    "ReportsHistory",
    "GroupReservations",
    "GuestSessions",
    "ProfileImages",
]

# Demo emails to remove from Cognito
DEMO_EMAILS = [
    "admin@example.com",
    "testowner@example.com",
    "customer@example.com",
    "guest@example.com",
    "waiter.rustaveli@example.com",
    "waiter.rustaveli2@example.com",
    "waiter.abashidze@example.com",
    "waiter.baratashvili@example.com",
    "testuser2026@gmail.com",
]


def wipe_table(dynamo, table_name: str) -> int:
    """Delete every item from a DynamoDB table."""
    table = dynamo.Table(table_name)
    key_schema = table.key_schema
    key_names = [k["AttributeName"] for k in key_schema]

    deleted = 0
    expr_names = {f"#k{i}": k for i, k in enumerate(key_names)}
    scan_kwargs: dict = {
        "ProjectionExpression": ", ".join(expr_names.keys()),
        "ExpressionAttributeNames": expr_names,
    }
    while True:
        response = table.scan(**scan_kwargs)
        items = response.get("Items", [])
        for item in items:
            key = {k: item[k] for k in key_names}
            table.delete_item(Key=key)
            deleted += 1
        if "LastEvaluatedKey" not in response:
            break
        scan_kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]
    return deleted


def clean_s3_images(s3_client, account: str) -> int:
    """Remove all objects from the images bucket (seed uploads)."""
    bucket = f"restaurant-backend-dev-images-{account}"
    deleted = 0
    paginator = s3_client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket):
        objects = page.get("Contents", [])
        if objects:
            s3_client.delete_objects(
                Bucket=bucket,
                Delete={"Objects": [{"Key": obj["Key"]} for obj in objects]},
            )
            deleted += len(objects)
    return deleted


def clean_cognito(cognito, pool_id: str) -> int:
    """Remove demo users from Cognito."""
    deleted = 0
    for email in DEMO_EMAILS:
        try:
            cognito.admin_delete_user(UserPoolId=pool_id, Username=email)
            print(f"  ✓ deleted user {email}")
            deleted += 1
        except cognito.exceptions.UserNotFoundException:
            print(f"  – {email} (not found)")
        except Exception as exc:
            print(f"  ✗ {email}: {exc}")
    # Also delete groups so seed recreates them cleanly
    for group in ("Admin", "Waiter", "Customer"):
        try:
            cognito.delete_group(UserPoolId=pool_id, GroupName=group)
            print(f"  ✓ deleted group {group}")
        except Exception:
            pass
    return deleted


def main() -> None:
    session = boto3.Session(region_name=REGION)
    account = session.client("sts").get_caller_identity()["Account"]
    dynamo = session.resource("dynamodb", region_name=REGION)
    s3 = session.client("s3", region_name=REGION)
    cognito = session.client("cognito-idp", region_name=REGION)

    pool_id = "eu-north-1_K1wp82SCa"

    print("=== Cleaning DynamoDB tables ===")
    for table_name in TABLES_TO_WIPE:
        try:
            count = wipe_table(dynamo, table_name)
            print(f"  ✓ {table_name}: {count} items deleted")
        except Exception as exc:
            print(f"  ✗ {table_name}: {exc}")

    print("\n=== Cleaning S3 images ===")
    count = clean_s3_images(s3, account)
    print(f"  ✓ {count} objects deleted from images bucket")

    print("\n=== Cleaning Cognito users ===")
    clean_cognito(cognito, pool_id)

    print("\n✅ Done! Now run seed with a new DEMO_PASSWORD.")


if __name__ == "__main__":
    main()
