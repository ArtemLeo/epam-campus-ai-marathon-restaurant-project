"""Report Sender Lambda (weekly EventBridge Scheduler target).

Builds the sales (per location) and service (per waiter) reports for the last 7 days, compares
them with the 7 days before, and emails both CSV files to every user in the Cognito "Admin" group.
"""

from __future__ import annotations

import csv
import datetime as dt
import io
import json
import logging
import os
from collections import defaultdict
from decimal import Decimal
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any
from zoneinfo import ZoneInfo

import boto3
from boto3.dynamodb.conditions import Attr

logger = logging.getLogger("report_sender")
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO").upper())

SUBJECT = "Weekly Green & Tasty Report"
BODY = "Please find the attached report."
PERIOD_DAYS = 7


def _region() -> str:
    return os.environ.get("Region") or os.environ.get("AWS_REGION", "eu-north-1")


def _num(value: Any) -> float:
    return float(Decimal(str(value))) if value is not None else 0.0


def load_aggregates(table: Any, start: dt.date, end: dt.date) -> list[dict[str, Any]]:
    condition = Attr("date").between(f"{start.isoformat()}T00:00:00.000Z", f"{end.isoformat()}T23:59:59.999Z")
    kwargs: dict[str, Any] = {"FilterExpression": condition, "ConsistentRead": True}
    items: list[dict[str, Any]] = []
    while True:
        page = table.scan(**kwargs)
        items.extend(page.get("Items", []))
        if "LastEvaluatedKey" not in page:
            return items
        kwargs["ExclusiveStartKey"] = page["LastEvaluatedKey"]


def _rated(items: list[dict[str, Any]], kind: str) -> tuple[float, float]:
    """(weighted average, minimum) of daily ratings; visits without a rating are ignored."""
    weighted, count, minimums = 0.0, 0, []
    for item in items:
        n = int(_num(item.get(f"{kind.lower()}RatingsCount", item.get("ordersProcessed"))))
        if n:
            weighted += _num(item.get(f"average{kind}Rating")) * n
            count += n
            if item.get(f"minimum{kind}Rating") is not None:
                minimums.append(_num(item[f"minimum{kind}Rating"]))
    return (round(weighted / count, 2) if count else 0.0), (min(minimums) if minimums else 0.0)


def _delta(current: float, previous: float) -> float:
    return round((current - previous) / previous * 100, 2) if previous else 0.0


def _grouped(items: list[dict[str, Any]], key: str) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in items:
        grouped[item.get(key, "")].append(item)
    return grouped


def sales_rows(current: list[dict[str, Any]], previous: list[dict[str, Any]], names: dict[str, str]) -> list[list[Any]]:
    before = _grouped(previous, "locationId")
    rows = []
    for location_id, items in _grouped(current, "locationId").items():
        revenue = round(sum(_num(i.get("totalRevenue")) for i in items), 2)
        average, minimum = _rated(items, "Cuisine")
        prev = before.get(location_id, [])
        prev_revenue = sum(_num(i.get("totalRevenue")) for i in prev)
        prev_average = _rated(prev, "Cuisine")[0]
        orders = int(sum(_num(i.get("ordersProcessed")) for i in items))
        rows.append(
            [
                names.get(location_id, location_id),
                orders,
                revenue,
                average,
                minimum,
                _delta(average, prev_average),
                _delta(revenue, prev_revenue),
            ]
        )
    return rows


def service_rows(
    current: list[dict[str, Any]],
    previous: list[dict[str, Any]],
    names: dict[str, str],
    waiters: dict[str, dict[str, str]],
) -> list[list[Any]]:
    def by_waiter_location(items: list[dict[str, Any]]) -> dict[tuple[str, str], list[dict[str, Any]]]:
        grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for item in items:
            grouped.setdefault((item.get("waiterId", ""), item.get("locationId", "")), []).append(item)
        return grouped

    before = by_waiter_location(previous)
    rows = []
    for (waiter_id, location_id), items in by_waiter_location(current).items():
        prev = before.get((waiter_id, location_id), [])
        orders = sum(_num(i.get("ordersProcessed")) for i in items)
        prev_orders = sum(_num(i.get("ordersProcessed")) for i in prev)
        average, minimum = _rated(items, "Service")
        info = waiters.get(waiter_id, {})
        rows.append(
            [
                names.get(items[0].get("locationId", ""), "Unknown"),
                info.get("name", "Unknown"),
                info.get("email", "Unknown"),
                int(orders),
                round(sum(_num(i.get("hoursWorked")) for i in items), 2),
                average,
                minimum,
                _delta(average, _rated(prev, "Service")[0]),
                _delta(orders, prev_orders),
            ]
        )
    return rows


SALES_HEADER = [
    "Location",
    "Total Orders",
    "Revenue",
    "Average Cuisine Feedback",
    "Minimal Cuisine Feedback",
    "Delta Avg Cuisine Feedback, %",
    "Delta Revenue, %",
]
SERVICE_HEADER = [
    "Location",
    "Waiter Name",
    "Email",
    "Total Orders",
    "Working Hours",
    "Average Feedback",
    "Minimal Feedback",
    "Delta Avg Feedback, %",
    "Delta Orders, %",
]


