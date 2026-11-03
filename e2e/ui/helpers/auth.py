"""UI authentication helper."""

from __future__ import annotations

from playwright.sync_api import Page


def login(page: Page, base_url: str, email: str, password: str) -> None:
    """Open the app and sign in through the login modal."""
    page.goto(base_url)
    page.get_by_role("button", name="Sign In to Reserve").first.click()
    dialog = page.get_by_role("dialog", name="Sign In")
    dialog.locator("input[name='email']").fill(email)
    dialog.locator("input[name='password']").fill(password)
    dialog.get_by_role("button", name="Sign In", exact=True).click()
    dialog.wait_for(state="hidden", timeout=15_000)
