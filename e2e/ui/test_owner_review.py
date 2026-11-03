"""Owner review of the group pre-order in the browser."""

from __future__ import annotations

import pytest
from api.client import RestaurantApi
from playwright.sync_api import Page, expect

from ui.pages.group_order_page import GroupOrderPage


@pytest.fixture
def order_page(logged_in_page: Page, base_url: str) -> GroupOrderPage:
    return GroupOrderPage(logged_in_page, base_url)


@pytest.mark.ui
@pytest.mark.level1
def test_owner_sees_participants_ui(order_page: GroupOrderPage, setup_group: dict) -> None:
    order_page.navigate(setup_group["reservation_id"])
    names = order_page.get_participant_names()
    for guest in setup_group["guest_sessions"]:
        assert guest.name in names
        assert order_page.get_participant_total(guest.name) == pytest.approx(guest.total)
        dish_names = order_page.get_participant_items(guest.name)
        assert guest.dishes[0][0]["name"] in dish_names
    assert len(names) == len(setup_group["guest_sessions"]) + 1


@pytest.mark.ui
@pytest.mark.level1
def test_grand_total_displayed(order_page: GroupOrderPage, setup_group: dict) -> None:
    order_page.navigate(setup_group["reservation_id"])
    # Grand Total = submitted carts (owner's order included once submitted by the backend rules)
    submitted = sum(g.total for g in setup_group["guest_sessions"] if g.submitted)
    assert order_page.get_grand_total() >= submitted
    shown = sum(order_page.get_participant_total(g.name) for g in setup_group["guest_sessions"] if g.submitted)
    assert shown == pytest.approx(submitted)


@pytest.mark.ui
@pytest.mark.level2
def test_submit_preorder_ui(order_page: GroupOrderPage, setup_group: dict) -> None:
    order_page.navigate(setup_group["reservation_id"])
    order_page.click_submit()
    order_page.confirm_submit()
    expect(order_page.status_badge).to_have_text("Sent to Restaurant", timeout=15_000)
    assert order_page.is_submit_disabled()


@pytest.mark.ui
@pytest.mark.level2
def test_submit_disabled_no_submitted_carts(
    order_page: GroupOrderPage, owner_api: RestaurantApi, setup_group: dict
) -> None:
    from api.flow import build_group, cleanup, unique_name

    group = build_group(owner_api, [unique_name("Dan"), unique_name("Eve")], guest_count=3, submit_carts=(False, False))
    try:
        order_page.navigate(group.reservation_id)
        assert order_page.is_submit_disabled()
    finally:
        cleanup(owner_api, group.reservation_id)


@pytest.mark.ui
@pytest.mark.level3
def test_remove_guest_ui(order_page: GroupOrderPage, setup_group: dict) -> None:
    order_page.navigate(setup_group["reservation_id"])
    victim = setup_group["guest_sessions"][0]
    before = order_page.get_grand_total()
    order_page.click_remove_guest(victim.name)
    order_page.confirm_remove()
    expect(order_page.page.get_by_text(f"Guest: {victim.name}")).to_have_count(0, timeout=15_000)
    assert victim.name not in order_page.get_participant_names()
    # victim submitted its cart, so the consolidated total drops by its subtotal
    assert order_page.get_grand_total() == pytest.approx(before - victim.total)
