"""Create DynamoDB Local tables and populate with demo data.

Run inside the backend container at startup or manually:
    python -m local.seed_local
"""

from __future__ import annotations

import argparse
import os
import time
import uuid
from decimal import Decimal
from pathlib import Path

from botocore.exceptions import ClientError
from scripts.seed import DISHES, LOCATIONS, NUTRITION, USERS, replacement_demo_photo

from core import aws, dynamo
from local.local_auth import hash_password

PASSWORD = os.environ.get("DEMO_PASSWORD", "GreenTasty#2026")


TABLES_SCHEMA: list[dict] = [
    {
        "name": "Locations",
        "keys": [{"name": "id", "type": "S", "key_type": "HASH"}],
        "gsi": [],
    },
    {
        "name": "Dishes",
        "keys": [{"name": "id", "type": "S", "key_type": "HASH"}],
        "gsi": [],
    },
    {
        "name": "Tables",
        "keys": [{"name": "id", "type": "S", "key_type": "HASH"}],
        "gsi": [
            {
                "name": "locationId-tableNumber-index",
                "keys": [
                    {"name": "locationId", "type": "S", "key_type": "HASH"},
                    {"name": "tableNumber", "type": "N", "key_type": "RANGE"},
                ],
            }
        ],
    },
    {
        "name": "Reservations",
        "keys": [{"name": "id", "type": "S", "key_type": "HASH"}],
        "gsi": [
            {"name": "GSI_ByTableId", "keys": [{"name": "tableId", "type": "S", "key_type": "HASH"}]},
            {"name": "GSI_UserId", "keys": [{"name": "customerId", "type": "S", "key_type": "HASH"}]},
            {"name": "GSI_WaiterId", "keys": [{"name": "waiterId", "type": "S", "key_type": "HASH"}]},
        ],
    },
    {
        "name": "Orders",
        "keys": [
            {"name": "orderId", "type": "S", "key_type": "HASH"},
            {"name": "customerId", "type": "S", "key_type": "RANGE"},
        ],
        "gsi": [
            {"name": "GSI_ReservationId", "keys": [{"name": "reservationId", "type": "S", "key_type": "HASH"}]},
            {"name": "GSI_CustomerId", "keys": [{"name": "customerId", "type": "S", "key_type": "HASH"}]},
        ],
    },
    {
        "name": "Feedback",
        "keys": [
            {"name": "reservationId", "type": "S", "key_type": "HASH"},
            {"name": "createdAt", "type": "S", "key_type": "RANGE"},
        ],
        "gsi": [
            {
                "name": "locationId-createdAt-index",
                "keys": [
                    {"name": "locationId", "type": "S", "key_type": "HASH"},
                    {"name": "createdAt", "type": "S", "key_type": "RANGE"},
                ],
            }
        ],
    },
    {
        "name": "Notifications",
        "keys": [{"name": "id", "type": "S", "key_type": "HASH"}],
        "gsi": [{"name": "UserIdIndex", "keys": [{"name": "userId", "type": "S", "key_type": "HASH"}]}],
    },
    {
        "name": "Waiters",
        "keys": [{"name": "userId", "type": "S", "key_type": "HASH"}],
        "gsi": [{"name": "locationId-index", "keys": [{"name": "locationId", "type": "S", "key_type": "HASH"}]}],
    },
    {
        "name": "ProfileImages",
        "keys": [{"name": "userId", "type": "S", "key_type": "HASH"}],
        "gsi": [],
    },
    {
        "name": "Reports",
        "keys": [
            {"name": "waiterId", "type": "S", "key_type": "HASH"},
            {"name": "date", "type": "S", "key_type": "RANGE"},
        ],
        "gsi": [],
    },
    {
        "name": "ReportsHistory",
        "keys": [{"name": "id", "type": "S", "key_type": "HASH"}],
        "gsi": [{"name": "UserIdIndex", "keys": [{"name": "userId", "type": "S", "key_type": "HASH"}]}],
    },
    {
        "name": "GroupReservations",
        "keys": [{"name": "groupReservationId", "type": "S", "key_type": "HASH"}],
        "gsi": [
            {"name": "reservationId", "keys": [{"name": "reservationId", "type": "S", "key_type": "HASH"}]},
            {"name": "reservationToken", "keys": [{"name": "reservationToken", "type": "S", "key_type": "HASH"}]},
        ],
    },
    {
        "name": "GuestSessions",
        "keys": [{"name": "guestSessionId", "type": "S", "key_type": "HASH"}],
        "gsi": [
            {"name": "groupReservationId", "keys": [{"name": "groupReservationId", "type": "S", "key_type": "HASH"}]},
            {
                "name": "guestSessionTokenHash",
                "keys": [{"name": "guestSessionTokenHash", "type": "S", "key_type": "HASH"}],
            },
        ],
    },
    {
        "name": "LocalUsers",
        "keys": [{"name": "email", "type": "S", "key_type": "HASH"}],
        "gsi": [],
    },
]


