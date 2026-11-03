"""Caller identity from Cognito claims and role checks.

Routes protected by the API Gateway Cognito authorizer receive verified claims in
``requestContext.authorizer.claims``. Unverified tokens are never trusted here; public
routes that need an optional identity use ``core.jwt_verifier``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from core.errors import Forbidden, Unauthorized

ADMIN = "Admin"
WAITER = "Waiter"
CUSTOMER = "Customer"
# Lower index wins when a user belongs to several groups (Roles enum order in the original).
ROLE_PRIORITY = (ADMIN, WAITER, CUSTOMER)


def parse_groups(raw: Any) -> tuple[str, ...]:
    """Accept the shapes API Gateway uses for ``cognito:groups``: list, JSON, ``[a, b]`` or ``a,b``."""
    if not raw:
        return ()
    if isinstance(raw, (list, tuple)):
        items = [str(item) for item in raw]
    else:
        text = str(raw).strip()
        try:
            loaded = json.loads(text)
            items = [str(item) for item in loaded] if isinstance(loaded, list) else [str(loaded)]
        except ValueError:
            items = text.strip("[]").replace(",", " ").split()
    return tuple(item.strip().strip("\"'") for item in items if item.strip().strip("\"'"))


def primary_role(groups: tuple[str, ...]) -> str:
    return next((role for role in ROLE_PRIORITY if role in groups), CUSTOMER)


@dataclass(frozen=True)
class Caller:
    user_id: str
    email: str | None = None
    username: str | None = None
    groups: tuple[str, ...] = ()

    @property
    def role(self) -> str:
        return primary_role(self.groups)

    @property
    def is_admin(self) -> bool:
        return ADMIN in self.groups

    @property
    def is_waiter(self) -> bool:
        return WAITER in self.groups


def caller_from_claims(claims: dict[str, Any] | None) -> Caller | None:
    if not claims or not claims.get("sub"):
        return None
    return Caller(
        user_id=str(claims["sub"]),
        email=claims.get("email"),
        username=claims.get("cognito:username"),
        groups=parse_groups(claims.get("cognito:groups")),
    )


def require_caller(caller: Caller | None) -> Caller:
    if caller is None:
        raise Unauthorized("User is not authenticated.")
    return caller


def require_role(caller: Caller | None, *roles: str) -> Caller:
    """Authenticated caller that belongs to at least one of ``roles``."""
    caller = require_caller(caller)
    if not any(role in caller.groups for role in roles):
        raise Forbidden("You don't have enough permissions to perform this action.")
    return caller
