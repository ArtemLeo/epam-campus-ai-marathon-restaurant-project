"""Level 1: owner views group participants."""

import pytest

from api.helpers import Env, dish_id, items_of, parts_by_name, pick, qty_by_dish

pytestmark = [pytest.mark.api, pytest.mark.level1]


@pytest.fixture
def env(api_url):
    e = Env(api_url)
    yield e
    e.close()


@pytest.fixture
def group(env, customer_token):
    """Reservation + group with no guests yet."""
    res = env.create_reservation(customer_token, guests=3)
    rid = pick(res, "id", "reservationId")
    gid = env.group_id_for(customer_token, rid)
    yield {"reservation_id": rid, "group_id": gid}
    env.cancel_reservation(customer_token, rid)


def _guest(env, group, name):
    sid, tok = env.join(group["group_id"], name)
    return sid, tok


def _total(body):
    return float(pick(body, "total", default=0) or 0)


def test_owner_sees_all_participants(env, group, customer_token, unique_id):
    ds = env.dishes(customer_token, 3)
    a, b = f"A{unique_id}", f"B{unique_id}"
    sa, ta = _guest(env, group, a)
    sb, tb = _guest(env, group, b)
    env.add_dish(sa, ta, dish_id(ds[0]), 2)
    env.add_dish(sa, ta, dish_id(ds[1]), 1)
    env.add_dish(sb, tb, dish_id(ds[2]), 3)
    env.submit_guest(sa, ta)
    env.submit_guest(sb, tb)

    r = env.participants(customer_token, group["group_id"])
    assert r.status_code == 200, r.text
    parts = parts_by_name(r.json())
    assert set(parts) >= {a, b} and len(parts) == 3
    assert sum(p["type"] == "Owner" for p in parts.values()) == 1
    assert qty_by_dish(items_of(parts[a])) == {dish_id(ds[0]): 2, dish_id(ds[1]): 1}
    assert qty_by_dish(items_of(parts[b])) == {dish_id(ds[2]): 3}
    assert pick(parts[a], "isSubmitted") is True
    assert pick(parts[b], "isSubmitted") is True


def test_total_equals_sum_of_participants(env, group, customer_token, unique_id):
    ds = env.dishes(customer_token, 2)
    sa, ta = _guest(env, group, f"A{unique_id}")
    sb, tb = _guest(env, group, f"B{unique_id}")
    env.add_dish(sa, ta, dish_id(ds[0]), 2)
    env.add_dish(sb, tb, dish_id(ds[1]), 1)
    env.submit_guest(sa, ta)

    body = env.participants(customer_token, group["group_id"]).json()
    parts = pick(body, "participants")
    assert len(parts) == 3
    s = sum(float(pick(p, "total", "subtotal", default=0) or 0) for p in parts)
    assert _total(body) == pytest.approx(s)
    assert _total(body) > 0


def test_unsubmitted_guest_shown_with_flag(env, group, customer_token, unique_id):
    ds = env.dishes(customer_token, 2)
    a, b = f"A{unique_id}", f"B{unique_id}"
    sa, ta = _guest(env, group, a)
    sb, tb = _guest(env, group, b)
    env.add_dish(sa, ta, dish_id(ds[0]), 1)
    env.add_dish(sb, tb, dish_id(ds[1]), 1)
    env.submit_guest(sa, ta)

    parts = parts_by_name(env.participants(customer_token, group["group_id"]).json())
    assert pick(parts[a], "isSubmitted") is True
    assert pick(parts[b], "isSubmitted") is False
    assert qty_by_dish(items_of(parts[b])) == {dish_id(ds[1]): 1}


def test_empty_cart_participant(env, group, customer_token, unique_id):
    name = f"E{unique_id}"
    _guest(env, group, name)
    r = env.participants(customer_token, group["group_id"])
    assert r.status_code == 200, r.text
    parts = parts_by_name(r.json())
    assert name in parts
    assert items_of(parts[name]) == []
    assert pick(parts[name], "isSubmitted") is False
    assert _total(r.json()) == 0


def test_empty_group_contains_owner_with_empty_cart(env, group, customer_token):
    r = env.participants(customer_token, group["group_id"])
    assert r.status_code == 200, r.text
    participants = r.json()["participants"]
    assert len(participants) == 1
    assert participants[0]["type"] == "Owner"
    assert participants[0]["items"] == []
    assert _total(r.json()) == 0


def test_only_owner_can_view(env, group, customer_token, unique_id):
    _, guest_tok = _guest(env, group, f"G{unique_id}")
    other = env.new_customer_token(unique_id)
    gid = group["group_id"]
    assert env.participants(other, gid).status_code == 403
    # Guest-session credentials are not account JWTs.
    assert env.participants(guest_tok, gid).status_code == 401
    assert env.participants(None, gid).status_code == 401


def test_nonexistent_group(env, customer_token):
    r = env.participants(customer_token, "00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404, r.text


def test_total_updates_when_guest_changes_cart(env, group, customer_token, unique_id):
    ds = env.dishes(customer_token, 2)
    name = f"A{unique_id}"
    sa, ta = _guest(env, group, name)
    env.add_dish(sa, ta, dish_id(ds[0]), 1)
    before = _total(env.participants(customer_token, group["group_id"]).json())
    assert before > 0

    env.add_dish(sa, ta, dish_id(ds[1]), 2)
    body = env.participants(customer_token, group["group_id"]).json()
    assert _total(body) > before
    assert qty_by_dish(items_of(parts_by_name(body)[name])) == {dish_id(ds[0]): 1, dish_id(ds[1]): 2}
