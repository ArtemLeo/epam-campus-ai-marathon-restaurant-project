"""Reports Handler Lambda (SQS consumer).

Folds every completed reservation published by the API into the waiter's daily aggregate
(Reports table, key: waiterId + date). Ratings of 0 mean "not rated" and do not affect averages.
Malformed messages are dropped; transient failures are retried through partial batch responses.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import os
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger("reports_handler")
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO").upper())

UTC = dt.timezone.utc
KINDS = ("Service", "Cuisine")


class InvalidReport(ValueError):
    """The message can never be processed; retrying would not help."""


def _table() -> Any:
    region = os.environ.get("AwsRegion") or os.environ.get("AWS_REGION", "eu-north-1")
    return boto3.resource("dynamodb", region_name=region).Table(os.environ.get("ReportsTableName", "Reports"))


def _parse_time(value: Any) -> dt.datetime:
    if not isinstance(value, str) or not value:
        raise InvalidReport("missing timestamp")
    parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)


def parse_report(body: str) -> dict[str, Any]:
    try:
        data = json.loads(body)
        report = {
            "reservationId": str(data["ReservationId"]),
            "revision": int(data.get("Revision", 1)),
            "waiterId": str(data.get("WaiterId") or ""),
            "locationId": str(data.get("LocationId") or ""),
            "start": _parse_time(data.get("ReservationStart")),
            "end": _parse_time(data.get("ReservationEnd")),
            "Service": int(data.get("ServiceRating") or 0),
            "Cuisine": int(data.get("CuisineRating") or 0),
            "revenue": Decimal(str(data.get("Revenue") or 0)),
        }
    except (ValueError, KeyError, TypeError) as exc:
        raise InvalidReport(f"malformed message: {exc}") from exc
    if not report["waiterId"] or not report["locationId"] or report["end"] <= report["start"]:
        raise InvalidReport("waiter, location and a positive duration are required")
    if not all(0 <= report[kind] <= 5 for kind in KINDS) or not report["revenue"].is_finite() or report["revenue"] < 0:
        raise InvalidReport("ratings must be 0..5 and revenue non-negative")
    return report


def _day(moment: dt.datetime) -> str:
    local = moment.astimezone(ZoneInfo(os.environ.get("RESTAURANT_TIMEZONE", "UTC")))
    return local.strftime("%Y-%m-%dT00:00:00.000Z")


def apply_report(aggregate: dict[str, Any] | None, report: dict[str, Any]) -> dict[str, Any] | None:
    """Latest revision per visit; duplicate/out-of-order messages cannot change totals."""
    aggregate = dict(aggregate or {"waiterId": report["waiterId"], "date": _day(report["start"])})
    visits = dict(aggregate.get("visits") or {})
    previous = visits.get(report["reservationId"])
    if previous and int(previous["revision"]) >= report["revision"]:
        return None
    if not visits and report["reservationId"] in (aggregate.get("reservationIds") or []):
        return None  # Legacy aggregate has already counted this visit.
    if aggregate.get("locationId") and aggregate["locationId"] != report["locationId"]:
        raise InvalidReport("A waiter cannot report two different locations in one day")
    if "legacyTotals" not in aggregate and not visits and aggregate.get("ordersProcessed"):
        aggregate["legacyTotals"] = {
            k: v for k, v in aggregate.items() if k not in {"waiterId", "date", "version", "reservationIds"}
        }
    legacy = aggregate.get("legacyTotals", {})
    visits[report["reservationId"]] = {
        "revision": report["revision"],
        "Service": report["Service"],
        "Cuisine": report["Cuisine"],
        "hours": Decimal(str((report["end"] - report["start"]).total_seconds())) / Decimal(3600),
        "revenue": report["revenue"],
    }
    aggregate.update(locationId=report["locationId"], visits=visits)
    aggregate["ordersProcessed"] = int(legacy.get("ordersProcessed", 0)) + len(visits)
    aggregate["hoursWorked"] = Decimal(str(legacy.get("hoursWorked", 0))) + sum(
        (v["hours"] for v in visits.values()), Decimal(0)
    )
    aggregate["totalRevenue"] = Decimal(str(legacy.get("totalRevenue", 0))) + sum(
        (v["revenue"] for v in visits.values()), Decimal(0)
    )
    for kind in KINDS:
        ratings = [int(v[kind]) for v in visits.values() if v[kind]]
        old_count = int(legacy.get(f"{kind.lower()}RatingsCount", 0))
        count = old_count + len(ratings)
        total = Decimal(str(legacy.get(f"average{kind}Rating", 0))) * old_count + sum(ratings)
        aggregate[f"{kind.lower()}RatingsCount"] = count
        aggregate[f"average{kind}Rating"] = total / count if count else Decimal(0)
        minimums = ratings + (
            [int(legacy[f"minimum{kind}Rating"])]
            if old_count and legacy.get(f"minimum{kind}Rating") is not None
            else []
        )
        aggregate[f"minimum{kind}Rating"] = min(minimums) if minimums else 0
    return aggregate


def process(body: str, table: Any) -> None:
    report = parse_report(body)
    day = _day(report["start"])
    key = {"waiterId": report["waiterId"], "date": f"{day}#{report['locationId']}"}
    # Existing pre-upgrade aggregates remain readable and are never counted twice.
    legacy_key = {"waiterId": report["waiterId"], "date": day}
    legacy = table.get_item(Key=legacy_key, ConsistentRead=True).get("Item")
    if legacy and legacy.get("locationId") == report["locationId"]:
        key = legacy_key
    for attempt in range(8):
        current = table.get_item(Key=key, ConsistentRead=True).get("Item")
        updated = apply_report(current, report)
        if updated is None:
            return
        condition = {"ExpressionAttributeNames": {"#v": "version"}}
        if current and "version" in current:
            condition.update(ConditionExpression="#v = :v", ExpressionAttributeValues={":v": current["version"]})
        else:
            condition["ConditionExpression"] = "attribute_not_exists(#v)"
        updated["date"] = key["date"]
        updated["version"] = int((current or {}).get("version", 0)) + 1
        try:
            table.put_item(Item=updated, **condition)
            return
        except ClientError as exc:
            if exc.response["Error"]["Code"] != "ConditionalCheckFailedException" or attempt == 7:
                raise


def handler(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    table = _table()
    failures = []
    for record in event.get("Records", []):
        message_id = record.get("messageId", "")
        try:
            process(record.get("body", ""), table)
        except InvalidReport as exc:
            logger.error("PERMANENT_ERROR: dropping message %s: %s", message_id, exc)
        except Exception:
            logger.exception("TRANSIENT_ERROR: message %s will be retried", message_id)
            failures.append({"itemIdentifier": message_id})
    return {"batchItemFailures": failures}
