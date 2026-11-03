"""Page object for /reservations/{id}/group-order."""

from __future__ import annotations

import re

from playwright.sync_api import Locator, Page, expect


def _money(text: str) -> float:
    m = re.search(r"-?\d[\d,]*\.?\d*", text.replace(" ", " "))
    if not m:
        raise ValueError(f"No amount in {text!r}")
    return float(m.group(0).replace(",", ""))


class GroupOrderPage:
    def __init__(self, page: Page, base_url: str) -> None:
        self.page = page
        self.base_url = base_url.rstrip("/")
        self.cards = page.locator("article.participant-card")
        self.grand_total = page.locator(".grand-total__value")
        self.status_badge = page.locator(".status-badge")
        self.submit_button = page.locator("button.group-order__submit")

    def navigate(self, reservation_id: str) -> None:
        self.page.goto(f"{self.base_url}/reservations/{reservation_id}/group-order")
        expect(self.page.locator(".grand-total")).to_be_visible(timeout=20_000)

    def card(self, name: str) -> Locator:
        return self.cards.filter(has=self.page.locator(".participant-card__title", has_text=name))

    def get_participant_names(self) -> list[str]:
        titles = self.cards.locator(".participant-card__title").all_inner_texts()
        return [t.split(":", 1)[1].strip() if ":" in t else t.strip() for t in titles]

    def get_participant_items(self, name: str) -> list[str]:
        return self.card(name).locator(".dish-row__name").all_inner_texts()

    def get_grand_total(self) -> float:
        return _money(self.grand_total.inner_text())

    def get_participant_total(self, name: str) -> float:
        return _money(self.card(name).locator(".participant-card__subtotal span").last.inner_text())

    def click_submit(self) -> None:
        self.submit_button.click()

    def confirm_submit(self) -> None:
        dialog = self.page.get_by_role("dialog").filter(has_text="Submit Pre-Order")
        dialog.get_by_role("button", name="Submit", exact=True).click()

    def get_status_badge(self) -> str:
        expect(self.status_badge).to_be_visible()
        return self.status_badge.inner_text().strip()

    def is_submit_disabled(self) -> bool:
        return self.submit_button.is_disabled()

    def click_remove_guest(self, name: str) -> None:
        self.page.get_by_role("button", name=f"Remove {name}").click()

    def confirm_remove(self) -> None:
        dialog = self.page.get_by_role("dialog").filter(has_text="Are you sure you want to remove")
        dialog.get_by_role("button", name="Remove Guest").click()
