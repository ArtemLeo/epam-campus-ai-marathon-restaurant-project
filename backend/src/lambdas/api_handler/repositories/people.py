"""Cognito users plus the waiters, feedback, notifications and profile images tables."""

from __future__ import annotations

from typing import Any

from core import aws, config, dynamo

Item = dict[str, Any]


# --- Cognito users ---------------------------------------------------------


def attributes(user: Item | None) -> dict[str, str]:
    if not user:
        return {}
    raw = user.get("Attributes") or user.get("UserAttributes") or []
    return {a["Name"]: a["Value"] for a in raw}


def user_by_email(email: str) -> Item | None:
    client = aws.cognito()
    try:
        return client.admin_get_user(UserPoolId=config.user_pool_id(), Username=email.strip().lower())
    except client.exceptions.UserNotFoundException:
        return None


def user_by_id(user_id: str) -> Item | None:
    if not user_id or '"' in user_id:
        return None
    response = aws.cognito().list_users(UserPoolId=config.user_pool_id(), Filter=f'sub = "{user_id}"', Limit=1)
    users = response.get("Users") or []
    return users[0] if users else None


def users_by_given_name_prefix(prefix: str) -> list[Item]:
    users: list[Item] = []
    kwargs: dict[str, Any] = {
        "UserPoolId": config.user_pool_id(),
        "Filter": f'given_name ^= "{prefix.replace(chr(34), "")}"',
        "Limit": 60,
    }
    while True:
        response = aws.cognito().list_users(**kwargs)
        users.extend(response.get("Users") or [])
        token = response.get("PaginationToken")
        if not token:
            return users
        kwargs["PaginationToken"] = token


def users_in_group(group: str) -> list[Item]:
    users: list[Item] = []
    kwargs: dict[str, Any] = {"UserPoolId": config.user_pool_id(), "GroupName": group, "Limit": 60}
    client = aws.cognito()
    while True:
        try:
            response = client.list_users_in_group(**kwargs)
        except client.exceptions.ResourceNotFoundException:
            return users
        users.extend(response.get("Users") or [])
        token = response.get("NextToken")
        if not token:
            return users
        kwargs["NextToken"] = token


def groups_of(username: str) -> list[str]:
    response = aws.cognito().admin_list_groups_for_user(UserPoolId=config.user_pool_id(), Username=username)
    return [g["GroupName"] for g in response.get("Groups", [])]


def ensure_group(group: str) -> None:
    client = aws.cognito()
    try:
        client.get_group(UserPoolId=config.user_pool_id(), GroupName=group)
    except client.exceptions.ResourceNotFoundException:
        client.create_group(UserPoolId=config.user_pool_id(), GroupName=group, Description=f"Group for role {group}")


def add_to_group(username: str, group: str) -> None:
    aws.cognito().admin_add_user_to_group(UserPoolId=config.user_pool_id(), Username=username, GroupName=group)


def remove_from_group(username: str, group: str) -> None:
    aws.cognito().admin_remove_user_from_group(UserPoolId=config.user_pool_id(), Username=username, GroupName=group)


def update_attributes(username: str, values: dict[str, str]) -> None:
    aws.cognito().admin_update_user_attributes(
        UserPoolId=config.user_pool_id(),
        Username=username,
        UserAttributes=[{"Name": k, "Value": v} for k, v in values.items()],
    )


def full_name(user_id: str | None) -> str | None:
    """``"First Last"`` for a Cognito user id; None when unknown."""
    if not user_id:
        return None
    try:
        attrs = attributes(user_by_id(user_id))
    except Exception:  # a name lookup must never break the main response
        return None
    name = f"{attrs.get('given_name', '')} {attrs.get('family_name', '')}".strip()
    return name or None


# --- Waiters ---------------------------------------------------------------


def get_waiter(user_id: str) -> Item | None:
    return dynamo.get_item("waiters", {"userId": user_id})


def waiters_by_location(location_id: str) -> list[Item]:
    return dynamo.query_index("waiters", "waiters_by_location", "locationId", location_id)


def all_waiters() -> list[Item]:
    return dynamo.scan_all("waiters")


def save_waiter(waiter: Item) -> None:
    dynamo.put_item("waiters", waiter)


def delete_waiter(user_id: str) -> None:
    dynamo.delete_item("waiters", {"userId": user_id})


# --- Feedback --------------------------------------------------------------


def feedback_by_reservation(reservation_id: str) -> list[Item]:
    return dynamo.query_partition("feedback", "reservationId", reservation_id)


def feedback_by_location(location_id: str) -> list[Item]:
    return dynamo.query_index("feedback", "feedback_by_location", "locationId", location_id)


def save_feedback(feedback: Item) -> None:
    dynamo.put_item("feedback", feedback)


# --- Notifications ---------------------------------------------------------


def get_notification(notification_id: str) -> Item | None:
    return dynamo.get_item("notifications", {"id": notification_id})


def notifications_by_user(user_id: str) -> list[Item]:
    return dynamo.query_index("notifications", "notifications_by_user", "userId", user_id)


def save_notification(notification: Item) -> None:
    dynamo.put_item("notifications", notification)


# --- Profile images --------------------------------------------------------


def get_profile_image(user_id: str) -> Item | None:
    return dynamo.get_item("profile_images", {"userId": user_id})


def save_profile_image(user_id: str, image_key: str) -> None:
    dynamo.put_item("profile_images", {"userId": user_id, "imageKey": image_key})
