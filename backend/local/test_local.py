"""Regression checks for the local adapter; run separately from the Cognito unit suite."""

from __future__ import annotations

import base64
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit

from fastapi.testclient import TestClient
from moto import mock_aws

from core import aws, dynamo
from core.errors import BadRequest, Unauthorized
from local import local_auth, seed_local


class LocalAdapterTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.directory = tempfile.TemporaryDirectory(prefix="restaurant-local-tests-")
        cls.env = patch.dict(
            os.environ,
            {
                "LOCAL_DATA_DIR": cls.directory.name,
                "AWS_DEFAULT_REGION": "eu-north-1",
                "AWS_ACCESS_KEY_ID": "testing",
                "AWS_SECRET_ACCESS_KEY": "testing",
            },
        )
        cls.env.start()
        # Import installs local adapters for this dedicated test process only.
        from local.app import app

        cls.app = app

    @classmethod
    def tearDownClass(cls) -> None:
        cls.env.stop()
        cls.directory.cleanup()
        local_auth._secret.cache_clear()

    def setUp(self) -> None:
        self.mock = mock_aws()
        self.mock.start()
        aws.reset_clients()
        seed_local.create_tables()
        seed_local.seed_data()
        self.client = TestClient(self.app)
        response = self.client.post("/signin", json={"email": "admin@example.com", "password": seed_local.PASSWORD})
        self.assertEqual(200, response.status_code, response.text)
        self.admin_headers = {"Authorization": "Bearer " + response.json()["idToken"]}

    def tearDown(self) -> None:
        self.client.close()
        aws.reset_clients()
        self.mock.stop()

    def test_seed_supports_booking_categories_menus_and_preserves_password(self) -> None:
        self.assertEqual(13, len(dynamo.scan_all("tables")))
        self.assertTrue(all(table["capacity"] > 0 for table in dynamo.scan_all("tables")))
        for category, count in (("Appetizer", 4), ("MainCourse", 4), ("Dessert", 3)):
            response = self.client.get("/dishes", params={"dishType": category})
            self.assertEqual(count, len(response.json()))
            self.assertTrue(all(dish["calories"] and dish["imageUrl"] for dish in response.json()))
        for location in self.client.get("/locations").json():
            self.assertEqual(11, len(self.client.get(f"/locations/{location['id']}/dishes").json()))
        token = local_auth.sign_in("customer@example.com", seed_local.PASSWORD)["accessToken"]
        local_auth.change_password(seed_local.PASSWORD, "New-password!42", token)
        seed_local.seed_data()
        self.assertTrue(local_auth.sign_in("customer@example.com", "New-password!42")["idToken"])
        self.assertEqual(11, len(dynamo.scan_all("dishes")))

    def test_health_images_and_binary_downloads_have_real_content(self) -> None:
        self.assertEqual({"status": "ok", "mode": "local"}, self.client.get("/health").json())
        photo = (Path(__file__).parents[1] / "scripts" / "seed-images" / "spring-salad.jpg").read_bytes()
        response = self.client.post(
            "/locations",
            headers=self.admin_headers,
            json={
                "address": "Local image regression",
                "description": "Photo check",
                "averageOccupancy": "0%",
                "imageBase64": base64.b64encode(photo).decode(),
            },
        )
        self.assertEqual(201, response.status_code, response.text)
        image_url = response.json()["imageUrl"]
        self.assertTrue(image_url.startswith("http://localhost:18080/images/"))
        downloaded = self.client.get(urlsplit(image_url).path)
        self.assertEqual(photo, downloaded.content)
        self.assertEqual("image/jpeg", downloaded.headers["content-type"])
        for payload, mime, filename in (
            (b"%PDF-1.4\nexample", "application/pdf", "report.pdf"),
            (b"Location,Revenue\nTbilisi,10\n", "text/csv", "report.csv"),
        ):
            with self.subTest(mime=mime), patch("services.reports.download", return_value=(payload, filename, mime)):
                report = self.client.get("/reports/download", headers=self.admin_headers)
                self.assertEqual(200, report.status_code, report.text)
                self.assertEqual(payload, report.content)
                self.assertIn(filename, report.headers["content-disposition"])

    def test_restart_preserves_admin_deletions_until_explicit_seed(self) -> None:
        with (
            tempfile.TemporaryDirectory(prefix="restaurant-bootstrap-test-") as directory,
            patch.dict(os.environ, {"LOCAL_DATA_DIR": directory}),
        ):
            seed_local.populate(bootstrap=True)
            dish = dynamo.scan_all("dishes")[0]
            dynamo.delete_item("dishes", {"id": dish["id"]})
            seed_local.populate(bootstrap=True)
            self.assertEqual(10, len(dynamo.scan_all("dishes")))
            seed_local.populate()
            self.assertEqual(11, len(dynamo.scan_all("dishes")))

    def test_explicit_photo_refresh_preserves_custom_data_deleted_dishes_and_order_snapshots(self) -> None:
        dishes = {dish["name"]: dish for dish in dynamo.scan_all("dishes")}
        spring = dishes["Spring Salad"]
        spring.update(imageUrl="/assets/img/dishes/spring-salad.jpg", price=99, translations={"uk": {"name": "Весна"}})
        dynamo.put_item("dishes", spring)
        chicken = dishes["Chicken Shkmeruli"]
        chicken["imageUrl"] = "/assets/svg/dish-placeholder.svg"
        dynamo.put_item("dishes", chicken)
        custom = dishes["Grilled Salmon"]
        custom["imageUrl"] = "https://example.com/my-salmon-photo.jpg"
        dynamo.put_item("dishes", custom)
        changed_recipe = dishes["Pelamushi"]
        changed_recipe.update(description="A different recipe", imageUrl="/assets/svg/dish-placeholder.svg")
        dynamo.put_item("dishes", changed_recipe)
        dynamo.delete_item("dishes", {"id": dishes["Mushroom Risotto"]["id"]})
        snapshot = {"orderId": "photo-test-order", "customerId": "photo-test-user", "dishSnapshot": spring}
        dynamo.put_item("orders", snapshot)

        self.assertEqual(2, seed_local.refresh_dish_photos())
        self.assertEqual(
            {**spring, "imageUrl": "/assets/img/dishes/spring-salad.webp"},
            dynamo.get_item("dishes", {"id": spring["id"]}),
        )
        self.assertEqual(
            "/assets/img/dishes/chicken-shkmeruli.webp", dynamo.get_item("dishes", {"id": chicken["id"]})["imageUrl"]
        )
        self.assertEqual(custom, dynamo.get_item("dishes", {"id": custom["id"]}))
        self.assertEqual(changed_recipe, dynamo.get_item("dishes", {"id": changed_recipe["id"]}))
        self.assertEqual(10, len(dynamo.scan_all("dishes")))
        self.assertEqual(
            snapshot, dynamo.get_item("orders", {"orderId": "photo-test-order", "customerId": "photo-test-user"})
        )
        self.assertEqual(0, seed_local.refresh_dish_photos())

    def test_photo_refresh_does_not_overwrite_a_concurrent_admin_upload(self) -> None:
        spring = next(d for d in dynamo.scan_all("dishes") if d["name"] == "Spring Salad")
        spring["imageUrl"] = "/assets/img/dishes/spring-salad.jpg"
        dynamo.put_item("dishes", spring)
        original_scan = dynamo.scan_all

        def changed_after_read(table_name: str) -> list[dict]:
            result = original_scan(table_name)
            dynamo.put_item("dishes", {**spring, "imageUrl": "https://example.com/new-admin-photo.webp"})
            return result

        with patch.object(dynamo, "scan_all", side_effect=changed_after_read):
            self.assertEqual(0, seed_local.refresh_dish_photos())
        self.assertEqual(
            "https://example.com/new-admin-photo.webp", dynamo.get_item("dishes", {"id": spring["id"]})["imageUrl"]
        )

    def test_local_tokens_and_recovery_fail_safely(self) -> None:
        for token in ("garbage", "x.y.z", "a.b", None):
            self.assertIsNone(local_auth.caller_from_token(token))
        user = "customer@example.com"
        token = local_auth.sign_in(user, seed_local.PASSWORD)["idToken"]
        self.assertEqual(user, local_auth.caller_from_token(token).email)
        self.assertIsNone(local_auth.caller_from_token(token[:-1] + ("a" if token[-1] != "a" else "b")))
        recovery = local_auth.forgot_password(user)
        with self.assertRaises(BadRequest):
            local_auth.reset_password(user, "invalid", "Password-new!42")
        local_auth.reset_password(user, recovery["resetCode"], "Password-new!42")
        with self.assertRaises(Unauthorized):
            local_auth.sign_in(user, seed_local.PASSWORD)
        self.assertTrue(local_auth.sign_in(user, "Password-new!42")["idToken"])
        with self.assertRaises(BadRequest):
            local_auth.reset_password(user, recovery["resetCode"], "Password-other!42")


if __name__ == "__main__":
    unittest.main()
