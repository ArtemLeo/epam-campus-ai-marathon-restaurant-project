"""Business acceptance: real forms, guest invitation, mobile cart and staff workflow."""

from __future__ import annotations

import os
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from api.client import RestaurantApi
from api.flow import cleanup, create_reservation
from playwright.sync_api import Page, expect

from ui.helpers.auth import login
from ui.fixtures import PNG_UPLOAD
from ui.pages.group_order_page import GroupOrderPage

pytestmark = pytest.mark.ui


def test_admin_location_upload_edit_delete(
    page: Page, base_url: str, api_url: str, admin_token: str, unique_id: str
) -> None:
    address = f"AQA UI {unique_id}"
    location_id = None
    login(page, base_url, os.environ["ADMIN_EMAIL"], os.environ["ADMIN_PASSWORD"])
    page.goto(f"{base_url}/admin")
    page.get_by_role("button", name="+ Add Location").click()
    dialog = page.get_by_role("dialog", name="Add Location")
    dialog.get_by_label("Address", exact=True).fill(address)
    dialog.get_by_label("Description", exact=True).fill("Created through the real admin form")
    dialog.get_by_label("Image", exact=True).set_input_files(PNG_UPLOAD)
    try:
        with page.expect_response(
            lambda response: response.url == f"{base_url}/api/locations" and response.request.method == "POST"
        ) as response:
            dialog.get_by_role("button", name="Save", exact=True).click()
        assert response.value.status == 201
        location_id = response.value.json()["id"]
        expect(dialog).to_have_count(0)
        card = page.locator("article.admin-card").filter(has=page.get_by_role("heading", name=address, exact=True))
        expect(card).to_be_visible()
        expect(card.locator("img")).to_be_visible()
        # Local S3 emulation stores an upload and returns its public AWS-shaped URL,
        # which is intentionally not fetched from the public Internet during E2E.
        assert response.value.json()["imageUrl"]
        card.get_by_role("button", name="Edit", exact=True).click()
        dialog = page.get_by_role("dialog", name="Edit Location")
        dialog.get_by_label("Description", exact=True).fill("Updated through the real admin form")
        dialog.get_by_role("button", name="Save", exact=True).click()
        expect(dialog).to_have_count(0)
        expect(card).to_contain_text("Updated through the real admin form")
        page.once("dialog", lambda prompt: prompt.accept())
        card.get_by_role("button", name="Delete", exact=True).click()
        expect(card).to_have_count(0)
    finally:
        if location_id:
            with RestaurantApi(api_url, admin_token) as admin:
                admin.raw("DELETE", f"/locations/{location_id}", params={"force": "true"})


def test_customer_books_then_submits_from_mobile_cart(
    logged_in_page: Page, base_url: str, api_url: str, owner_api: RestaurantApi, test_restaurant: dict
) -> None:
    page = logged_in_page
    rid = None
    page.goto(f"{base_url}/tables?locationId={test_restaurant['location']['id']}")
    page.get_by_label("Location", exact=True).select_option(test_restaurant["location"]["id"])
    page.get_by_label("Date", exact=True).fill((datetime.now(UTC) + timedelta(days=10)).date().isoformat())
    page.get_by_label("Guests", exact=True).select_option("2")
    page.get_by_role("button", name="View time slots").click()
    page.get_by_role("dialog").locator("button.slot").first.click()
    page.get_by_label(re.compile("Guests \\(max")).fill("2")
    try:
        with page.expect_response(
            lambda response: response.url == f"{base_url}/api/reservations" and response.request.method == "POST"
        ) as response:
            page.get_by_role("button", name="Confirm", exact=True).click()
        assert response.value.status == 201
        rid = response.value.json()["id"]
        expect(page.get_by_role("dialog", name="Reservation confirmed")).to_be_visible()
        expect(page.get_by_label("Invite link")).to_have_value(re.compile("/join/"))
        page.get_by_role("button", name="Done", exact=True).click()
        page.goto(f"{base_url}/menu")
        dish = owner_api._request("GET", f"/dishes/{test_restaurant['dish_ids'][0]}")
        page.locator(".dish-card").filter(has=page.get_by_role("heading", name=dish["name"], exact=True)).click()
        dialog = page.get_by_role("dialog", name=dish["name"], exact=True)
        dialog.get_by_label("Reservation", exact=True).select_option(rid)
        dialog.get_by_role("button", name="Add to Cart").click()
        expect(dialog).to_have_count(0)
        page.set_viewport_size({"width": 390, "height": 844})
        page.get_by_role("button", name=re.compile("^Cart(?:,|$)")).click()
        cart = page.get_by_role("dialog", name="Cart", exact=True)
        expect(cart).to_be_visible()
        cart.get_by_role("button", name="Submit Pre-order", exact=True).click()
        expect(page.get_by_role("dialog", name="Pre-order Submitted!")).to_be_visible()
        assert owner_api.get_order(rid)["status"] == 3
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    finally:
        if rid:
            cleanup(owner_api, rid)


