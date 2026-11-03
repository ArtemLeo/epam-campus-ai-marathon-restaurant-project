"""Account lifecycle and administrator forms against the running local application."""

from __future__ import annotations

import os

import pytest
from api.client import RestaurantApi
from playwright.sync_api import Page, expect

from ui.helpers.auth import login
from ui.fixtures import PNG_UPLOAD

pytestmark = pytest.mark.ui


def test_registration_password_change_and_recovery(page: Page, base_url: str, api_url: str, unique_id: str) -> None:
    email = f"aqa.account.{unique_id}@example.com"
    password, changed, recovered = "AqaFirst#2026", "AqaChanged#2026", "AqaReset#2026"
    page.goto(f"{base_url}/signup")
    for label, value in [
        ("First Name", "Олена"),
        ("Last Name", "Коваль"),
        ("Email", email),
        ("Password", password),
        ("Confirm Password", password),
    ]:
        page.get_by_label(label, exact=True).fill(value)
    page.get_by_role("button", name="Create Account", exact=True).click()
    dialog = page.get_by_role("dialog", name="Sign In")
    expect(dialog).to_be_visible()
    dialog.locator("input[name='email']").fill(email)
    dialog.locator("input[name='password']").fill(password)
    dialog.get_by_role("button", name="Sign In", exact=True).click()
    expect(dialog).to_have_count(0)
    page.goto(f"{base_url}/profile")
    expect(page.get_by_label("First Name", exact=True)).to_have_value("Олена")
    for label, value in [("Current Password", password), ("New Password", changed), ("Confirm New Password", changed)]:
        page.get_by_label(label, exact=True).fill(value)
    page.get_by_role("button", name="Update Password", exact=True).click()
    expect(page.get_by_text("Password updated successfully!", exact=True)).to_be_visible()
    page.get_by_role("button", name="Logout", exact=True).click()
    page.goto(f"{base_url}/forgot-password")
    page.get_by_label("Email", exact=True).fill(email)
    page.get_by_role("button", name="Send recovery code", exact=True).click()
    local_code = page.get_by_role("status").filter(has_text="Local demo recovery code:").locator("strong")
    expect(local_code).to_be_visible()
    page.get_by_label("Recovery code", exact=True).fill(local_code.inner_text())
    page.get_by_label("New password", exact=True).fill(recovered)
    page.get_by_label("Confirm new password", exact=True).fill(recovered)
    page.get_by_role("button", name="Save new password", exact=True).click()
    expect(page.get_by_text("Your password has been changed.", exact=False)).to_be_visible()
    login(page, base_url, email, recovered)
    page.goto(f"{base_url}/profile")
    expect(page.get_by_label("First Name", exact=True)).to_have_value("Олена")
    with RestaurantApi(api_url) as anonymous:
        assert anonymous.raw("POST", "/signin", json={"email": email, "password": changed}).status_code == 401


