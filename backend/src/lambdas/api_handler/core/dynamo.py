"""Small DynamoDB helpers: paginated query/scan, batch get and number conversion."""

from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal
from typing import Any

from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

from core import aws, config
from core.errors import Conflict


def _collect(operation: Any, **kwargs: Any) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    while True:
        page = operation(**kwargs)
        items.extend(page.get("Items", []))
        last_key = page.get("LastEvaluatedKey")
        if not last_key:
            return items
        kwargs["ExclusiveStartKey"] = last_key


def query_index(table_key: str, index_key: str, attribute: str, value: str) -> list[dict[str, Any]]:
    table = aws.table(table_key)
    return _collect(
        table.query,
        IndexName=config.index_name(index_key),
        KeyConditionExpression=Key(attribute).eq(value),
    )


def query_partition(table_key: str, attribute: str, value: str) -> list[dict[str, Any]]:
    table = aws.table(table_key)
    return _collect(table.query, KeyConditionExpression=Key(attribute).eq(value), ConsistentRead=True)


def scan_all(table_key: str, **kwargs: Any) -> list[dict[str, Any]]:
    return _collect(aws.table(table_key).scan, **kwargs)


def get_item(table_key: str, key: dict[str, Any]) -> dict[str, Any] | None:
    return aws.table(table_key).get_item(Key=key, ConsistentRead=True).get("Item")


def put_item(table_key: str, item: dict[str, Any]) -> None:
    aws.table(table_key).put_item(Item=_sanitize(item))


def version_condition(item: dict[str, Any] | None) -> dict[str, Any]:
    """An optimistic lock, including legacy records written before versions existed."""
    condition: dict[str, Any] = {"ExpressionAttributeNames": {"#version": "version"}}
    if item and "version" in item:
        condition.update(
            ConditionExpression="#version = :version", ExpressionAttributeValues={":version": item["version"]}
        )
    else:
        condition["ConditionExpression"] = "attribute_not_exists(#version)"
    return condition


def put_action(
    table_key: str, item: dict[str, Any], *, new_key: str | None = None, existing_key: str | None = None
) -> dict[str, Any]:
    condition = version_condition(item)
    if new_key:
        condition = {"ConditionExpression": "attribute_not_exists(#key)", "ExpressionAttributeNames": {"#key": new_key}}
    elif existing_key:
        condition["ConditionExpression"] += " AND attribute_exists(#key)"
        condition["ExpressionAttributeNames"]["#key"] = existing_key
    updated = {**item, "version": int(item.get("version", 0)) + 1}
    return {"Put": {"TableName": config.table_name(table_key), "Item": _sanitize(updated), **condition}}


def check_action(table_key: str, key: dict[str, Any], item: dict[str, Any]) -> dict[str, Any]:
    return {"ConditionCheck": {"TableName": config.table_name(table_key), "Key": key, **version_condition(item)}}


def delete_action(table_key: str, key: dict[str, Any], item: dict[str, Any]) -> dict[str, Any]:
    return {"Delete": {"TableName": config.table_name(table_key), "Key": key, **version_condition(item)}}


def transaction(actions: list[dict[str, Any]]) -> None:
    """Commit related writes together, rejecting a stale read instead of losing an update."""
    try:
        aws.dynamodb().meta.client.transact_write_items(TransactItems=actions)
    except ClientError as exc:
        code = exc.response["Error"]["Code"]
        reasons = {r.get("Code") for r in exc.response.get("CancellationReasons", [])}
        if code == "TransactionConflictException" or (
            code == "TransactionCanceledException" and reasons & {"ConditionalCheckFailed", "TransactionConflict"}
        ):
            raise Conflict("The data changed while you were working. Refresh and try again.") from exc
        raise


def save_versioned(table_key: str, item: dict[str, Any], *, new_key: str | None = None) -> None:
    transaction([put_action(table_key, item, new_key=new_key)])
    item["version"] = int(item.get("version", 0)) + 1


def _sanitize(obj: Any) -> Any:
    """Recursively convert floats to Decimals so DynamoDB accepts them."""
    if isinstance(obj, float):
        return Decimal(str(obj))
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize(v) for v in obj]
    return obj


def delete_item(table_key: str, key: dict[str, Any]) -> None:
    aws.table(table_key).delete_item(Key=key)


def batch_get(table_key: str, key_name: str, ids: Iterable[str]) -> dict[str, dict[str, Any]]:
    """Items keyed by their id; missing ids are simply absent from the result."""
    unique = list(dict.fromkeys(i for i in ids if i))
    name = config.table_name(table_key)
    found: dict[str, dict[str, Any]] = {}
    for start in range(0, len(unique), 100):
        request = {name: {"Keys": [{key_name: i} for i in unique[start : start + 100]], "ConsistentRead": True}}
        while request:
            response = aws.dynamodb().batch_get_item(RequestItems=request)
            for item in response.get("Responses", {}).get(name, []):
                found[item[key_name]] = item
            request = response.get("UnprocessedKeys") or {}
    return found


def number(value: Any, default: int | float = 0) -> int | float:
    """DynamoDB Decimal (or anything numeric) as int when whole, otherwise float."""
    if value is None or value == "":
        return default
    try:
        decimal = value if isinstance(value, Decimal) else Decimal(str(value))
    except (ArithmeticError, ValueError):
        return default
    return int(decimal) if decimal == decimal.to_integral_value() else float(decimal)


def decimal(value: Any) -> Decimal:
    """Number suitable for storing in DynamoDB (floats are not accepted by boto3)."""
    return value if isinstance(value, Decimal) else Decimal(str(value))
