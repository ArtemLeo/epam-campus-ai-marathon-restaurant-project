"""Admin reports built from daily waiter aggregates.

Completing a reservation publishes a message to SQS; the reports-handler Lambda folds it into
the waiter's daily aggregate (Reports table). Reports compare a period with the previous one.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import uuid
from decimal import Decimal
from typing import Any

from core import aws, config, dynamo, timeutils
from core.auth import Caller
from core.enums import FeedbackType, ReportType, parse_enum, stored_enum
from core.errors import BadRequest, NotFound
from repositories import bookings, catalog, people
from repositories import reports as reports_repo
from services import orders, report_files

logger = logging.getLogger(__name__)

Item = dict[str, Any]


# --- Publishing completed reservations -------------------------------------


def reservation_report_payload(reservation: Item, feedback_items: list[Item] | None = None) -> Item:
    feedback = {
        stored_enum(FeedbackType, f.get("type"), FeedbackType.Service): int(dynamo.number(f.get("rating")))
        for f in (feedback_items if feedback_items is not None else people.feedback_by_reservation(reservation["id"]))
    }
    table = catalog.get_table(reservation.get("tableId", "")) or {}
    return {
        "ReservationId": reservation["id"],
        "Revision": int(reservation.get("reportRevision", 0)) + 1,
        "CreatedAt": timeutils.iso(timeutils.utcnow()),
        "ReservationStart": reservation["startTime"],
        "ReservationEnd": reservation["endTime"],
        "WaiterId": reservation.get("waiterId", ""),
        "LocationId": reservation.get("locationId") or table.get("locationId", ""),
        "ServiceRating": feedback.get(FeedbackType.Service, 0),
        "CuisineRating": feedback.get(FeedbackType.CuisineExperience, 0),
        "Revenue": float(orders.revenue(bookings.active_order(reservation["id"]))),
    }


def prepare_completed_reservation(reservation: Item, feedback_items: list[Item] | None = None) -> None:
    """The caller persists this outbox event atomically with the visit/feedback change."""
    event = reservation_report_payload(reservation, feedback_items)
    reservation["reportEvent"] = event
    reservation["reportRevision"] = event["Revision"]


def deliver_report(message: Item) -> None:
    """Transport boundary: SQS in AWS, the same worker called directly in local mode."""
    client = aws.sqs()
    queue_url = client.get_queue_url(QueueName=config.reports_queue_name())["QueueUrl"]
    client.send_message(
        QueueUrl=queue_url,
        MessageBody=json.dumps(message, default=lambda value: float(value)),
    )


def publish_completed_reservation(reservation: Item) -> None:
    if not reservation.get("reportEvent"):
        prepare_completed_reservation(reservation)
        bookings.save_reservation(reservation)
    try:
        deliver_report(reservation["reportEvent"])
        # A failed or concurrent acknowledgement is harmless: delivery is idempotent.
        reservation["reportDeliveredRevision"] = reservation["reportRevision"]
        dynamo.save_versioned("reservations", reservation)
    except Exception:
        logger.exception(
            "Report event for reservation %s remains pending and will be retried",
            reservation.get("id"),
        )


def replay_pending_reports() -> None:
    for reservation in bookings.all_reservations():
        if reservation.get("reportEvent") and int(reservation.get("reportDeliveredRevision", 0)) < int(
            reservation.get("reportRevision", 0)
        ):
            publish_completed_reservation(reservation)


# --- Building reports ------------------------------------------------------


def _day_bounds(start: dt.date, end: dt.date) -> tuple[str, str]:
    first = dt.datetime.combine(start, dt.time.min, tzinfo=timeutils.UTC)
    last = dt.datetime.combine(end, dt.time.max, tzinfo=timeutils.UTC)
    return timeutils.iso(first), timeutils.iso(last)


def _aggregates(start: dt.date, end: dt.date, location_id: str | None) -> list[Item]:
    return reports_repo.aggregates_between(*_day_bounds(start, end), location_id)


def previous_period(start: dt.date, end: dt.date) -> tuple[dt.date, dt.date]:
    days = (end - start).days + 1
    return start - dt.timedelta(days=days), start - dt.timedelta(days=1)


def _count(aggregate: Item, kind: str) -> int:
    """How many rated visits the daily average covers (older items only have ordersProcessed)."""
    value = aggregate.get(f"{kind}RatingsCount")
    return int(dynamo.number(value if value is not None else aggregate.get("ordersProcessed")))


def _average(aggregates: list[Item], kind: str) -> float:
    total = sum(
        Decimal(str(dynamo.number(a.get(f"average{kind.title()}Rating")))) * _count(a, kind) for a in aggregates
    )
    count = sum(_count(a, kind) for a in aggregates)
    return round(float(total / count), 2) if count else 0.0


def _minimum(aggregates: list[Item], kind: str) -> float:
    values = [
        dynamo.number(a.get(f"minimum{kind.title()}Rating"))
        for a in aggregates
        if _count(a, kind) and a.get(f"minimum{kind.title()}Rating") is not None
    ]
    return float(min(values)) if values else 0.0


def _delta(current: float, previous: float | None) -> float:
    return round((current - previous) / previous * 100, 2) if previous else 0.0


def _sum(aggregates: list[Item], key: str) -> float:
    return float(sum(Decimal(str(dynamo.number(a.get(key)))) for a in aggregates))


def _group(aggregates: list[Item], key: str) -> dict[str, list[Item]]:
    grouped: dict[str, list[Item]] = {}
    for aggregate in aggregates:
        grouped.setdefault(aggregate.get(key, ""), []).append(aggregate)
    return grouped


def _base(
    report_type: ReportType,
    start: dt.date,
    end: dt.date,
    user_id: str,
    location_id: str,
    location_name: str,
) -> Item:
    return {
        "reportType": int(report_type),
        "startDate": start.isoformat(),
        "endDate": end.isoformat(),
        "userId": user_id,
        "locationId": location_id,
        "locationName": location_name,
    }


def waiter_rows(
    current: list[Item],
    previous: list[Item],
    start: dt.date,
    end: dt.date,
    user_id: str,
    names: dict[str, str],
) -> list[Item]:
    def by_waiter_location(items: list[Item]) -> dict[tuple[str, str], list[Item]]:
        grouped: dict[tuple[str, str], list[Item]] = {}
        for item in items:
            grouped.setdefault((item.get("waiterId", ""), item.get("locationId", "")), []).append(item)
        return grouped

    before = by_waiter_location(previous)
    rows = []
    for (waiter_id, location_id), items in by_waiter_location(current).items():
        prev = before.get((waiter_id, location_id), [])
        attrs = people.attributes(people.user_by_id(waiter_id))
        location_id = items[0].get("locationId", "")
        orders_now = _sum(items, "ordersProcessed")
        avg_now = _average(items, "service")
        rows.append(
            {
                **_base(
                    ReportType.Service,
                    start,
                    end,
                    user_id,
                    location_id,
                    names.get(location_id, "Unknown"),
                ),
                "waiterId": waiter_id,
                "waiterName": f"{attrs.get('given_name', 'Unknown')} {attrs.get('family_name', '')}".strip(),
                "waiterEmail": attrs.get("email", "Unknown"),
                "workingHours": round(_sum(items, "hoursWorked"), 2),
                "totalOrders": int(orders_now),
                "avgServiceFeedback": avg_now,
                "minServiceFeedback": _minimum(items, "service"),
                "deltaAvgServiceFeedback": _delta(avg_now, _average(prev, "service") if prev else None),
                "deltaTotalOrders": _delta(orders_now, _sum(prev, "ordersProcessed") if prev else None),
            }
        )
    return sorted(rows, key=lambda r: r["waiterName"])


def location_rows(
    current: list[Item],
    previous: list[Item],
    start: dt.date,
    end: dt.date,
    user_id: str,
    names: dict[str, str],
) -> list[Item]:
    before = _group(previous, "locationId")
    rows = []
    for location_id, items in _group(current, "locationId").items():
        prev = before.get(location_id, [])
        revenue_now = round(_sum(items, "totalRevenue"), 2)
        avg_now = _average(items, "cuisine")
        rows.append(
            {
                **_base(
                    ReportType.Sales,
                    start,
                    end,
                    user_id,
                    location_id,
                    names.get(location_id, "Unknown"),
                ),
                "totalOrders": int(_sum(items, "ordersProcessed")),
                "revenue": revenue_now,
                "avgCuisineFeedback": avg_now,
                "minCuisineFeedback": _minimum(items, "cuisine"),
                "deltaAvgCuisineFeedback": _delta(avg_now, _average(prev, "cuisine") if prev else None),
                "deltaRevenue": _delta(revenue_now, _sum(prev, "totalRevenue") if prev else None),
            }
        )
    return rows


def build(
    report_type: ReportType,
    start: dt.date,
    end: dt.date,
    location_id: str | None,
    user_id: str,
) -> list[Item]:
    replay_pending_reports()
    current = _aggregates(start, end, location_id)
    if not current:
        return []
    previous = _aggregates(*previous_period(start, end), location_id)
    names = {loc["id"]: loc.get("address", "Unknown") for loc in catalog.all_locations()}
    builder = waiter_rows if report_type == ReportType.Service else location_rows
    return builder(current, previous, start, end, user_id, names)


# --- API operations ----------------------------------------------------------


def _params(query: dict[str, str], *, default_period: bool) -> tuple[ReportType, dt.date, dt.date, str]:
    location_id = (query.get("locationId") or "").strip()
    if not location_id:
        raise BadRequest("Missing required parameter: locationId")
    if default_period and not query.get("startDate"):
        start = timeutils.utcnow().date() - dt.timedelta(days=7)
    else:
        start = timeutils.parse_date(query.get("startDate"), "startDate")
    if default_period and not query.get("endDate"):
        end = timeutils.utcnow().date()
    else:
        end = timeutils.parse_date(query.get("endDate"), "endDate")
    if start > end:
        raise BadRequest("startDate must be before or equal to endDate")
    raw_type = query.get("type")
    report_type = parse_enum(ReportType, raw_type, "reportType") if raw_type not in (None, "") else ReportType.Service
    return report_type, start, end, location_id


def _same_report(row: Item, report_type: ReportType, start: dt.date, end: dt.date, location_id: str) -> bool:
    return (
        stored_enum(ReportType, row.get("reportType"), ReportType.Service) == report_type
        and row.get("locationId") == location_id
        and row.get("startDate") == start.isoformat()
        and row.get("endDate") == end.isoformat()
    )


def _public(row: Item) -> Item:
    return {k: dynamo.number(v) if isinstance(v, Decimal) else v for k, v in row.items() if k != "id"}


def generate(caller: Caller, query: dict[str, str]) -> list[Item]:
    report_type, start, end, location_id = _params(query, default_period=False)
    if not catalog.get_location(location_id):
        raise NotFound(f"Location with ID {location_id} not found.")
    rows = build(report_type, start, end, location_id, caller.user_id)
    stale = [
        r for r in reports_repo.history_by_user(caller.user_id) if _same_report(r, report_type, start, end, location_id)
    ]
    for row in stale:
        dynamo.delete_item("reports_history", {"id": row["id"]})
    for row in rows:
        reports_repo.save_history({"id": str(uuid.uuid4()), **{k: _storable(v) for k, v in row.items()}})
    return rows


def _storable(value: Any) -> Any:
    return dynamo.decimal(value) if isinstance(value, float) else value


def download(caller: Caller, query: dict[str, str]) -> tuple[bytes, str, str]:
    locale = query.get("locale") or "en"
    if locale not in report_files.SUPPORTED_LOCALES:
        raise BadRequest("Unsupported report language. Choose en, uk, fr, es or de.")
    report_type, start, end, location_id = _params(query, default_period=True)
    rows = [
        _public(r)
        for r in reports_repo.history_by_user(caller.user_id)
        if _same_report(r, report_type, start, end, location_id)
    ] or build(report_type, start, end, location_id, caller.user_id)
    if not rows:
        raise NotFound("No report data for the selected period.")
    return report_files.render(
        rows,
        (query.get("format") or "csv").lower(),
        start.isoformat(),
        end.isoformat(),
        locale,
    )


def history(caller: Caller) -> list[Item]:
    replay_pending_reports()
    names = {loc["id"]: loc.get("address", "Unknown") for loc in catalog.all_locations()}
    seen: dict[tuple[Any, ...], Item] = {}
    for row in reports_repo.history_by_user(caller.user_id):
        key = (
            row.get("startDate"),
            row.get("endDate"),
            row.get("locationId"),
            int(dynamo.number(row.get("reportType"))),
        )
        seen.setdefault(
            key,
            {
                "startDate": row.get("startDate"),
                "endDate": row.get("endDate"),
                "userId": caller.user_id,
                "locationId": row.get("locationId"),
                "locationName": names.get(row.get("locationId", ""), row.get("locationName", "Unknown")),
                "reportType": int(dynamo.number(row.get("reportType"))),
            },
        )
    return sorted(
        seen.values(),
        key=lambda r: (str(r["startDate"]), r["reportType"]),
        reverse=True,
    )
