"""Lazily created AWS SDK clients shared across warm Lambda invocations."""

from __future__ import annotations

import os
from functools import cache
from typing import Any

import boto3

from core import config


@cache
def dynamodb() -> Any:
    endpoint = os.environ.get("DYNAMODB_ENDPOINT")
    kwargs: dict[str, Any] = {"region_name": config.region()}
    if endpoint:
        kwargs["endpoint_url"] = endpoint
    return boto3.resource("dynamodb", **kwargs)


@cache
def cognito() -> Any:
    return boto3.client("cognito-idp", region_name=config.region())


@cache
def s3() -> Any:
    return boto3.client("s3", region_name=config.region())


@cache
def sqs() -> Any:
    return boto3.client("sqs", region_name=config.region())


def table(key: str) -> Any:
    """DynamoDB Table resource for a logical table key from ``config.TABLES``."""
    return dynamodb().Table(config.table_name(key))


def reset_clients() -> None:
    """Drop cached clients (used by tests that start a fresh moto backend)."""
    for factory in (dynamodb, cognito, s3, sqs):
        factory.cache_clear()