def create_tables() -> None:
    db = aws.dynamodb()
    existing = [t.name for t in db.tables.all()]

    for spec in TABLES_SCHEMA:
        if spec["name"] in existing:
            print(f"  = table {spec['name']}")
            continue

        key_schema = [{"AttributeName": k["name"], "KeyType": k["key_type"]} for k in spec["keys"]]
        attr_defs_map: dict[str, str] = {k["name"]: k["type"] for k in spec["keys"]}
        gsi_defs = []

        for gsi in spec.get("gsi", []):
            gsi_keys = [{"AttributeName": k["name"], "KeyType": k["key_type"]} for k in gsi["keys"]]
            for k in gsi["keys"]:
                attr_defs_map[k["name"]] = k["type"]
            gsi_defs.append(
                {
                    "IndexName": gsi["name"],
                    "KeySchema": gsi_keys,
                    "Projection": {"ProjectionType": "ALL"},
                }
            )

        attr_defs = [{"AttributeName": n, "AttributeType": t} for n, t in attr_defs_map.items()]

        kwargs: dict = {
            "TableName": spec["name"],
            "KeySchema": key_schema,
            "AttributeDefinitions": attr_defs,
            "BillingMode": "PAY_PER_REQUEST",
        }
        if gsi_defs:
            kwargs["GlobalSecondaryIndexes"] = gsi_defs

        db.create_table(**kwargs)
        print(f"  + table {spec['name']}")


def seed_data() -> None:
    """Add missing demo data without overwriting edits or resetting passwords."""
    db = aws.dynamodb()
    users = db.Table("LocalUsers")
    for email, first, last, groups in USERS:
        if not users.get_item(Key={"email": email}).get("Item"):
            roles = ["Waiter", "Customer"] if email.startswith("waiter.") else list(groups)
            users.put_item(
                Item={
                    "email": email,
                    "sub": str(uuid.uuid4()),
                    "given_name": first,
                    "family_name": last,
                    "password_hash": hash_password(PASSWORD),
                    "groups": roles,
                }
            )

    existing_locations = {item["address"]: item for item in dynamo.scan_all("locations")}
    existing_tables = dynamo.scan_all("tables")
    location_ids = []
    for spec in LOCATIONS:
        location = existing_locations.get(spec["address"])
        if location is None:
            location = {
                "id": str(uuid.uuid4()),
                "address": spec["address"],
                "description": spec["description"],
                "averageOccupancy": spec["averageOccupancy"],
                "imageUrl": f"/assets/img/locations/{spec['image']}",
            }
            dynamo.put_item("locations", location)
            for number, capacity in spec["tables"]:
                dynamo.put_item(
                    "tables",
                    {
                        "id": str(uuid.uuid4()),
                        "locationId": location["id"],
                        "tableNumber": number,
                        "capacity": capacity,
                    },
                )
            for email in spec["waiters"]:
                user = users.get_item(Key={"email": email})["Item"]
                dynamo.put_item("waiters", {"userId": user["sub"], "locationId": location["id"]})
        elif not location.get("imageUrl"):
            location["imageUrl"] = f"/assets/img/locations/{spec['image']}"
            dynamo.put_item("locations", location)
        location_ids.append(location["id"])

    # Repair data written by the earlier local seed without changing valid admin edits.
    for table in existing_tables:
        if "capacity" not in table and "numberOfSeats" in table:
            table["capacity"] = table.pop("numberOfSeats")
            table.pop("isAvailable", None)
            dynamo.put_item("tables", table)

    known = {item["name"]: item for item in dynamo.scan_all("dishes")}
    dish_ids = []
    for name, dish_type, price, weight, image, state, description in DISHES:
        dish = known.get(name)
        image_url = f"/assets/img/dishes/{image}" if image else "/assets/svg/dish-placeholder.svg"
        if dish is None:
            dish = {
                "id": str(uuid.uuid4()),
                "name": name,
                "dishType": dish_type,
                "price": Decimal(str(price)),
                "weight": weight,
                "state": state,
                "description": description,
                "imageUrl": image_url,
                **NUTRITION,
            }
            dynamo.put_item("dishes", dish)
        elif "dishType" not in dish or "nutrition" in dish:
            dish["dishType"] = dish.pop("type", dish_type)
            for key, value in dish.pop("nutrition", NUTRITION).items():
                dish.setdefault(key, value)
            dish.setdefault("imageUrl", image_url)
            dynamo.put_item("dishes", dish)
        if dish.get("imageUrl") == "/assets/img/dish-placeholder.jpg":
            dish["imageUrl"] = "/assets/svg/dish-placeholder.svg"
            dynamo.put_item("dishes", dish)
        dish_ids.append(dish["id"])
    for location_id in location_ids:
        location = dynamo.get_item("locations", {"id": location_id})
        if "specialtyDishIds" not in location:
            location["specialtyDishIds"] = location.pop("dishes", dish_ids)
            dynamo.put_item("locations", location)
    print("Demo ready: 3 locations, 13 tables, 11 dishes. Existing edits/passwords preserved.")


