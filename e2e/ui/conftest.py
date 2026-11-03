"""UI fixtures: Playwright page + API-seeded group."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from api.client import RestaurantApi
from api.flow import build_group, cleanup, unique_name
from playwright.sync_api import Page

from ui.helpers.auth import login


@pytest.fixture
def page(browser_page: Page) -> Page:
    """Playwright page (from the root conftest)."""
    return browser_page


@pytest.fixture
def owner_api(api_url: str, customer_token: str) -> Iterator[RestaurantApi]:
    with RestaurantApi(api_url, customer_token) as api:
        yield api


@pytest.fixture
def setup_group(owner_api: RestaurantApi) -> Iterator[dict]:
    """Reservation with 3 guests (2 submitted, 1 still choosing). Returns ids, guests and expected totals."""
    group = build_group(
        owner_api,
        [unique_name("Ann"), unique_name("Bob"), unique_name("Cat")],
        submit_carts=(True, True, False),
    )
    yield {
        "reservation_id": group.reservation_id,
        "group_id": group.group_id,
        "guest_sessions": group.guests,
        "owner_session_id": group.owner_session_id,
        "group": group,
    }
    cleanup(owner_api, group.reservation_id)


@pytest.fixture
def logged_in_page(page: Page, base_url: str) -> Page:
    email, password = os.getenv("CUSTOMER_EMAIL"), os.getenv("CUSTOMER_PASSWORD")
    if not email or not password:
        pytest.skip("CUSTOMER_EMAIL / CUSTOMER_PASSWORD not set")
    login(page, base_url, email, password)
    return page
