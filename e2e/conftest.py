"""Shared pytest fixtures for the restaurant AQA suite."""

from __future__ import annotations

import os
import sys
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pytest
from api.client import RestaurantApi
from dotenv import load_dotenv

if TYPE_CHECKING:
    from playwright.sync_api import Browser, Page

load_dotenv(Path(__file__).parent / ".env")


def pytest_configure(config: pytest.Config) -> None:
    if not config.option.collectonly:
        required = [
            "API_URL",
            "ADMIN_EMAIL",
            "ADMIN_PASSWORD",
            "CUSTOMER_EMAIL",
            "CUSTOMER_PASSWORD",
            "GUEST_EMAIL",
            "GUEST_PASSWORD",
        ]
        missing = [name for name in required if not os.getenv(name)]
        if missing:
            raise pytest.UsageError(
                "Missing E2E configuration: " + ", ".join(missing) + ". See e2e/.env.example or run make e2e."
            )
    for line in (
        "api: API tests",
        "ui: UI tests (Playwright)",
        "level1: Level 1 scenarios",
        "level2: Level 2 scenarios",
        "level3: Level 3 scenarios",
    ):
        config.addinivalue_line("markers", line)


def _env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise pytest.UsageError(f"Environment variable {name} is not set (see e2e/.env.example)")
    return value


def _sign_in(api_url: str, email_var: str, password_var: str) -> str:
    with RestaurantApi(api_url) as api:
        return str(api.signin(_env(email_var), _env(password_var))["idToken"])


@pytest.fixture(scope="session")
def api_url() -> str:
    return _env("API_URL").rstrip("/")


@pytest.fixture(scope="session")
def base_url() -> str:
    return _env("BASE_URL").rstrip("/")


@pytest.fixture(scope="session")
def admin_token(api_url: str) -> str:
    return _sign_in(api_url, "ADMIN_EMAIL", "ADMIN_PASSWORD")


@pytest.fixture(scope="session")
def customer_token(api_url: str) -> str:
    return _sign_in(api_url, "CUSTOMER_EMAIL", "CUSTOMER_PASSWORD")


@pytest.fixture(scope="session", autouse=True)
def test_restaurant(api_url: str, admin_token: str) -> Iterator[dict]:
    """Own restaurant and waiter: access tests must never depend on another waiter's assignment.

    Run only against a development/test environment. Catalog data is removed on
    teardown; the registered test account remains because the API has no account
    deletion endpoint. A demo reset removes those accounts locally.
    """
    suffix = uuid.uuid4().hex[:10]
    email = f"aqa.waiter.{suffix}@example.com"
    password = f"Aq#{suffix}9"
    location_id = None
    dish_ids = []
    previous_location = os.environ.get("AQA_LOCATION_ID")
    with RestaurantApi(api_url, admin_token) as api:
        api._request(
            "POST",
            "/register",
            json={
                "firstName": "Aqa",
                "lastName": "Waiter",
                "email": email,
                "password": password,
                "confirmPassword": password,
            },
        )
        try:
            location = api._request(
                "POST",
                "/locations",
                json={
                    "address": f"AQA {suffix}",
                    "description": "Temporary acceptance-test restaurant",
                    "averageOccupancy": "0%",
                },
            )
            location_id = location["id"]
            api._request("POST", "/waiters", json={"email": email, "locationId": location_id})
            table = api._request("POST", "/tables", json={"locationId": location_id, "tableNumber": 1, "capacity": 8})
            for index in range(4):
                dish = api._request(
                    "POST",
                    "/dishes",
                    json={
                        "name": f"AQA {suffix} dish {index + 1}",
                        "description": "Acceptance test menu item",
                        "dishType": index % 3,
                        "price": 10 + index * 3,
                        "weight": "250 g",
                        "state": "Available",
                        "calories": "300 kcal",
                        "proteins": "12 g",
                        "fats": "10 g",
                        "carbohydrates": "40 g",
                        "vitamins": "A",
                        "locationIds": [location_id],
                    },
                )
                dish_ids.append(dish["id"])
            with RestaurantApi(api_url) as waiter:
                token = str(waiter.signin(email, password)["idToken"])
            os.environ["AQA_LOCATION_ID"] = location_id
            yield {
                "location": location,
                "table": table,
                "dish_ids": dish_ids,
                "waiter_token": token,
                "waiter_email": email,
                "waiter_password": password,
            }
        finally:
            if previous_location is None:
                os.environ.pop("AQA_LOCATION_ID", None)
            else:
                os.environ["AQA_LOCATION_ID"] = previous_location
            for dish_id in dish_ids:
                api.raw("DELETE", f"/dishes/{dish_id}", params={"force": "true"})
            if location_id:
                api.raw("DELETE", "/waiters", json={"email": email})
                api.raw("DELETE", f"/locations/{location_id}", params={"force": "true"})


@pytest.fixture(scope="session")
def waiter_token(test_restaurant: dict) -> str:
    return test_restaurant["waiter_token"]


@pytest.fixture
def unique_id() -> str:
    """Short random prefix for test-data isolation."""
    return uuid.uuid4().hex[:8]


@pytest.fixture(scope="session")
def _playwright_browser() -> Iterator["Browser"]:
    headless = os.getenv("HEADLESS", "true").strip().lower() not in {"0", "false", "no"}
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        executable = os.getenv("PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH")
        browser = pw.chromium.launch(
            headless=headless,
            executable_path=executable or None,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        yield browser
        browser.close()


@pytest.fixture
def browser_page(_playwright_browser: "Browser") -> Iterator["Page"]:
    context = _playwright_browser.new_context(
        viewport={"width": 1440, "height": 900}, timezone_id="Europe/Kyiv", locale="en-US"
    )
    page = context.new_page()
    yield page
    context.close()
