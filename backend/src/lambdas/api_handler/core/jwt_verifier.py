"""Verification of Cognito ID tokens on routes without the API Gateway authorizer.

Used where the original API is public but the response depends on who is asking
(e.g. the reservation owner opening their own group invite). RS256 is verified with
the user pool JWKS using only the standard library, so no native packages are needed.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import time
import urllib.request
from typing import Any

from core import config
from core.auth import Caller, caller_from_claims

logger = logging.getLogger(__name__)

# DER prefix of DigestInfo for SHA-256 (RFC 8017, section 9.2, note 1).
_SHA256_DIGEST_INFO = bytes.fromhex("3031300d060960864801650304020105000420")
_JWKS_TTL_SECONDS = 3600
_jwks_cache: dict[str, Any] = {"keys": None, "loaded_at": 0.0}


def _b64url_decode(segment: str) -> bytes:
    return base64.urlsafe_b64decode(segment + "=" * (-len(segment) % 4))


def _issuer() -> str:
    return f"https://cognito-idp.{config.region()}.amazonaws.com/{config.user_pool_id()}"


def _fetch_jwks() -> dict[str, dict[str, Any]]:
    with urllib.request.urlopen(f"{_issuer()}/.well-known/jwks.json", timeout=3) as response:  # noqa: S310
        keys = json.loads(response.read())["keys"]
    return {key["kid"]: key for key in keys}


def _signing_key(kid: str) -> dict[str, Any] | None:
    now = time.time()
    keys = _jwks_cache["keys"]
    if keys is None or kid not in keys or now - _jwks_cache["loaded_at"] > _JWKS_TTL_SECONDS:
        try:
            keys = _fetch_jwks()
        except Exception:  # network/JSON errors mean "cannot verify", never "trusted"
            logger.warning("Unable to load Cognito JWKS", exc_info=True)
            return None
        _jwks_cache.update(keys=keys, loaded_at=now)
    return keys.get(kid)


def set_jwks(keys: list[dict[str, Any]]) -> None:
    """Install a JWKS directly (tests and local runs)."""
    _jwks_cache.update(keys={key["kid"]: key for key in keys}, loaded_at=time.time())


def _rs256_valid(signing_input: bytes, signature: bytes, jwk: dict[str, Any]) -> bool:
    n = int.from_bytes(_b64url_decode(jwk["n"]), "big")
    e = int.from_bytes(_b64url_decode(jwk["e"]), "big")
    key_len = (n.bit_length() + 7) // 8
    if len(signature) != key_len:
        return False
    encoded = pow(int.from_bytes(signature, "big"), e, n).to_bytes(key_len, "big")
    digest_info = _SHA256_DIGEST_INFO + hashlib.sha256(signing_input).digest()
    padding = b"\xff" * (key_len - len(digest_info) - 3)
    # Compare the whole EMSA-PKCS1-v1_5 block rather than parsing it.
    return encoded == b"\x00\x01" + padding + b"\x00" + digest_info


def verify_id_token(token: str | None) -> dict[str, Any] | None:
    """Claims of a valid, unexpired ID token issued by this user pool for this app client, else None."""
    if not token or token.count(".") != 2 or not config.user_pool_id():
        return None
    try:
        header_b64, payload_b64, signature_b64 = token.split(".")
        header = json.loads(_b64url_decode(header_b64))
        claims = json.loads(_b64url_decode(payload_b64))
        signature = _b64url_decode(signature_b64)
    except ValueError:
        return None
    if not isinstance(header, dict) or header.get("alg") != "RS256" or not isinstance(claims, dict):
        return None
    jwk = _signing_key(str(header.get("kid", "")))
    if jwk is None or not _rs256_valid(f"{header_b64}.{payload_b64}".encode(), signature, jwk):
        return None
    if claims.get("iss") != _issuer() or claims.get("token_use") != "id":
        return None
    if claims.get("aud") != config.user_pool_client_id():
        return None
    if not isinstance(claims.get("exp"), (int, float)) or claims["exp"] < time.time() - 60:
        return None
    return claims


def optional_caller(token: str | None) -> Caller | None:
    return caller_from_claims(verify_id_token(token))
