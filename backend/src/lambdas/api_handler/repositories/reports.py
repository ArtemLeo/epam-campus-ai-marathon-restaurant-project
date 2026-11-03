"""Daily waiter aggregates (Reports table) and generated report history (ReportsHistory table)."""

from __future__ import annotations

from typing import Any

from boto3.dynamodb.conditions import Attr

from core import dynamo

Item = dict[str, Any]


def aggregates_between(start_iso: str, end_iso: str, location_id: str | None = None) -> list[Item]:
    condition = Attr("date").between(start_iso, end_iso)
    if location_id:
        condition = condition & Attr("locationId").eq(location_id)
    return dynamo.scan_all("reports", FilterExpression=condition, ConsistentRead=True)


def history_by_user(user_id: str) -> list[Item]:
    return dynamo.query_index("reports_history", "reports_history_by_user", "userId", user_id)


def save_history(item: Item) -> None:
    dynamo.put_item("reports_history", item)
