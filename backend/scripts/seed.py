"""Fill a deployed environment with demo data through the public API.

Creates (idempotently) demo users in Cognito, then signs in as the admin and uses the API to add
locations with photos, tables, the menu and waiters. Safe to run more than once.

    python backend/scripts/seed.py --api-url https://<api-id>.execute-api.<region>.amazonaws.com/develop

The user pool is looked up by name (restaurant-backend-user-pool) unless --user-pool-id is given.
"""

from __future__ import annotations

import argparse
import base64
import contextlib
import hashlib
import json
import os
import ssl
import sys
import urllib.error
import urllib.request
from functools import cache
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import boto3

try:
    import certifi

    _SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    _SSL_CONTEXT = None

IMAGES = Path(__file__).with_name("seed-images")
PASSWORD = "GreenTasty#2026"

USERS = [
    # email, first name, last name, Cognito groups
    ("admin@example.com", "Anna", "Admin", ("Admin", "Customer")),
    ("waiter.rustaveli@example.com", "Mariia", "Shevchenko", ("Customer",)),
    ("waiter.rustaveli2@example.com", "Taras", "Bondar", ("Customer",)),
    ("waiter.abashidze@example.com", "Nino", "Beridze", ("Customer",)),
    ("waiter.baratashvili@example.com", "Giorgi", "Kapanadze", ("Customer",)),
    ("customer@example.com", "Olena", "Kovalenko", ("Customer",)),
    ("guest@example.com", "Andrii", "Melnyk", ("Customer",)),
]

LOCATIONS = [
    {
        "address": "Rustaveli Avenue 48",
        "description": "Our flagship on Tbilisi's main avenue: bright hall, open kitchen and a summer terrace.",
        "averageOccupancy": "75%",
        "image": "rustaveli-avenue-48.jpg",
        "tables": [(1, 2), (2, 2), (3, 4), (4, 4), (5, 6)],
        "waiters": ["waiter.rustaveli@example.com", "waiter.rustaveli2@example.com"],
    },
    {
        "address": "Abashidze Street 9",
        "description": "A cosy neighbourhood spot in Vake with seasonal vegetarian specials.",
        "averageOccupancy": "60%",
        "image": "abashidze-street-9.jpg",
        "tables": [(1, 2), (2, 4), (3, 4), (4, 6)],
        "waiters": ["waiter.abashidze@example.com"],
    },
    {
        "address": "Baratashvili Street 14",
        "description": "Old Town location with a view of the river, perfect for big company dinners.",
        "averageOccupancy": "45%",
        "image": "baratashvili-street-14.jpg",
        "tables": [(1, 2), (2, 4), (3, 6), (4, 8)],
        "waiters": ["waiter.baratashvili@example.com"],
    },
]

NUTRITION = {"calories": "350 kcal", "proteins": "12 g", "fats": "14 g", "carbohydrates": "40 g", "vitamins": "A, C, E"}
DISHES = [
    # name, type, price, weight, image, state, description
    (
        "Spring Salad",
        "Appetizer",
        12,
        "430 g",
        "spring-salad.webp",
        "Available",
        "Young greens, radish, cucumber and herb dressing.",
    ),
    (
        "Fresh Strawberry Mint Salad",
        "Appetizer",
        11,
        "350 g",
        "fresh-strawberry-mint-salad.webp",
        "Available",
        "Strawberries, mint, feta and balsamic glaze.",
    ),
    (
        "Avocado Pine Nut Bowl",
        "Appetizer",
        14.5,
        "380 g",
        "avocado-pine-nut-bowl.webp",
        "Available",
        "Avocado, quinoa, pine nuts and lime.",
    ),
    (
        "Roasted Sweet Potato & Lentil Salad",
        "Appetizer",
        13,
        "400 g",
        "roasted-sweet-potato-and-lentil-salad.webp",
        "Available",
        "Warm lentils with roasted sweet potato and tahini.",
    ),
    (
        "Khachapuri Adjaruli",
        "MainCourse",
        15,
        "450 g",
        "khachapuri-adjaruli.webp",
        "Available",
        "Boat-shaped bread with sulguni cheese, egg and butter.",
    ),
    (
        "Chicken Shkmeruli",
        "MainCourse",
        18.5,
        "420 g",
        "chicken-shkmeruli.webp",
        "Available",
        "Roasted chicken in creamy garlic sauce.",
    ),
    (
        "Mushroom Risotto",
        "MainCourse",
        16,
        "380 g",
        "mushroom-risotto.webp",
        "Available",
        "Arborio rice, porcini, parmesan.",
    ),
    (
        "Grilled Salmon",
        "MainCourse",
        22,
        "350 g",
        "grilled-salmon.webp",
        "OnStop",
        "Salmon steak with seasonal vegetables.",
    ),
    (
        "Pelamushi",
        "Dessert",
        6,
        "200 g",
        "pelamushi.webp",
        "Available",
        "Traditional grape-juice pudding with walnuts.",
    ),
    (
        "Chocolate Fondant",
        "Dessert",
        8.5,
        "180 g",
        "chocolate-fondant.webp",
        "Available",
        "Warm chocolate cake with a molten centre.",
    ),
    (
        "Churchkhela Cheesecake",
        "Dessert",
        7.5,
        "190 g",
        "churchkhela-cheesecake.webp",
        "OutOfStock",
        "Creamy cheesecake with churchkhela crumble.",
    ),
]


