"""Local user store replacing Cognito for Docker-based development.

Users are kept in a DynamoDB table (LocalUsers) so they survive container restarts.
JWTs are signed with a local secret — no Cognito user pool needed.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import time
import uuid
from functools import cache
from pathlib import Path
from typing import Any

from core import config, dynamo
from core.auth import CUSTOMER, Caller, parse_groups
from core.errors import BadRequest, Conflict, NotFound, Unauthorized
from core.validation import validate_email, validate_name, validate_password, validate_passwords


@cache
def _secret() -> str:
    if os.environ.get("LOCAL_AUTH_SECRET"):
        return os.environ["LOCAL_AUTH_SECRET"]
    path = Path(os.environ.get("LOCAL_DATA_DIR", "/app/data")) / "auth-secret"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(secrets.token_urlsafe(48))
        path.chmod(0o600)
    return path.read_text().strip()


TOKEN_TTL = 86400

USERS_TABLE = "local_users"

config.TABLES["local_users"] = ("localUsersTable", "LocalUsers")


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 260000).hex()
    return f"pbkdf2_sha256${salt}${digest}"


def _password_matches(password: str, stored: str) -> bool:
    if stored.startswith("pbkdf2_sha256$"):
        _, salt, digest = stored.split("$", 2)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 260000).hex()
    else:  # Upgrade existing local demo accounts at their next successful login.
        digest, actual = stored, hashlib.sha256(password.encode()).hexdigest()
    return hmac.compare_digest(actual, digest)


def _make_jwt(payload: dict[str, Any]) -> str:
    header = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    body = _b64(json.dumps(payload).encode())
    sig = _b64(hmac.new(_secret().encode(), f"{header}.{body}".encode(), hashlib.sha256).digest())
    return f"{header}.{body}.{sig}"


def _b64(data: bytes) -> str:
    import base64

    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _decode_jwt(token: str) -> dict[str, Any] | None:
    import base64

    if not isinstance(token, str):
        return None
    parts = token.split(".")
    if len(parts) != 3:
        return None
    header, body, sig = parts
    expected = _b64(hmac.new(_secret().encode(), f"{header}.{body}".encode(), hashlib.sha256).digest())
    if not hmac.compare_digest(sig, expected):
        return None
    try:
        payload = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
    except (ValueError, TypeError):
        return None
    if not isinstance(payload, dict) or not isinstance(payload.get("exp"), (int, float)):
        return None
    if payload["exp"] < time.time() or not payload.get("sub") or not payload.get("email"):
        return None
    return payload


def caller_from_token(token: str | None) -> Caller | None:
    if not token:
        return None
    payload = _decode_jwt(token)
    if not payload:
        return None
    return Caller(
        user_id=payload["sub"],
        email=payload.get("email"),
        username=payload.get("email"),
        groups=parse_groups(payload.get("cognito:groups")),
    )


def _get_user(email: str) -> dict[str, Any] | None:
    return dynamo.get_item(USERS_TABLE, {"email": email})


def register(first_name: Any, last_name: Any, email: Any, password: Any, confirm_password: Any) -> None:
    validate_name(first_name, "First name")
    validate_name(last_name, "Last name")
    email = validate_email(email).strip().lower()
    validate_passwords(password, confirm_password)

    if _get_user(email):
        raise Conflict("A user with this email address already exists.")

    user_id = str(uuid.uuid4())
    dynamo.put_item(
        USERS_TABLE,
        {
            "email": email,
            "sub": user_id,
            "given_name": first_name,
            "family_name": last_name,
            "password_hash": hash_password(password),
            "groups": [CUSTOMER],
        },
    )


def sign_in(email: Any, password: Any) -> dict[str, Any]:
    email = validate_email(email).strip().lower()
    validate_password(password)

    user = _get_user(email)
    if not user or not _password_matches(password, user["password_hash"]):
        raise Unauthorized("Invalid email or password")
    if not user["password_hash"].startswith("pbkdf2_sha256$"):
        user["password_hash"] = hash_password(password)
        dynamo.put_item(USERS_TABLE, user)

    groups = list(user.get("groups") or [CUSTOMER])
    now = time.time()
    payload = {
        "sub": user["sub"],
        "email": user["email"],
        "cognito:username": user["email"],
        "cognito:groups": groups,
        "given_name": user.get("given_name", ""),
        "family_name": user.get("family_name", ""),
        "iat": int(now),
        "exp": int(now + TOKEN_TTL),
    }
    token = _make_jwt(payload)
    return {"message": "Sign in successful", "idToken": token, "accessToken": token}


def current_user(caller: Caller) -> dict[str, Any]:
    from core.auth import primary_role

    user = _find_user_by_id(caller.user_id)
    if not user:
        raise Unauthorized("User is not authenticated.")
    groups = tuple(user.get("groups") or [CUSTOMER])
    return {
        "id": caller.user_id,
        "firstName": user.get("given_name", "Unknown"),
        "lastName": user.get("family_name", "User"),
        "email": user.get("email", "no_email"),
        "role": primary_role(groups),
    }


def _find_user_by_id(user_id: str) -> dict[str, Any] | None:
    for user in dynamo.scan_all(USERS_TABLE):
        if user.get("sub") == user_id:
            return user
    return None


def update_profile(caller: Caller, first_name: Any, last_name: Any) -> None:
    validate_name(first_name, "First name")
    validate_name(last_name, "Last name")
    user = _find_user_by_id(caller.user_id)
    if not user:
        raise Unauthorized("User is not authenticated.")
    user["given_name"] = first_name
    user["family_name"] = last_name
    dynamo.put_item(USERS_TABLE, user)


def change_password(old_password: Any, new_password: Any, access_token: Any) -> None:
    validate_password(old_password)
    validate_passwords(new_password, new_password)
    payload = _decode_jwt(access_token) if isinstance(access_token, str) else None
    if not payload:
        raise BadRequest("Access token is required.")
    user = _get_user(payload["email"])
    if not user or not _password_matches(old_password, user["password_hash"]):
        raise BadRequest("The old password is incorrect or the session has expired.")
    user["password_hash"] = hash_password(new_password)
    dynamo.put_item(USERS_TABLE, user)


def search_users(full_name: Any) -> list[dict[str, Any]]:
    if not isinstance(full_name, str) or not full_name.strip():
        raise BadRequest("Missing or empty 'fullName' query parameter.")
    names = full_name.split()
    first = validate_name(names[0], "First name").lower()
    last = validate_name(names[1], "Last name").lower() if len(names) > 1 else ""
    results = []
    for user in dynamo.scan_all(USERS_TABLE):
        gn = (user.get("given_name") or "").lower()
        fn = (user.get("family_name") or "").lower()
        if not gn.startswith(first):
            continue
        if last and fn != last:
            continue
        results.append(
            {
                "id": user["sub"],
                "firstName": user.get("given_name", "Unknown"),
                "lastName": user.get("family_name", "User"),
                "email": user.get("email", "no_email"),
                "role": CUSTOMER,
            }
        )
    return results


def user_name(user_id: str) -> str:
    user = _find_user_by_id(user_id)
    if not user:
        return "Anonymous User"
    return f"{user.get('given_name', '')} {user.get('family_name', '')}".strip() or "Anonymous User"


def require_user_id_by_email(email: str) -> str:
    user = _get_user(email.strip().lower())
    if not user:
        raise NotFound(f"User with email {email} is not registered")
    return user["sub"]


def user_by_email(email: str) -> dict[str, Any] | None:
    return _get_user(email.strip().lower())


def user_by_id(user_id: str) -> dict[str, Any] | None:
    return _find_user_by_id(user_id)


def full_name(user_id: str | None) -> str | None:
    if not user_id:
        return None
    user = _find_user_by_id(user_id)
    if not user:
        return None
    name = f"{user.get('given_name', '')} {user.get('family_name', '')}".strip()
    return name or None


def groups_of(email: str) -> list[str]:
    user = _get_user(email)
    return list(user.get("groups", [])) if user else []


def add_to_group(email: str, group: str) -> None:
    user = _get_user(email)
    if not user:
        return
    groups = list(user.get("groups") or [])
    if group not in groups:
        groups.append(group)
    user["groups"] = groups
    dynamo.put_item(USERS_TABLE, user)


def remove_from_group(email: str, group: str) -> None:
    user = _get_user(email)
    if not user:
        return
    groups = [g for g in (user.get("groups") or []) if g != group]
    user["groups"] = groups
    dynamo.put_item(USERS_TABLE, user)


def forgot_password(email: Any) -> dict[str, Any]:
    """Local demo recovery: return the code because this mode does not send emails."""
    email = validate_email(email).strip().lower()
    user = _get_user(email)
    result = {"message": "If the account exists, a password reset code has been issued."}
    if user:
        code = f"{secrets.randbelow(1000000):06d}"
        user["reset_hash"] = hashlib.sha256(code.encode()).hexdigest()
        user["reset_expires"] = int(time.time()) + 600
        user["reset_attempts"] = 0
        dynamo.put_item(USERS_TABLE, user)
        result["resetCode"] = code
    return result


def reset_password(email: Any, code: Any, new_password: Any) -> None:
    email = validate_email(email).strip().lower()
    validate_passwords(new_password, new_password)
    user = _get_user(email)
    if not user or not isinstance(code, str):
        raise BadRequest("Invalid or expired reset code.")
    if user.get("reset_expires", 0) < time.time() or user.get("reset_attempts", 0) >= 5:
        raise BadRequest("Invalid or expired reset code.")
    user["reset_attempts"] = int(user.get("reset_attempts", 0)) + 1
    if not hmac.compare_digest(user.get("reset_hash", ""), hashlib.sha256(code.encode()).hexdigest()):
        dynamo.put_item(USERS_TABLE, user)
        raise BadRequest("Invalid or expired reset code.")
    user["password_hash"] = hash_password(new_password)
    for key in ("reset_hash", "reset_expires", "reset_attempts"):
        user.pop(key, None)
    dynamo.put_item(USERS_TABLE, user)


def confirm_registration(email: Any, code: Any) -> None:
    validate_email(email)
    raise BadRequest("Local accounts are confirmed automatically. You can sign in immediately.")


def resend_confirmation(email: Any) -> None:
    validate_email(email)
    raise BadRequest("Local accounts are confirmed automatically. You can sign in immediately.")


def update_attributes(email: str, values: dict[str, str]) -> None:
    user = _get_user(email)
    if user:
        user.update(values)
        dynamo.put_item(USERS_TABLE, user)


def users_in_group(group: str) -> list[dict[str, Any]]:
    return [user for user in dynamo.scan_all(USERS_TABLE) if group in user.get("groups", [])]


def users_by_given_name_prefix(prefix: str) -> list[dict[str, Any]]:
    return [
        user for user in dynamo.scan_all(USERS_TABLE) if user.get("given_name", "").lower().startswith(prefix.lower())
    ]
