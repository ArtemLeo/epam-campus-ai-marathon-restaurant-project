"""Waiter list: which registered users serve which location, and their reservation load."""

from __future__ import annotations

from typing import Any

from botocore.exceptions import ClientError

from core import auth, aws, dynamo, timeutils
from core.enums import ReservationStatus, stored_enum
from core.errors import BadRequest, Conflict, NotFound
from core.validation import validate_email
from repositories import bookings, catalog, people

Item = dict[str, Any]


def _user_id_for(email: str) -> str | None:
    return people.attributes(people.user_by_email(email)).get("sub")


def add_waiter(email: Any, location_id: Any) -> None:
    email = validate_email(email).strip().lower()
    user_id = _user_id_for(email)
    if user_id and people.get_waiter(user_id):
        raise Conflict("This user is already added to the waiters list")
    if not isinstance(location_id, str) or not catalog.get_location(location_id):
        raise NotFound(f"Location with ID {location_id} does not exist.")
    if not user_id:
        raise NotFound(f"User with email {email} is not registered")
    people.save_waiter(
        {
            "userId": user_id,
            "locationId": location_id,
            "createdAt": timeutils.iso(timeutils.utcnow()),
            "reservations": [],
        }
    )
    people.ensure_group(auth.WAITER)
    people.add_to_group(email, auth.WAITER)


def remove_waiter(email: Any) -> None:
    email = validate_email(email).strip().lower()
    user_id = _user_id_for(email)
    waiter = people.get_waiter(user_id) if user_id else None
    if not waiter:
        raise NotFound("Email not found")
    if any(
        stored_enum(ReservationStatus, r.get("status"), ReservationStatus.Reserved)
        in (ReservationStatus.Reserved, ReservationStatus.InProgress)
        for r in bookings.all_reservations()
        if r.get("waiterId") == user_id
    ):
        raise Conflict("This waiter has active reservations. Complete or cancel them before removing the assignment.")
    dynamo.transaction([dynamo.delete_action("waiters", {"userId": user_id}, waiter)])
    people.remove_from_group(email, auth.WAITER)


def remove_waiter_by_id(user_id: str) -> None:
    if not people.get_waiter(user_id):
        return
    people.delete_waiter(user_id)
    email = people.attributes(people.user_by_id(user_id)).get("email")
    if email:
        people.remove_from_group(email, auth.WAITER)


def waiter_location(user_id: str) -> str:
    waiter = people.get_waiter(user_id)
    if not waiter:
        raise NotFound(f"No location found for waiter with ID {user_id}")
    return waiter["locationId"]


def require_waiter(user_id: str) -> Item:
    waiter = people.get_waiter(user_id)
    if not waiter:
        raise BadRequest(f"Waiter with userId '{user_id}' not found.")
    return waiter


def least_busy_waiter(location_id: str) -> Item:
    waiters = people.waiters_by_location(location_id)
    if not waiters:
        raise BadRequest(f"No waiters found for location ID {location_id}.")

    def active_count(waiter: Item) -> int:
        return sum(
            stored_enum(ReservationStatus, r.get("status"), ReservationStatus.Reserved)
            in (ReservationStatus.Reserved, ReservationStatus.InProgress)
            and timeutils.parse_datetime(r["endTime"]) > timeutils.utcnow()
            for r in bookings.reservations_by_waiter(waiter["userId"])
        )

    return min(waiters, key=active_count)


def assign_reservation(waiter_id: str, reservation_id: str) -> None:
    require_waiter(waiter_id)
    aws.table("waiters").update_item(
        Key={"userId": waiter_id},
        UpdateExpression="SET reservations = list_append(if_not_exists(reservations, :empty), :value), #v = if_not_exists(#v, :zero) + :one",
        ConditionExpression="attribute_exists(userId)",
        ExpressionAttributeNames={"#v": "version"},
        ExpressionAttributeValues={":empty": [], ":value": [reservation_id], ":zero": 0, ":one": 1},
    )


def release_reservation(reservation_id: str) -> None:
    for waiter in people.all_waiters():
        for attempt in range(5):
            current = people.get_waiter(waiter["userId"]) or {}
            assigned = list(current.get("reservations") or [])
            if reservation_id not in assigned:
                break
            index = assigned.index(reservation_id)
            try:
                aws.table("waiters").update_item(
                    Key={"userId": waiter["userId"]},
                    UpdateExpression=f"SET #v = if_not_exists(#v, :zero) + :one REMOVE reservations[{index}]",
                    ConditionExpression=f"reservations[{index}] = :id",
                    ExpressionAttributeNames={"#v": "version"},
                    ExpressionAttributeValues={":id": reservation_id, ":zero": 0, ":one": 1},
                )
                break
            except ClientError as exc:
                if exc.response["Error"]["Code"] != "ConditionalCheckFailedException" or attempt == 4:
                    raise


def list_waiters(location_id: str | None = None) -> list[Item]:
    found = people.waiters_by_location(location_id) if location_id else people.all_waiters()
    result = []
    for waiter in found:
        attrs = people.attributes(people.user_by_id(waiter["userId"]))
        result.append(
            {
                "userId": waiter["userId"],
                "locationId": waiter["locationId"],
                "email": attrs.get("email", ""),
                "firstName": attrs.get("given_name", ""),
                "lastName": attrs.get("family_name", ""),
            }
        )
    return sorted(result, key=lambda row: (row["firstName"], row["lastName"]))
