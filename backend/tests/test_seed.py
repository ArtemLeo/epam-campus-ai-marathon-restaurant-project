"""The demo-data seed script, run twice against the moto-backed API (it must be idempotent)."""

from __future__ import annotations

import base64
import importlib.util
import json
import unittest
from typing import Any

from helpers import BACKEND, AwsTestCase, handler

from core import aws

_spec = importlib.util.spec_from_file_location("seed", BACKEND / "scripts" / "seed.py")
seed = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(seed)


class InProcessApi(seed.Api):
    """Calls the Lambda handler directly; the token's claims play the API Gateway authorizer."""

    def call(self, method: str, path: str, body: Any = None) -> tuple[int, Any]:
        event: dict[str, Any] = {
            "httpMethod": method,
            "path": path,
            "headers": {},
            "body": None if body is None else json.dumps(body),
        }
        if "?" in path:
            event["path"], raw_query = path.split("?", 1)
            event["queryStringParameters"] = dict(pair.split("=", 1) for pair in raw_query.split("&"))
        if self.token:
            payload = self.token.split(".")[1]
            claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
            claims["cognito:groups"] = ",".join(claims.get("cognito:groups", []))
            event["requestContext"] = {"authorizer": {"claims": claims}}
        response = handler(event)
        return response["statusCode"], json.loads(response["body"]) if response["body"] else None


class SeedTest(AwsTestCase):
    def test_seed_is_complete_and_idempotent(self) -> None:
        for _ in range(2):
            seed.ensure_users(self.cognito, self.pool_id)
            seed.seed(InProcessApi("https://unused"))

        locations = self.ok("GET", "/locations")
        self.assertEqual(3, len(locations))
        self.assertTrue(all(loc["imageUrl"] for loc in locations))
        self.assertEqual(13, sum(loc["totalCapacity"] for loc in locations))
        dishes = self.ok("GET", "/dishes")
        self.assertEqual(11, len(dishes))
        self.assertEqual(11, sum(1 for d in dishes if d["imageUrl"]))
        for dish in dishes:
            key = dish["imageUrl"].split(".amazonaws.com/", 1)[1]
            image = aws.s3().get_object(Bucket="test-images", Key=key)
            self.assertEqual("image/webp", image["ContentType"])
            self.assertTrue(image["Body"].read().startswith(b"RIFF"))
        self.assertEqual(4, len(self.table("Waiters").scan()["Items"]))
        admins = self.cognito.list_users_in_group(UserPoolId=self.pool_id, GroupName="Admin")["Users"]
        self.assertEqual(["admin@example.com"], [u["Username"] for u in admins])


class DemoPhotoRecognitionTest(unittest.TestCase):
    def dish(self, name: str = "Spring Salad", **changes: Any) -> dict[str, Any]:
        spec = next(row for row in seed.DISHES if row[0] == name)
        return {"id": "dish-test-id", "name": name, "description": spec[6], **changes}

    def test_all_demo_recipes_have_distinct_webp_photos(self) -> None:
        self.assertEqual(11, len({spec[4] for spec in seed.DISHES}))
        for name, _, _, _, image, _, _ in seed.DISHES:
            with self.subTest(name=name):
                self.assertTrue(image.endswith(".webp"))
                for old in (None, "", "/assets/svg/dish-placeholder.svg", "/assets/img/dish-placeholder.jpg"):
                    self.assertEqual(
                        f"/assets/img/dishes/{image}", seed.replacement_demo_photo(self.dish(name, imageUrl=old))
                    )

    def test_original_static_and_content_addressed_photos_are_recognized(self) -> None:
        for name, old_image in seed.LEGACY_DISH_IMAGES.items():
            dish = self.dish(name)
            target = seed.replacement_demo_photo(dish)
            fingerprint = seed._legacy_image_fingerprint(old_image)
            for source in (
                f"/assets/img/dishes/{old_image}",
                f"https://photos.s3.eu-north-1.amazonaws.com/assets/img/dishes/dish_dish-test-id_{fingerprint}",
                f"http://localhost:18080/images/assets/img/dishes/dish_dish-test-id_{fingerprint}.jpeg",
            ):
                with self.subTest(name=name, source=source):
                    self.assertEqual(target, seed.replacement_demo_photo({**dish, "imageUrl": source}))

    def test_custom_recipes_uploads_and_already_upgraded_images_are_preserved(self) -> None:
        dish = self.dish()
        for changes in (
            {"name": "My spring salad"},
            {"description": "My different recipe"},
            {"imageUrl": "/assets/img/dishes/spring-salad.webp"},
            {"imageUrl": "https://restaurant.example/custom-photo.jpg"},
            {"imageUrl": "https://restaurant.example/assets/img/dishes/spring-salad.jpg"},
            {"imageUrl": "http://localhost:18080/images/assets/img/dishes/dish_dish-test-id_customhash.jpeg"},
            {"imageUrl": "/assets/img/dishes/avocado-pine-nut-bowl.jpg"},
        ):
            with self.subTest(changes=changes):
                self.assertIsNone(seed.replacement_demo_photo({**dish, **changes}))


if __name__ == "__main__":
    unittest.main()