def test_admin_dish_table_and_waiter_forms(
    page: Page, base_url: str, api_url: str, admin_token: str, test_restaurant: dict, unique_id: str
) -> None:
    dish_id = table_id = None
    waiter_email = f"aqa.staff.{unique_id}@example.com"
    waiter_password = "AqaStaff#2026"
    location_id = test_restaurant["location"]["id"]
    address = test_restaurant["location"]["address"]
    dish_name = f"AQA страва {unique_id}"
    login(page, base_url, os.environ["ADMIN_EMAIL"], os.environ["ADMIN_PASSWORD"])
    page.goto(f"{base_url}/admin")
    with RestaurantApi(api_url, admin_token) as admin:
        try:
            page.locator("nav.tabs").get_by_role("button", name="Dishes", exact=True).click()
            page.get_by_role("button", name="+ Add Dish", exact=True).click()
            dialog = page.get_by_role("dialog", name="Add Dish")
            for label, value in [
                ("Name", dish_name),
                ("Description", "Страва для перевірки"),
                ("Price", "17.50"),
                ("Weight", "250 g"),
                ("Calories", "300 kcal"),
                ("Proteins", "10 g"),
                ("Fats", "12 g"),
                ("Carbohydrates", "30 g"),
                ("Vitamins", "A, C"),
            ]:
                dialog.get_by_label(label, exact=True).fill(value)
            dialog.get_by_label("Type", exact=True).select_option("MainCourse")
            dialog.get_by_role("checkbox", name=address, exact=True).check()
            dialog.get_by_label("Image", exact=True).set_input_files(PNG_UPLOAD)
            with page.expect_response(
                lambda response: response.url == f"{base_url}/api/dishes" and response.request.method == "POST"
            ) as created:
                dialog.get_by_role("button", name="Save", exact=True).click()
            assert created.value.status == 201
            dish_id = created.value.json()["id"]
            expect(dialog).to_have_count(0)
            card = page.locator("article.admin-card").filter(
                has=page.get_by_role("heading", name=dish_name, exact=True)
            )
            expect(card).to_contain_text("17.5")
            card.get_by_role("button", name="Edit", exact=True).click()
            dialog = page.get_by_role("dialog", name="Edit Dish")
            expect(dialog.get_by_role("checkbox", name=address, exact=True)).to_be_checked()
            expect(dialog.get_by_label("Type", exact=True)).to_have_value("MainCourse")
            dialog.get_by_label("Price", exact=True).fill("19.50")
            dialog.get_by_label("State", exact=True).select_option("OnStop")
            dialog.get_by_role("button", name="Save", exact=True).click()
            expect(dialog).to_have_count(0)
            expect(card).to_contain_text("19.5")
            page.once("dialog", lambda prompt: prompt.accept())
            card.get_by_role("button", name="Delete", exact=True).click()
            expect(card).to_have_count(0)

            page.locator("nav.tabs").get_by_role("button", name="Tables", exact=True).click()
            page.locator(".filter-row select").select_option(location_id)
            page.get_by_role("button", name="+ Add Table", exact=True).click()
            dialog = page.get_by_role("dialog", name="Add Table")
            dialog.get_by_label("Table Number", exact=True).fill("77")
            dialog.get_by_label("Capacity", exact=True).fill("3")
            with page.expect_response(
                lambda response: response.url == f"{base_url}/api/tables" and response.request.method == "POST"
            ) as created:
                dialog.get_by_role("button", name="Save", exact=True).click()
            assert created.value.status == 201
            table_id = created.value.json()["id"]
            expect(dialog).to_have_count(0)
            table = page.locator("article.admin-card").filter(
                has=page.get_by_role("heading", name="Table #77", exact=True)
            )
            expect(table).to_contain_text("3 seats")
            table.get_by_role("button", name="Edit", exact=True).click()
            dialog = page.get_by_role("dialog", name="Edit Table")
            dialog.get_by_label("Capacity", exact=True).fill("5")
            dialog.get_by_role("button", name="Save", exact=True).click()
            expect(dialog).to_have_count(0)
            expect(table).to_contain_text("5 seats")
            page.once("dialog", lambda prompt: prompt.accept())
            table.get_by_role("button", name="Delete", exact=True).click()
            expect(table).to_have_count(0)

            admin._request(
                "POST",
                "/register",
                json={
                    "firstName": "Aqa",
                    "lastName": "Staff",
                    "email": waiter_email,
                    "password": waiter_password,
                    "confirmPassword": waiter_password,
                },
            )
            page.locator("nav.tabs").get_by_role("button", name="Waiters", exact=True).click()
            page.locator(".filter-row select").select_option(location_id)
            page.get_by_role("button", name="+ Add Waiter", exact=True).click()
            dialog = page.get_by_role("dialog", name="Add Waiter")
            dialog.get_by_label("Email (must be a registered user)", exact=True).fill(waiter_email)
            dialog.get_by_role("button", name="Add Waiter", exact=True).click()
            expect(dialog).to_have_count(0)
            row = page.locator("article.admin-card").filter(has_text=waiter_email)
            expect(row).to_be_visible()
            page.once("dialog", lambda prompt: prompt.accept())
            row.get_by_role("button", name="Remove", exact=True).click()
            expect(row).to_have_count(0)
        finally:
            admin.raw("DELETE", "/waiters", json={"email": waiter_email})
            if table_id:
                admin.raw("DELETE", f"/tables/{table_id}")
            if dish_id:
                admin.raw("DELETE", f"/dishes/{dish_id}", params={"force": "true"})
