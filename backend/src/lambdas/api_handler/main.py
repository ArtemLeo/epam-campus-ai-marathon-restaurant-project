"""API Handler Lambda: routes API Gateway proxy events to handlers and maps errors to HTTP responses."""

from __future__ import annotations

import base64
import logging
import os
import re
import sys
from typing import Any
from urllib.parse import unquote

# Make the bundled packages (core, handlers, services, ...) importable in the Lambda runtime.
_here = os.path.dirname(os.path.abspath(__file__))
if _here not in sys.path:
    sys.path.insert(0, _here)

from core import http  # noqa: E402
from core.auth import caller_from_claims  # noqa: E402
from core.errors import ApiError, BadRequest  # noqa: E402
from routes import resolve  # noqa: E402

logger = logging.getLogger("api_handler")
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO").upper())
logging.getLogger().setLevel(os.environ.get("LOG_LEVEL", "INFO").upper())

_STAGE_PREFIX = re.compile(r"^/(?:develop|dev|prod)(?=/|$)")


def _normalize_path(raw_path: str) -> str:
    path = _STAGE_PREFIX.sub("", raw_path or "/") or "/"
    path = path.rstrip("/") or "/"
    return path if path.startswith("/") else "/" + path


def _build_request(event: dict[str, Any], method: str, path: str, params: dict[str, str]) -> http.Request:
    body = event.get("body")
    if body and event.get("isBase64Encoded"):
        try:
            body = base64.b64decode(body, validate=True).decode("utf-8")
        except (ValueError, UnicodeError) as exc:
            raise BadRequest("Invalid base64 or UTF-8 request body.") from exc
    claims = (event.get("requestContext") or {}).get("authorizer", {}) or {}
    return http.Request(
        method=method,
        path=path,
        path_params={k: unquote(v) for k, v in params.items()},
        query=dict(event.get("queryStringParameters") or {}),
        headers={str(k).lower(): v for k, v in (event.get("headers") or {}).items()},
        raw_body=body,
        caller=caller_from_claims(claims.get("claims")),
        event=event,
    )


def handler(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    method = str(event.get("httpMethod") or "GET").upper()
    path = _normalize_path(event.get("path") or "/")
    if method == "OPTIONS":
        return http.json_response(200)

    resolved = resolve(method, path)
    if resolved is None:
        logger.warning("Route not found: %s %s", method, path)
        return http.error(404, "Not Found")

    route_handler, params = resolved
    try:
        request = _build_request(event, method, path, params)
        logger.info("%s %s (user: %s)", method, path, request.caller.user_id if request.caller else "anonymous")
        return route_handler(request)
    except ApiError as exc:
        logger.info("%s %s -> %s %s", method, path, exc.status, exc.message)
        return http.error(exc.status, exc.message, exc.error_code)
    except Exception:
        logger.exception("Unhandled error processing %s %s", method, path)
        return http.error(500, "Internal Server Error")
