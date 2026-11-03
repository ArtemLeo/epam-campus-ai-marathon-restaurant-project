"""Runtime configuration resolved from the Lambda environment (see lambda_config.json)."""

from __future__ import annotations

import os
from zoneinfo import ZoneInfo

RESTAURANT_NAME = "Green & Tasty"


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


def region() -> str:
    return env("REGION") or env("AWS_REGION", "eu-north-1")


def restaurant_timezone() -> ZoneInfo:
    return ZoneInfo(env("RESTAURANT_TIMEZONE", "UTC"))


def user_pool_id() -> str:
    return env("COGNITO_USER_POOL_ID")


def user_pool_client_id() -> str:
    return env("COGNITO_USER_POOL_CLIENT_ID")


def reports_queue_name() -> str:
    return env("reports_queue_name", "restaurant-reports-queue")


def images_bucket() -> str:
    return env("imagesBucketName")


def profile_images_bucket() -> str:
    return env("profileImagesBucketName")


# DynamoDB table names: (environment variable, default used locally and in tests)
TABLES: dict[str, tuple[str, str]] = {
    "locations": ("locationsTable", "Locations"),
    "dishes": ("dishesTable", "Dishes"),
    "tables": ("tablesTable", "Tables"),
    "reservations": ("reservationsTable", "Reservations"),
    "orders": ("ordersTable", "Orders"),
    "feedback": ("FEEDBACK_TABLE_NAME", "Feedback"),
    "notifications": ("notificationsTable", "Notifications"),
    "waiters": ("WaiterListTableName", "Waiters"),
    "profile_images": ("profileImagesTable", "ProfileImages"),
    "reports": ("reportsTable", "Reports"),
    "reports_history": ("reportsHistoryTable", "ReportsHistory"),
    "group_reservations": ("groupReservationsTable", "GroupReservations"),
    "guest_sessions": ("guestSessionTable", "GuestSessions"),
}

# Global secondary index names: (environment variable, default)
INDEXES: dict[str, tuple[str, str]] = {
    "reservations_by_table": ("reservationsTableGlobalIndex", "GSI_ByTableId"),
    "reservations_by_customer": ("reservationsCustomerIdGlobalIndex", "GSI_UserId"),
    "reservations_by_waiter": ("reservationsWaiterIdGlobalIndex", "GSI_WaiterId"),
    "orders_by_reservation": ("OrderIndexReservationId", "GSI_ReservationId"),
    "orders_by_customer": ("", "GSI_CustomerId"),
    "tables_by_location": ("tableLocationIdIndex", "locationId-tableNumber-index"),
    "waiters_by_location": ("waitersGlobalIndex", "locationId-index"),
    "feedback_by_location": ("feedbackGlobalIndex", "locationId-createdAt-index"),
    "notifications_by_user": ("notificationsUserIdIndex", "UserIdIndex"),
    "reports_history_by_user": ("", "UserIdIndex"),
    "groups_by_reservation": ("", "reservationId"),
    "groups_by_token": ("", "reservationToken"),
    "sessions_by_group": ("", "groupReservationId"),
    "sessions_by_token_hash": ("", "guestSessionTokenHash"),
}


def table_name(key: str) -> str:
    var, default = TABLES[key]
    return env(var, default) or default


def index_name(key: str) -> str:
    var, default = INDEXES[key]
    return (env(var) if var else "") or default