def refresh_dish_photos() -> int:
    """Upgrade only recognized demo photos, without recreating deleted catalog items.

    A conditional single-attribute update also preserves concurrent administrator edits.
    Historical order/group snapshots intentionally keep their original image references.
    """
    updated = 0
    table = aws.table("dishes")
    for dish in dynamo.scan_all("dishes"):
        target = replacement_demo_photo(dish)
        if target is None:
            continue
        values = {":new": target, ":name": dish["name"], ":description": dish["description"]}
        condition = "#name = :name AND #description = :description AND "
        if "imageUrl" in dish:
            condition += "#image = :old"
            values[":old"] = dish["imageUrl"]
        else:
            condition += "attribute_not_exists(#image)"
        try:
            table.update_item(
                Key={"id": dish["id"]},
                UpdateExpression="SET #image = :new",
                ConditionExpression=condition,
                ExpressionAttributeNames={"#image": "imageUrl", "#name": "name", "#description": "description"},
                ExpressionAttributeValues=values,
            )
            updated += 1
        except ClientError as error:
            if error.response["Error"]["Code"] != "ConditionalCheckFailedException":
                raise
            print(f"  = skipped concurrently changed dish {dish['name']}")
    print(f"Updated {updated} demo dish photos. Custom uploads, recipes and all other data preserved.")
    return updated


def cleanup_aqa() -> None:
    """Remove all local acceptance-test records, including leftovers after an interrupted run."""
    locations = [item for item in dynamo.scan_all("locations") if str(item.get("address", "")).startswith("AQA")]
    location_ids = {item["id"] for item in locations}
    tables = [item for item in dynamo.scan_all("tables") if item.get("locationId") in location_ids]
    table_ids = {item["id"] for item in tables}
    reservations = [
        item
        for item in dynamo.scan_all("reservations")
        if item.get("locationId") in location_ids or item.get("tableId") in table_ids
    ]
    reservation_ids = {item["id"] for item in reservations}
    groups = [item for item in dynamo.scan_all("group_reservations") if item.get("reservationId") in reservation_ids]
    group_ids = {item["groupReservationId"] for item in groups}

    for item in dynamo.scan_all("orders"):
        if item.get("reservationId") in reservation_ids:
            dynamo.delete_item("orders", {"orderId": item["orderId"], "customerId": item["customerId"]})
    for item in dynamo.scan_all("guest_sessions"):
        if item.get("groupReservationId") in group_ids:
            dynamo.delete_item("guest_sessions", {"guestSessionId": item["guestSessionId"]})
    for item in groups:
        dynamo.delete_item("group_reservations", {"groupReservationId": item["groupReservationId"]})
    for item in dynamo.scan_all("feedback"):
        if item.get("reservationId") in reservation_ids:
            dynamo.delete_item("feedback", {"reservationId": item["reservationId"], "createdAt": item["createdAt"]})
    for item in reservations:
        dynamo.delete_item("reservations", {"id": item["id"]})
    for item in tables:
        dynamo.delete_item("tables", {"id": item["id"]})
    for item in dynamo.scan_all("waiters"):
        if item.get("locationId") in location_ids:
            dynamo.delete_item("waiters", {"userId": item["userId"]})
    for item in locations:
        dynamo.delete_item("locations", {"id": item["id"]})
    for item in dynamo.scan_all("dishes"):
        if str(item.get("name", "")).startswith("AQA") or item.get("description") in {
            "Acceptance test menu item",
            "Fresh vegetables with herbs.",
        }:
            dynamo.delete_item("dishes", {"id": item["id"]})
    for item in dynamo.scan_all("local_users"):
        if str(item.get("email", "")).startswith("aqa."):
            dynamo.delete_item("profile_images", {"userId": item["sub"]})
            dynamo.delete_item("local_users", {"email": item["email"]})
    print(f"Removed local AQA records: {len(locations)} locations, {len(reservation_ids)} reservations.")


def populate(*, bootstrap: bool = False) -> None:
    marker = Path(os.environ.get("LOCAL_DATA_DIR", "/app/data")) / ".demo-seeded"
    if bootstrap and marker.exists():
        print("Existing local data preserved. Run make seed explicitly to add missing demo data.")
        return
    seed_data()
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.touch()


def wait_for_dynamodb(max_wait: int = 30) -> None:
    import botocore.exceptions

    for i in range(max_wait):
        try:
            list(aws.dynamodb().tables.all())
            return
        except (botocore.exceptions.EndpointConnectionError, botocore.exceptions.ClientError):
            if i == 0:
                print("Waiting for DynamoDB Local...")
            time.sleep(1)
    raise SystemExit("DynamoDB Local not reachable")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--bootstrap", action="store_true", help="Seed only on the first start of this data volume")
    mode.add_argument(
        "--refresh-dish-photos", action="store_true", help="Upgrade only existing, recognizable demo dish photos"
    )
    mode.add_argument("--cleanup-aqa", action="store_true", help="Remove local records created by acceptance tests")
    args = parser.parse_args()
    wait_for_dynamodb()
    if args.cleanup_aqa:
        cleanup_aqa()
    elif args.refresh_dish_photos:
        refresh_dish_photos()
    else:
        print("Creating tables:")
        create_tables()
        print("\nSeeding data:")
        populate(bootstrap=args.bootstrap)
    print("\nDone!")