# Existing installations may still use the old low-resolution seed images or placeholders.
# Keep their fingerprints so an explicit refresh can distinguish seed photos from custom uploads.
LEGACY_DISH_IMAGES = {
    "Spring Salad": "spring-salad.jpg",
    "Fresh Strawberry Mint Salad": "fresh-strawberry-mint-salad.jpg",
    "Avocado Pine Nut Bowl": "avocado-pine-nut-bowl.jpg",
    "Roasted Sweet Potato & Lentil Salad": "roasted-sweet-potato-and-lentil-salad.jpg",
}
LEGACY_PLACEHOLDERS = {"", "/assets/img/dish-placeholder.jpg", "/assets/svg/dish-placeholder.svg"}


@cache
def _legacy_image_fingerprint(name: str) -> str:
    return hashlib.sha256((IMAGES / name).read_bytes()).hexdigest()[:16]


def replacement_demo_photo(dish: dict[str, Any]) -> str | None:
    """Return a bundled photo for an unchanged demo recipe with an identifiable old seed image.

    Matching by name alone could put the wrong food on a custom recipe. An uploaded photo must
    also match the original bytes' content-addressed key; arbitrary URLs are never replaced.
    """
    spec = next((row for row in DISHES if row[0] == dish.get("name") and row[6] == dish.get("description")), None)
    if not spec:
        return None
    target = f"/assets/img/dishes/{spec[4]}"
    url = dish.get("imageUrl") or ""
    if not isinstance(url, str):
        return None
    if url == target:
        return None
    # Empty photos and the project's placeholders are safe to upgrade for known demo recipes.
    if url in LEGACY_PLACEHOLDERS:
        return target
    original = LEGACY_DISH_IMAGES.get(spec[0])
    if original is None:
        return None
    if url == f"/assets/img/dishes/{original}":
        return target
    path = urlsplit(url).path
    fingerprint = _legacy_image_fingerprint(original)
    key = f"dish_{dish.get('id')}_{fingerprint}"
    # AWS uploads have no extension; the local adapter adds the detected file extension.
    known_paths = {f"/assets/img/dishes/{key}", f"/images/assets/img/dishes/{key}.jpeg"}
    return target if path in known_paths else None


class Api:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.token: str | None = None

    def call(self, method: str, path: str, body: Any = None) -> tuple[int, Any]:
        data = None if body is None else json.dumps(body).encode()
        request = urllib.request.Request(self.base_url + path, data=data, method=method)
        request.add_header("Content-Type", "application/json")
        if self.token:
            request.add_header("Authorization", f"Bearer {self.token}")
        try:
            with urllib.request.urlopen(request, timeout=60, context=_SSL_CONTEXT) as response:
                status, raw = response.status, response.read()
        except urllib.error.HTTPError as error:
            status, raw = error.code, error.read()
        try:
            return status, json.loads(raw) if raw else None
        except ValueError:
            return status, raw.decode(errors="replace")

    def ok(self, method: str, path: str, body: Any = None, allowed: tuple[int, ...] = ()) -> Any:
        status, data = self.call(method, path, body)
        if status >= 300 and status not in allowed:
            raise SystemExit(f"{method} {path} failed with {status}: {data}")
        return data


def image_base64(name: str | None) -> str | None:
    return base64.b64encode((IMAGES / name).read_bytes()).decode() if name else None


