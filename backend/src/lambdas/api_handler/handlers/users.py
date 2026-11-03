"""/register, /signin, /me and /users endpoints."""

from __future__ import annotations

from typing import Any

from core import http
from core.auth import ADMIN, WAITER, require_caller, require_role
from core.http import Request
from services import users


def register(req: Request) -> dict[str, Any]:
    body = req.json()
    result = users.register(
        body.get("firstName"),
        body.get("lastName"),
        body.get("email"),
        body.get("password"),
        body.get("confirmPassword"),
    )
    return http.ok(result or {"message": "User registered successfully", "confirmationRequired": False})


def confirm_registration(req: Request) -> dict[str, Any]:
    body = req.json()
    users.confirm_registration(body.get("email"), body.get("code"))
    return http.message("Email confirmed. You can sign in.")


def resend_confirmation(req: Request) -> dict[str, Any]:
    return http.ok(users.resend_confirmation(req.json().get("email")))


def forgot_password(req: Request) -> dict[str, Any]:
    return http.ok(users.forgot_password(req.json().get("email")))


def reset_password(req: Request) -> dict[str, Any]:
    body = req.json()
    users.reset_password(body.get("email"), body.get("code"), body.get("newPassword"))
    return http.message("Password reset. You can sign in with your new password.")


def sign_in(req: Request) -> dict[str, Any]:
    body = req.json()
    return http.ok(users.sign_in(body.get("email"), body.get("password")))


def me(req: Request) -> dict[str, Any]:
    return http.ok(users.current_user(require_caller(req.caller)))


def update_me(req: Request) -> dict[str, Any]:
    caller = require_caller(req.caller)
    body = req.json()
    users.update_profile(caller, body.get("firstName"), body.get("lastName"))
    return http.message("User information updated successfully.")


def change_password(req: Request) -> dict[str, Any]:
    require_caller(req.caller)
    body = req.json()
    users.change_password(body.get("oldPassword"), body.get("newPassword"), body.get("accessToken"))
    return http.message("Password changed successfully.")


def search(req: Request) -> dict[str, Any]:
    require_role(req.caller, WAITER, ADMIN)
    return http.ok(users.search_users(req.query.get("fullName")))


def name(req: Request) -> dict[str, Any]:
    require_caller(req.caller)
    return http.ok({"name": users.user_name(req.param("id"))})


def profile_image(req: Request) -> dict[str, Any]:
    url = users.profile_image_url(req.param("id"))
    return http.ok({"presignedUrl": url} if url else "Profile image is not uploaded so far.")


def upload_profile_image(req: Request) -> dict[str, Any]:
    caller = require_caller(req.caller)
    url = users.upload_profile_image(caller, req.json().get("base64Image"))
    return http.ok({"presignedUrl": url} if url else "Photo was uploaded successfully!")
