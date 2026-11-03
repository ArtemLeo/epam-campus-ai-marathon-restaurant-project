"""HTTP request parsing and API Gateway proxy response builders."""

from __future__ import annotations

import base64
import datetime as dt
import json
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from core.auth import Caller
from core.errors import BadRequest
from core.timeutils import iso

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,PATCH,OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type,Authorization,X-Amz-Date,X-Api-Key,X-Amz-Security-Token",
}


def _default(value: Any) -> Any:
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, dt.datetime):
        return iso(value)
    if isinstance(value, dt.date):
        return value.isoformat()
    if isinstance(value, (set, frozenset)):
        return sorted(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def to_json(body: Any) -> str:
    return json.dumps(body, default=_default, ensure_ascii=False)


def json_response(status: int, body: Any = None) -> dict[str, Any]:
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json", **CORS_HEADERS},
        "body": "" if body is None else to_json(body),
        "isBase64Encoded": False,
    }


def ok(body: Any = None, status: int = 200) -> dict[str, Any]:
    return json_response(status, body)


def message(text: str, status: int = 200) -> dict[str, Any]:
    """``{"message": text}`` — the original ``ResponseBuilder.CreateSuccessResponse(string)``."""
    return json_response(status, {"message": text})


def text(status: int, content: str) -> dict[str, Any]:
    return {
        "statusCode": status,
        "headers": {"Content-Type": "text/plain", **CORS_HEADERS},
        "body": content,
        "isBase64Encoded": False,
    }


def file(content: bytes, file_name: str, content_type: str) -> dict[str, Any]:
    is_text = content_type.startswith("text/") or content_type == "application/json"
    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": content_type,
            "Content-Disposition": f'attachment; filename="{file_name}"',
            "Access-Control-Expose-Headers": "Content-Disposition",
            **CORS_HEADERS,
        },
        "body": content.decode("utf-8") if is_text else base64.b64encode(content).decode("ascii"),
        "isBase64Encoded": not is_text,
    }


def error(status: int, text_message: str, error_code: str | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {"error": text_message, "message": text_message}
    if error_code:
        body["errorCode"] = error_code
    return json_response(status, body)


@dataclass
class Request:
    """Parsed API Gateway proxy event."""

    method: str
    path: str
    path_params: dict[str, str] = field(default_factory=dict)
    query: dict[str, str] = field(default_factory=dict)
    headers: dict[str, str] = field(default_factory=dict)
    raw_body: str | None = None
    caller: Caller | None = None
    event: dict[str, Any] = field(default_factory=dict)

    def header(self, name: str) -> str | None:
        return self.headers.get(name.lower())

    def bearer_token(self) -> str | None:
        value = (self.header("authorization") or "").strip()
        if value.lower().startswith("bearer "):
            value = value[7:].strip()
        return value or None

    def json(self) -> dict[str, Any]:
        """Request body as a JSON object; raises 400 when it is missing or malformed."""
        if not self.raw_body or not self.raw_body.strip():
            raise BadRequest("Request body is empty")
        try:
            body = json.loads(self.raw_body, parse_float=Decimal)
        except (ValueError, TypeError) as exc:
            raise BadRequest("Invalid request body.") from exc
        if not isinstance(body, dict):
            raise BadRequest("Invalid request body.")
        return body

    def param(self, name: str) -> str:
        value = (self.path_params.get(name) or "").strip()
        if not value:
            raise BadRequest(f"Missing '{name}' in path parameters.")
        return value