def find_pool(cognito: Any, pool_id: str | None) -> str:
    if pool_id:
        return pool_id
    for page in cognito.get_paginator("list_user_pools").paginate(MaxResults=60):
        for pool in page["UserPools"]:
            if pool["Name"] == "restaurant-backend-user-pool":
                return pool["Id"]
    raise SystemExit("User pool 'restaurant-backend-user-pool' not found; pass --user-pool-id")


def ensure_users(cognito: Any, pool_id: str, password: str = PASSWORD) -> None:
    for group in ("Admin", "Waiter", "Customer"):
        with contextlib.suppress(cognito.exceptions.GroupExistsException):
            cognito.create_group(UserPoolId=pool_id, GroupName=group, Description=f"Group for role {group}")
    for email, first, last, groups in USERS:
        created = False
        try:
            cognito.admin_create_user(
                UserPoolId=pool_id,
                Username=email,
                MessageAction="SUPPRESS",
                UserAttributes=[
                    {"Name": "email", "Value": email},
                    {"Name": "email_verified", "Value": "true"},
                    {"Name": "given_name", "Value": first},
                    {"Name": "family_name", "Value": last},
                ],
            )
            created = True
            print(f"  + user {email}")
        except cognito.exceptions.UsernameExistsException:
            print(f"  = user {email}")
        if created:
            cognito.admin_set_user_password(UserPoolId=pool_id, Username=email, Password=password, Permanent=True)
        for group in groups:
            cognito.admin_add_user_to_group(UserPoolId=pool_id, Username=email, GroupName=group)


def seed(api: Api, password: str = PASSWORD) -> None:
    signed_in = api.ok("POST", "/signin", {"email": USERS[0][0], "password": password})
    api.token = signed_in["idToken"]

    existing = {loc["address"]: loc for loc in api.ok("GET", "/locations")}
    location_ids = []
    for spec in LOCATIONS:
        location = existing.get(spec["address"])
        if location is None:
            location = api.ok(
                "POST",
                "/locations",
                {
                    "address": spec["address"],
                    "description": spec["description"],
                    "averageOccupancy": spec["averageOccupancy"],
                    "imageBase64": image_base64(spec["image"]),
                },
            )
            print(f"  + location {spec['address']}")
        else:
            print(f"  = location {spec['address']}")
        location_ids.append(location["id"])
        for number, capacity in spec["tables"]:
            api.ok(
                "POST",
                "/tables",
                {"locationId": location["id"], "capacity": capacity, "tableNumber": number},
                allowed=(409,),
            )
        for email in spec["waiters"]:
            api.ok("POST", "/waiters", {"email": email, "locationId": location["id"]}, allowed=(409,))

    known = {dish["name"] for dish in api.ok("GET", "/dishes")}
    for name, dish_type, price, weight, image, state, description in DISHES:
        if name in known:
            print(f"  = dish {name}")
            continue
        api.ok(
            "POST",
            "/dishes",
            {
                "name": name,
                "dishType": dish_type,
                "price": price,
                "weight": weight,
                "state": state,
                "description": description,
                "imageBase64": image_base64(image),
                "locationIds": location_ids,
                **NUTRITION,
            },
        )
        print(f"  + dish {name}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--api-url",
        required=True,
        help="API Gateway stage URL, e.g. https://abc.execute-api.eu-north-1.amazonaws.com/develop",
    )
    parser.add_argument("--region", default="eu-north-1")
    parser.add_argument("--user-pool-id")
    parser.add_argument("--demo", action="store_true", help="Explicitly allow demo accounts; never use on production.")
    args = parser.parse_args()

    password = os.environ.get("DEMO_PASSWORD", "")
    if not args.demo or not password or password == PASSWORD:
        raise SystemExit("Demo seed requires --demo and a unique DEMO_PASSWORD environment variable.")
    cognito = boto3.client("cognito-idp", region_name=args.region)
    pool_id = find_pool(cognito, args.user_pool_id)
    print(f"Users (pool {pool_id}):")
    ensure_users(cognito, pool_id, password)
    print("Catalog:")
    seed(Api(args.api_url), password)
    print("\nDemo accounts (existing passwords were not changed):")
    for email, first, last, groups in USERS:
        role = "Admin" if "Admin" in groups else ("Waiter" if email.startswith("waiter") else "Customer")
        print(f"  {role:<9} {email:<34} {first} {last}")


if __name__ == "__main__":
    sys.exit(main())
