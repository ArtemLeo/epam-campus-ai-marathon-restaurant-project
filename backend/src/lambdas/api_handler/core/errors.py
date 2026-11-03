"""Domain errors mapped to HTTP responses by the router (main.py)."""

from __future__ import annotations

# Machine-readable codes returned with guest pre-order errors (ErrorCodeResponse in the original API).
GROUP_RESERVATION_EXPIRED = "GroupReservationExpired"
GROUP_RESERVATION_SUBMITTED = "GroupReservationSubmitted"
GUEST_LIMIT_EXCEEDED = "GuestLimitExceeded"
GUEST_SESSION_EXPIRED = "GuestSessionExpired"


class ApiError(Exception):
    """Error that becomes an HTTP response with ``status`` and ``{"error": message}`` body."""

    status = 500

    def __init__(self, message: str, *, status: int | None = None, error_code: str | None = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        if status is not None:
            self.status = status

    def with_status(self, status: int) -> ApiError:
        return ApiError(self.message, status=status, error_code=self.error_code)


class BadRequest(ApiError):
    status = 400


class Unauthorized(ApiError):
    status = 401


class Forbidden(ApiError):
    status = 403


class NotFound(ApiError):
    status = 404


class Conflict(ApiError):
    status = 409


def group_expired(message: str = "Group reservation is expired.") -> BadRequest:
    return BadRequest(message, error_code=GROUP_RESERVATION_EXPIRED)


def group_submitted(message: str = "Group reservation was submitted.") -> BadRequest:
    return BadRequest(message, error_code=GROUP_RESERVATION_SUBMITTED)


def guest_limit_exceeded(message: str = "Guest limit exceeded for this reservation.") -> BadRequest:
    return BadRequest(message, error_code=GUEST_LIMIT_EXCEEDED)


def guest_session_expired(message: str) -> BadRequest:
    return BadRequest(message, error_code=GUEST_SESSION_EXPIRED)
