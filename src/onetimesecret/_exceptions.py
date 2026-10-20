"""Exception hierarchy.

Every exception raised by this library derives from :class:`OnetimeSecretError`.
API errors follow the server's ADR-013 wire format::

    {"error": "<user-facing message>", "error_type": "<ClassName>", ...}

plus optional class-specific fields (``field``, ``error_key``, ``code``,
``retry_after``, ``entitlement``) and a cross-cutting ``request_id``.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import httpx


class OnetimeSecretError(Exception):
    """Base class for every error raised by this library."""


class ConfigurationError(OnetimeSecretError):
    """The client was constructed with an invalid or incomplete configuration."""


class APIConnectionError(OnetimeSecretError):
    """A request never produced an HTTP response (DNS, refused connection, TLS, reset).

    The underlying ``httpx`` exception is available as ``__cause__``.
    """


class APITimeoutError(APIConnectionError):
    """A request exceeded the configured timeout."""


class APIError(OnetimeSecretError):
    """An HTTP response with status >= 400.

    Attributes:
        message: The user-facing message from the ``error`` field.
        status_code: HTTP status code.
        error_type: The server's machine-readable type, e.g. ``"RecordNotFound"``.
        field: The offending field for form errors.
        error_key: i18n lookup key, when the server sends one.
        code: Per-operation discriminator (e.g. ``"GUEST_CONCEAL_DISABLED"``).
        retry_after: Seconds to wait before retrying, for rate limits.
        entitlement: The missing entitlement, for ``EntitlementRequired``.
        request_id: Correlation id echoed from ``x-request-id``.
        body: The parsed response body (a dict when the body was a JSON object).
        response: The underlying ``httpx.Response``.
    """

    def __init__(
        self,
        message: str,
        *,
        response: httpx.Response,
        body: Any = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.response = response
        self.status_code: int = response.status_code
        self.body = body
        data: Mapping[str, Any] = body if isinstance(body, Mapping) else {}
        self.error_type: str | None = _opt_str(data.get("error_type"))
        self.field: str | None = _opt_str(data.get("field"))
        self.error_key: str | None = _opt_str(data.get("error_key"))
        self.code: str | None = _opt_str(data.get("code"))
        self.retry_after: float | None = _retry_after(data, response)
        self.entitlement: str | None = _opt_str(data.get("entitlement"))
        self.request_id: str | None = _opt_str(data.get("request_id")) or response.headers.get(
            "x-request-id"
        )

    def __str__(self) -> str:
        parts = [self.message, f"(status={self.status_code}"]
        if self.error_type:
            parts.append(f"type={self.error_type}")
        if self.request_id:
            parts.append(f"request_id={self.request_id}")
        return " ".join(parts) + ")"


class BadRequestError(APIError):
    """400 / 422, or an ADR-013 ``FormError``."""


class AuthenticationError(APIError):
    """401: the credentials were missing, malformed, or rejected."""


class AccountRequiredError(AuthenticationError):
    """The operation needs an authenticated account.

    The server reports this inside a form-error body (``field: "requires_account"``)
    rather than with a status of its own. It is an authentication problem, not a
    payload problem, so it lives under :class:`AuthenticationError`.
    """


class ForbiddenError(APIError):
    """403, or ``Forbidden`` / ``GuestRoutesDisabled``."""


class EntitlementError(ForbiddenError):
    """``EntitlementRequired``: the account's plan does not include this feature."""


class NotFoundError(APIError):
    """404 / ``RecordNotFound``."""


class ConflictError(APIError):
    """409."""


class RateLimitError(APIError):
    """429 / ``LimitExceeded``. See :attr:`APIError.retry_after`."""


class ServerError(APIError):
    """5xx / ``ServerError``."""


# --- Mapping -------------------------------------------------------------

_ERROR_TYPE_MAP: dict[str, type[APIError]] = {
    "FormError": BadRequestError,
    "RequiresAccount": AccountRequiredError,
    "AccountRequired": AccountRequiredError,
    "RecordNotFound": NotFoundError,
    "NotFound": NotFoundError,
    "Forbidden": ForbiddenError,
    "GuestRoutesDisabled": ForbiddenError,
    "EntitlementRequired": EntitlementError,
    "LimitExceeded": RateLimitError,
    "ServerError": ServerError,
}

_STATUS_MAP: dict[int, type[APIError]] = {
    400: BadRequestError,
    401: AuthenticationError,
    403: ForbiddenError,
    404: NotFoundError,
    409: ConflictError,
    422: BadRequestError,
    429: RateLimitError,
}

# The account requirement may arrive in any of several slots depending on the
# endpoint: the FormError `field`, the i18n `error_key`, or a `code` such as
# "GUEST_CONCEAL_REQUIRES_ACCOUNT". Underscores are word characters, so \b is
# no help; match explicit non-alphanumeric boundaries instead.
_ACCOUNT_REQUIRED_KEYS = ("error_type", "field", "error_key", "code")
_ACCOUNT_REQUIRED_PATTERN = re.compile(
    r"(?:^|[^a-z0-9])(requires[_-]?account|account[_-]?required)(?:$|[^a-z0-9])",
    re.IGNORECASE,
)

_ACCOUNT_REQUIRED_MESSAGE = (
    "This operation requires an authenticated account: pass your customer "
    "extid and API token to the client."
)


def error_from_response(response: httpx.Response, body: Any) -> APIError:
    """Build the appropriate :class:`APIError` subclass for a failed response."""
    data: Mapping[str, Any] = body if isinstance(body, Mapping) else {}
    status = response.status_code

    account_required = any(
        _ACCOUNT_REQUIRED_PATTERN.search(str(data.get(key) or ""))
        for key in _ACCOUNT_REQUIRED_KEYS
    )
    if account_required:
        cls: type[APIError] = AccountRequiredError
    else:
        cls = _error_class(_opt_str(data.get("error_type")), status)

    message = _opt_str(data.get("error")) or _opt_str(data.get("message"))
    if not message:
        message = _ACCOUNT_REQUIRED_MESSAGE if account_required else _default_message(status)

    return cls(message, response=response, body=body)


def _error_class(error_type: str | None, status: int) -> type[APIError]:
    if error_type and error_type in _ERROR_TYPE_MAP:
        return _ERROR_TYPE_MAP[error_type]
    if status in _STATUS_MAP:
        return _STATUS_MAP[status]
    return ServerError if status >= 500 else APIError


def _default_message(status: int) -> str:
    if status == 400:
        return "Bad request"
    if status == 401:
        return "Authentication failed"
    if status == 403:
        return "Forbidden"
    if status == 404:
        return "Not found"
    if status == 429:
        return "Rate limit exceeded"
    if status >= 500:
        return f"Server error ({status})"
    return f"Request failed ({status})"


def _opt_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text or None


def _retry_after(data: Mapping[str, Any], response: httpx.Response) -> float | None:
    raw: Any = data.get("retry_after")
    if raw is None:
        raw = response.headers.get("retry-after")
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None