def test_guest_to_waiter_feedback_and_report(
    page: Page, base_url: str, api_url: str, owner_api: RestaurantApi, test_restaurant: dict
) -> None:
    reservation = create_reservation(owner_api, 3)
    rid = reservation["id"]
    token = owner_api.get_invite_token(rid)
    dish_id = test_restaurant["dish_ids"][0]
    dish = owner_api._request("GET", f"/dishes/{dish_id}")
    try:
        # Guest joins without an account, changes their basket, reloads and submits.
        page.goto(f"{base_url}/join/{token}")
        page.get_by_label("Your name").fill("Оксана")
        page.get_by_role("button", name="Join group", exact=True).click()
        add = page.get_by_role("button", name=f"Add {dish['name']}", exact=True)
        add.click()
        add.click()
        page.get_by_role("button", name=f"Remove one {dish['name']}", exact=True).click()
        page.reload()
        expect(page.locator(".guest-summary")).to_contain_text(f"1 × {dish['name']}")
        page.get_by_role("button", name="Submit Pre-Order", exact=True).click()
        expect(page.get_by_role("heading", name="Your pre-order has been submitted")).to_be_visible()
        owner_api._request(
            "POST",
            "/orders",
            json={"reservationId": rid, "orderItems": [{"dishId": test_restaurant["dish_ids"][1], "quantity": 1}]},
        )
        owner_api._request("POST", f"/orders/{rid}/submit")
        login(page, base_url, os.environ["CUSTOMER_EMAIL"], os.environ["CUSTOMER_PASSWORD"])
        review = GroupOrderPage(page, base_url)
        review.navigate(rid)
        review.click_submit()
        review.confirm_submit()
        expect(review.status_badge).to_have_text("Sent to Restaurant")
        assert len(owner_api.get_order(rid)["orderItems"]) == 2
        page.get_by_role("button", name="Logout", exact=True).click()
        login(page, base_url, test_restaurant["waiter_email"], test_restaurant["waiter_password"])
        page.goto(f"{base_url}/waiter-pre-order?reservationId={rid}")
        page.get_by_role("button", name=f"Confirm {dish['name']}", exact=True).click()
        expect(page.get_by_role("button", name=f"Confirm {dish['name']}", exact=True)).to_be_disabled()
        page.goto(f"{base_url}/waiter-reservations")
        card = page.locator(".reservation-card").filter(
            has=page.locator(f'a[href="/waiter-pre-order?reservationId={rid}"]')
        )
        card.get_by_role("button", name="Mark In Progress").click()
        card.get_by_role("button", name="Complete", exact=True).click()
        card.get_by_role("button", name="Feedback QR", exact=True).click()
        qr = page.get_by_role("dialog", name="Feedback QR Code")
        expect(qr.locator("code")).to_contain_text("token=")
        feedback_url = qr.locator("code").inner_text()
        qr.get_by_role("button", name="Close", exact=True).click()
        page.get_by_role("button", name="Logout", exact=True).click()
        page.goto(feedback_url)
        page.get_by_role("button", name="5 stars", exact=True).click()
        comment = "Дякуємо за уважне обслуговування!"
        page.get_by_label("Comment (optional)", exact=True).fill(comment)
        page.get_by_role("button", name="Submit Feedback", exact=True).click()
        expect(page.get_by_role("heading", name="Thank you!")).to_be_visible()
        page.goto(f"{base_url}/locations/{test_restaurant['location']['id']}")
        expect(page.get_by_text(comment, exact=True)).to_be_visible()
        login(page, base_url, os.environ["ADMIN_EMAIL"], os.environ["ADMIN_PASSWORD"])
        page.goto(f"{base_url}/reports")
        page.get_by_label("Location", exact=True).select_option(test_restaurant["location"]["id"])
        page.get_by_label("Start date", exact=True).fill((datetime.now(UTC) - timedelta(days=1)).date().isoformat())
        page.get_by_label("End date", exact=True).fill((datetime.now(UTC) + timedelta(days=90)).date().isoformat())
        page.get_by_role("button", name="Generate Report", exact=True).click()
        expect(page.get_by_role("heading", name="Generated report", exact=True)).to_be_visible()
        with page.expect_download() as download:
            page.get_by_role("button", name="Download", exact=True).click()
        assert download.value.suggested_filename.endswith(".csv")
        assert b"\n" in Path(download.value.path()).read_bytes()
    finally:
        cleanup(owner_api, rid)


def test_profile_photo_and_name_persist(logged_in_page: Page, base_url: str) -> None:
    page = logged_in_page
    page.goto(f"{base_url}/profile")
    first_name = page.get_by_label("First Name", exact=True)
    expect(first_name).not_to_have_value("")
    original = first_name.input_value()
    try:
        first_name.fill("Олена")
        page.get_by_role("button", name="Save Changes", exact=True).click()
        expect(page.get_by_text("Profile updated successfully!", exact=True)).to_be_visible()
        page.locator('input[type="file"]').set_input_files(PNG_UPLOAD)
        expect(page.get_by_text("Profile picture updated!", exact=True)).to_be_visible()
        expect(page.locator("img.avatar-img")).not_to_have_attribute("src", "/assets/img/avatar.png")
        page.reload()
        expect(first_name).to_have_value("Олена")
        expect(page.locator("img.avatar-img")).not_to_have_attribute("src", "/assets/img/avatar.png")
    finally:
        first_name.fill(original)
        page.get_by_role("button", name="Save Changes", exact=True).click()
