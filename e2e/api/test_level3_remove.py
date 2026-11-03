"""Level 3: owner removes a guest from the group pre-order."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from api.client import RestaurantApi
from api.flow import Group, build_group, cleanup, unique_name

pytestmark = [pytest.mark.api, pytest.mark.level3]


@pytest.fixture
def owner(api_url: str, customer_token: str) -> Iterator[RestaurantApi]:
    with RestaurantApi(api_url, customer_token) as api:
        yield api


@pytest.fixture
def group(owner: RestaurantApi) -> Iterator[Group]:
    """Group with 3 guests, each with a dish; guest #2 has submitted the cart."""
    g = build_group(owner, [unique_name("A"), unique_name("B"), unique_name("C")], submit_carts=(False, True, False))
    yield g
    cleanup(owner, g.reservation_id)


def _ids(snapshot: dict) -> list[str]:
    return [p["id"] for p in snapshot["participants"]]


def _sum(snapshot: dict) -> float:
    return round(sum(p["total"] for p in snapshot["participants"]), 2)


def test_remove_one_guest_others_remain(owner: RestaurantApi, group: Group) -> None:
    before = owner.get_group_sessions(group.group_id)
    removed = group.guests[0]
    result = owner.remove_guest_session(group.group_id, removed.session_id)

    assert removed.session_id not in _ids(result)
    assert {g.session_id for g in group.guests[1:]} <= set(_ids(result))
    assert len(result["participants"]) == len(before["participants"]) - 1
    assert result["total"] == pytest.approx(before["total"] - removed.total)
    assert result["total"] == pytest.approx(_sum(result))


def test_remove_submitted_guest(owner: RestaurantApi, group: Group) -> None:
    submitted = group.guests[1]
    assert submitted.submitted
    before = owner.get_group_sessions(group.group_id)
    result = owner.remove_guest_session(group.group_id, submitted.session_id)

    assert submitted.session_id not in _ids(result)
    assert result["total"] == pytest.approx(before["total"] - submitted.total)
    assert result["total"] < before["total"]


def test_remove_last_guest(owner: RestaurantApi, group: Group) -> None:
    result = {}
    for g in group.guests:
        result = owner.remove_guest_session(group.group_id, g.session_id)

    assert _ids(result) == [group.owner_session_id]
    assert result["participants"][0]["type"] == "Owner"
    assert result["total"] == pytest.approx(result["participants"][0]["total"])
    assert owner.get_group_sessions(group.group_id) == result


def test_cross_group_guest_error(owner: RestaurantApi, group: Group) -> None:
    other = build_group(owner, [unique_name("X")])
    try:
        resp = owner.raw("DELETE", f"/guest/groups/{group.group_id}/sessions/{other.guests[0].session_id}")
        assert resp.status_code == 400
        # the guest of the other group is untouched
        assert other.guests[0].session_id in _ids(owner.get_group_sessions(other.group_id))
    finally:
        cleanup(owner, other.reservation_id)


def test_nonexistent_session_error(owner: RestaurantApi, group: Group) -> None:
    resp = owner.raw("DELETE", f"/guest/groups/{group.group_id}/sessions/gs-does-not-exist-{unique_name()}")
    assert resp.status_code == 404


def test_non_owner_cannot_remove(api_url: str, group: Group) -> None:
    import os

    email, password = os.getenv("GUEST_EMAIL"), os.getenv("GUEST_PASSWORD")
    if not email or not password:
        pytest.skip("GUEST_EMAIL / GUEST_PASSWORD not set")
    with RestaurantApi(api_url) as other:
        other.token = str(other.signin(email, password)["idToken"])
        resp = other.raw("DELETE", f"/guest/groups/{group.group_id}/sessions/{group.guests[0].session_id}")
    assert resp.status_code == 403


def test_end_to_end_flow(owner: RestaurantApi, waiter_token: str, api_url: str) -> None:
    g = build_group(owner, [unique_name("E1"), unique_name("E2"), unique_name("E3")], submit_carts=(True, True, True))
    try:
        review = owner.get_group_sessions(g.group_id)
        assert len(review["participants"]) == 4

        removed = g.guests[1]
        after = owner.remove_guest_session(g.group_id, removed.session_id)
        assert removed.session_id not in _ids(after)

        owner.submit_group_preorder(g.group_id, g.reservation_id)

        with RestaurantApi(api_url, waiter_token) as waiter:
            order = waiter.get_order(g.reservation_id)
        items = {
            (i["dish"]["id"] if isinstance(i.get("dish"), dict) else i.get("dishId") or i.get("dish")): i["quantity"]
            for i in order["orderItems"]
        }
        kept = g.guests[0], g.guests[2]
        for guest in kept:
            dish, _ = guest.dishes[0]
            assert dish["id"] in items
        # a dish only the removed guest ordered must not be in the order
        others = {d["id"] for guest in kept for d, _ in guest.dishes} | {g.owner_dish["id"]}
        removed_dish = removed.dishes[0][0]["id"]
        if removed_dish not in others:
            assert removed_dish not in items
        else:
            expected = sum(q for guest in kept for d, q in guest.dishes if d["id"] == removed_dish)
            expected += 1 if g.owner_dish["id"] == removed_dish else 0
            assert items[removed_dish] == expected
    finally:
        cleanup(owner, g.reservation_id)
