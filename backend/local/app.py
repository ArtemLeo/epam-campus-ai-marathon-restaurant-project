"""Local HTTP adapter; business rules and report aggregation are shared with AWS."""

from __future__ import annotations

import base64
import json
import logging
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from src.lambdas.reports_handler import main as report_worker

from core import aws, http, jwt_verifier
from core.errors import ApiError
from local import local_auth
from repositories import people
from services import images, reports, users

logger = logging.getLogger("local_api")
logging.basicConfig(level=logging.INFO)

# Keep the adapters together: the application routes always call the shared services.
for name in (
    "register",
    "sign_in",
    "current_user",
    "update_profile",
    "change_password",
    "search_users",
    "user_name",
    "require_user_id_by_email",
    "forgot_password",
    "reset_password",
    "confirm_registration",
    "resend_confirmation",
):
    setattr(users, name, getattr(local_auth, name))
for name in (
    "user_by_email",
    "user_by_id",
    "full_name",
    "groups_of",
    "add_to_group",
    "remove_from_group",
    "users_by_given_name_prefix",
    "users_in_group",
    "update_attributes",
):
    setattr(people, name, getattr(local_auth, name))
people.ensure_group = lambda group: None
people.attributes = lambda user: user if isinstance(user, dict) else {}
jwt_verifier.optional_caller = local_auth.caller_from_token

DATA_DIR = Path(os.environ.get("LOCAL_DATA_DIR", "/app/data"))
IMAGES_DIR = DATA_DIR / "images"
IMAGES_DIR.mkdir(parents=True, exist_ok=True)
PUBLIC_API_URL = os.environ.get("PUBLIC_API_URL", "http://localhost:18080").rstrip("/")


def _image_path(key: str) -> Path:
    path = (IMAGES_DIR / key).resolve()
    if not path.is_relative_to(IMAGES_DIR.resolve()):
        raise ValueError("Invalid image path")
    return path


def _upload(image: bytes, bucket: str, folder: str, file_name: str) -> str:
    extension = images.content_type(image).split("/")[1]
    key = f"{folder}/{file_name}.{extension}"
    path = _image_path(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(image)
    return key


def _image_url(bucket: str, key: str, expires_in: int = 3600) -> str:
    return f"{PUBLIC_API_URL}/images/{key}"


def _download(bucket: str, key: str) -> bytes | None:
    path = _image_path(key)
    return path.read_bytes() if path.is_file() else None


def _delete(bucket: str, key: str) -> None:
    _image_path(key).unlink(missing_ok=True)


def _deliver_report(payload: dict[str, Any]) -> None:
    report_worker.process(json.dumps(payload, default=str), aws.table("reports"))


images.upload = _upload
images.public_url = _image_url
images.presigned_url = _image_url
images.download = _download
images.delete = _delete
reports.deliver_report = _deliver_report

app = FastAPI(title="Green & Tasty local API", docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.environ.get("FRONTEND_URL", "http://localhost:4200")],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)


@app.get("/health")
def health() -> dict[str, str]:
    aws.table("locations").load()
    return {"status": "ok", "mode": "local"}


# Static files and health must be registered before the API catch-all.
app.mount("/images", StaticFiles(directory=str(IMAGES_DIR)), name="images")


@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def dispatch(request: Request, path: str) -> Response:
    from routes import resolve

    resolved = resolve(request.method.upper(), "/" + path.rstrip("/"))
    if resolved is None:
        return JSONResponse(status_code=404, content={"error": "Not Found"})
    handler, params = resolved
    try:
        body = await request.body()
        authorization = request.headers.get("authorization", "")
        token = authorization[7:].strip() if authorization.lower().startswith("bearer ") else None
        req = http.Request(
            method=request.method,
            path=request.url.path,
            path_params=params,
            query=dict(request.query_params),
            headers=dict(request.headers),
            raw_body=body.decode("utf-8") if body else None,
            caller=local_auth.caller_from_token(token),
        )
        result = handler(req)
    except UnicodeDecodeError:
        result = http.error(400, "Request must be UTF-8 encoded.")
    except ApiError as exc:
        result = http.error(exc.status, exc.message, exc.error_code)
    except Exception:
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        result = http.error(500, "Internal Server Error")
    headers = {
        key: value for key, value in result.get("headers", {}).items() if not key.lower().startswith("access-control-")
    }
    content = result.get("body", "")
    if result.get("isBase64Encoded"):
        content = base64.b64decode(content)
    return Response(status_code=result["statusCode"], content=content, headers=headers)
