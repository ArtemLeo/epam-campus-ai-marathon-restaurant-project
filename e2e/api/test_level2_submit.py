"""Level 2: owner submits consolidated group pre-order."""

import pytest

from api.helpers import Env, dish_id, pick, qty_by_dish

pytestmark = [pytest.mark.api, pytest.mark.level2]

SUBMITTED_BY_CUSTOMER = 3
NO_GROUP = "00000000-0000-0000-0000-000000000000"


@pytest.fixture
def env(api_url):
    e = Env(api_url)
    yield e
    e.close()


@pytest.fixture
def ctx(env, customer_token):
    """Reservation + group (no order yet) + dishes."""
    res = env.create_reservation(customer_token, guests=3)
    rid = pick(res, "id", "reservationId")
    gid = env.group_id_for(customer_token, rid)
    yield {"rid": rid, "gid": gid, "dishes": env.dishes(customer_token, 4)}
    env.cancel_reservation(customer_token, rid)


def _submit(env, token, ctx):
    return env.req("POST", f"/group-reservations/{ctx['gid']}/submit", token, json={"reservationId": ctx["rid"]})


def _owner_order(env, token, ctx):
    d = ctx["dishes"]
    env.create_order(token, ctx["rid"], [(dish_id(d[3]), 1)])


def _result_items(resp):
    body = resp.json()
    if isinstance(body, list):
        return body
    return pick(body, "items", "orderItems", "consolidatedItems", default=[])


def _guest_cart(env, ctx, name, picks, submit=True):
    sid, tok = env.join(ctx["gid"], name)
    for idx, qty in picks:
        env.add_dish(sid, tok, dish_id(ctx["dishes"][idx]), qty)
    if submit:
        env.submit_guest(sid, tok)
    return sid, tok


def test_successful_submit(env, ctx, customer_token, unique_id):
    d = ctx["dishes"]
    _owner_order(env, customer_token, ctx)
    _guest_cart(env, ctx, f"A{unique_id}", [(0, 2), (1, 1)])
    _guest_cart(env, ctx, f"B{unique_id}", [(0, 3), (2, 1)])
    r = _submit(env, customer_token, ctx)
    assert r.status_code == 200, r.text
    got = qty_by_dish(_result_items(r))
    assert got[dish_id(d[0])] == 5  # merged 2 + 3
    assert got[dish_id(d[1])] == 1
    assert got[dish_id(d[2])] == 1


def test_unsubmitted_carts_excluded(env, ctx, customer_token, unique_id):
    d = ctx["dishes"]
    _owner_order(env, customer_token, ctx)
    _guest_cart(env, ctx, f"A{unique_id}", [(0, 2)])
    _guest_cart(env, ctx, f"B{unique_id}", [(1, 4)], submit=False)
    r = _submit(env, customer_token, ctx)
    assert r.status_code == 200, r.text
    got = qty_by_dish(_result_items(r))
    assert got.get(dish_id(d[0])) == 2
    assert dish_id(d[1]) not in got


def test_order_status_after_submit(env, ctx, customer_token, unique_id):
    _owner_order(env, customer_token, ctx)
    _guest_cart(env, ctx, f"A{unique_id}", [(0, 1)])
    assert _submit(env, customer_token, ctx).status_code == 200
    r = env.req("GET", f"/orders/{ctx['rid']}", customer_token)
    assert r.status_code == 200, r.text
    assert pick(r.json(), "status") == SUBMITTED_BY_CUSTOMER


def test_group_status_after_submit(env, ctx, customer_token, unique_id):
    _owner_order(env, customer_token, ctx)
    _guest_cart(env, ctx, f"A{unique_id}", [(0, 1)])
    assert _submit(env, customer_token, ctx).status_code == 200
    r = env.req("GET", f"/guest/groups/{ctx['gid']}/status")
    assert r.status_code == 200, r.text
    assert str(pick(r.json(), "status")).lower() == "submitted"


def test_waiter_sees_submitted_order(env, ctx, customer_token, waiter_token, unique_id):
    d = ctx["dishes"]
    _owner_order(env, customer_token, ctx)
    _guest_cart(env, ctx, f"A{unique_id}", [(0, 2)])
    assert _submit(env, customer_token, ctx).status_code == 200
    r = env.req("GET", f"/orders/{ctx['rid']}", waiter_token)
    assert r.status_code == 200, r.text
    items = pick(r.json(), "orderItems", "items", default=[])
    assert qty_by_dish(items).get(dish_id(d[0])) == 2


def test_no_submitted_carts_error(env, ctx, customer_token, unique_id):
    _owner_order(env, customer_token, ctx)
    _guest_cart(env, ctx, f"A{unique_id}", [(0, 1)], submit=False)
    _guest_cart(env, ctx, f"B{unique_id}", [(1, 1)], submit=False)
    assert _submit(env, customer_token, ctx).status_code == 400


def test_no_dishes_error(env, ctx, customer_token, unique_id):
    _owner_order(env, customer_token, ctx)
    session_id, token = _guest_cart(env, ctx, f"A{unique_id}", [], submit=False)
    response = env.req("POST", f"/guest/sessions/{session_id}/submit", token)
    assert response.status_code == 400
    assert _submit(env, customer_token, ctx).status_code == 400


def test_guests_can_order_when_owner_has_no_dishes(env, ctx, customer_token, unique_id):
    # The host may join the meal without pre-ordering a dish themselves.
    _guest_cart(env, ctx, f"A{unique_id}", [(0, 1)])
    response = _submit(env, customer_token, ctx)
    assert response.status_code == 200, response.text
    assert qty_by_dish(_result_items(response)) == {dish_id(ctx["dishes"][0]): 1}


def test_nonexistent_group_error(env, ctx, customer_token):
    r = env.req("POST", f"/group-reservations/{NO_GROUP}/submit", customer_token, json={"reservationId": ctx["rid"]})
    assert r.status_code == 404, r.text


def test_double_submit_error(env, ctx, customer_token, unique_id):
    _owner_order(env, customer_token, ctx)
    _guest_cart(env, ctx, f"A{unique_id}", [(0, 1)])
    assert _submit(env, customer_token, ctx).status_code == 200
    assert _submit(env, customer_token, ctx).status_code == 400


def test_non_owner_cannot_submit(env, ctx, customer_token, unique_id):
    _owner_order(env, customer_token, ctx)
    _guest_cart(env, ctx, f"A{unique_id}", [(0, 1)])
    other = env.new_customer_token(unique_id)
    assert _submit(env, other, ctx).status_code == 403