def to_csv(header: list[str], rows: list[list[Any]]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


def _users_in_group(cognito: Any, pool_id: str, group: str) -> list[dict[str, Any]]:
    users: list[dict[str, Any]] = []
    kwargs: dict[str, Any] = {"UserPoolId": pool_id, "GroupName": group, "Limit": 60}
    while True:
        try:
            page = cognito.list_users_in_group(**kwargs)
        except cognito.exceptions.ResourceNotFoundException:
            return users
        users.extend(page.get("Users", []))
        if not page.get("NextToken"):
            return users
        kwargs["NextToken"] = page["NextToken"]


def _attributes(user: dict[str, Any]) -> dict[str, str]:
    return {a["Name"]: a["Value"] for a in user.get("Attributes", [])}


def build_email(sender: str, recipients: list[str], attachments: dict[str, bytes]) -> bytes:
    message = MIMEMultipart()
    message["Subject"] = SUBJECT
    message["From"] = sender
    message["To"] = ", ".join(recipients)
    message.attach(MIMEText(BODY, "plain"))
    for name, content in attachments.items():
        part = MIMEApplication(content, _subtype="csv")
        part.add_header("Content-Disposition", "attachment", filename=name)
        message.attach(part)
    return message.as_bytes()


def replay_pending_reports(dynamodb: Any) -> int:
    """Retry durable events without acknowledging a newer concurrently written revision."""
    table = dynamodb.Table(os.environ.get("ReservationsTableName", "Reservations"))
    sqs = boto3.client("sqs", region_name=_region())
    queue_url = None
    kwargs: dict[str, Any] = {"FilterExpression": Attr("reportEvent").exists(), "ConsistentRead": True}
    sent = 0
    while True:
        page = table.scan(**kwargs)
        for reservation in page.get("Items", []):
            revision = int(reservation.get("reportRevision", 0))
            if int(reservation.get("reportDeliveredRevision", 0)) >= revision:
                continue
            if queue_url is None:
                queue_url = sqs.get_queue_url(
                    QueueName=os.environ.get("reports_queue_name", "restaurant-reports-queue")
                )["QueueUrl"]
            sqs.send_message(QueueUrl=queue_url, MessageBody=json.dumps(reservation["reportEvent"], default=float))
            table.update_item(
                Key={"id": reservation["id"]},
                UpdateExpression="SET reportDeliveredRevision = :revision",
                ConditionExpression="reportRevision = :revision",
                ExpressionAttributeValues={":revision": revision},
            )
            sent += 1
        if not page.get("LastEvaluatedKey"):
            return sent
        kwargs["ExclusiveStartKey"] = page["LastEvaluatedKey"]


def handler(event: Any = None, context: Any = None) -> dict[str, Any]:
    today = dt.datetime.now(ZoneInfo(os.environ.get("RESTAURANT_TIMEZONE", "UTC"))).date()
    start, end = today - dt.timedelta(days=PERIOD_DAYS), today - dt.timedelta(days=1)
    prev_start, prev_end = start - dt.timedelta(days=PERIOD_DAYS), start - dt.timedelta(days=1)

    dynamodb = boto3.resource("dynamodb", region_name=_region())
    replay_pending_reports(dynamodb)
    reports = dynamodb.Table(os.environ.get("ReportTableName", "Reports"))
    locations = dynamodb.Table(os.environ.get("LocationTableName", "Locations"))
    current = load_aggregates(reports, start, end)
    previous = load_aggregates(reports, prev_start, prev_end)

    names = {}
    for location_id in {i.get("locationId", "") for i in current if i.get("locationId")}:
        item = locations.get_item(Key={"id": location_id}).get("Item") or {}
        names[location_id] = item.get("address", "Unknown")

    cognito = boto3.client("cognito-idp", region_name=_region())
    pool_id = os.environ.get("CognitoUserPoolId", "")
    waiters = {}
    for user in _users_in_group(cognito, pool_id, "Waiter"):
        attrs = _attributes(user)
        waiters[attrs.get("sub", "")] = {
            "name": f"{attrs.get('given_name', 'Unknown')} {attrs.get('family_name', '')}".strip(),
            "email": attrs.get("email", "Unknown"),
        }
    recipients = [e for e in (_attributes(u).get("email") for u in _users_in_group(cognito, pool_id, "Admin")) if e]

    period = f"{start.isoformat()}-{end.isoformat()}"
    attachments = {
        f"sales_report_{period}.csv": to_csv(SALES_HEADER, sales_rows(current, previous, names)),
        f"service_report_{period}.csv": to_csv(SERVICE_HEADER, service_rows(current, previous, names, waiters)),
    }
    sender = os.environ.get("EmailFrom", "")
    summary = {"period": period, "aggregates": len(current), "recipients": len(recipients), "sent": False}
    if not sender or not recipients:
        logger.warning("Weekly report not emailed: sender=%r, recipients=%d", sender, len(recipients))
        return summary
    boto3.client("ses", region_name=_region()).send_raw_email(
        Source=sender, Destinations=recipients, RawMessage={"Data": build_email(sender, recipients, attachments)}
    )
    logger.info("Weekly report %s sent to %d admins", period, len(recipients))
    return {**summary, "sent": True}
