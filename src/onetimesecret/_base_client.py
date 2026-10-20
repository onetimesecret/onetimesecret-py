"""Request building, response handling and retry policy shared by both clients.

Nothing here performs I/O. :class:`Client` and :class:`AsyncClient` own the
``httpx`` client and drive the retry loop; this module decides what to send
and how to interpret what comes back.
"""

from __future__ import annotations

import json
import logging
import platform
import random
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import httpx

from ._exceptions import (
    APIConnectionError,
    APITimeoutError,
    error_from_response,
)
from ._response import Response
from ._version import __version__

if TYPE_CHECKING:
    from collections.abc import Mapping

    from ._config import ClientConfig

log = logging.getLogger("onetimesecret")

RETRYABLE_STATUSES = frozenset({429, 500, 502, 503, 504})
# Only idempotent requests are retried. POST is never retried: concealing
# twice creates two secrets, and revealing or burning is destructive.
IDEMPOTENT_METHODS = frozenset({"GET", "HEAD"})

_BACKOFF_BASE = 0.5
_BACKOFF_CAP = 8.0


@dataclass(frozen=True, slots=True)
class RequestSpec:
    """A fully described API request, relative to the ``/api/v2`` prefix."""

    method: str
    path: str
    json: Mapping[str, Any] | None = None
    params: Mapping[str, Any] | None = None


class BaseClient:
    """Shared, I/O-free machinery for :class:`Client` and :class:`AsyncClient`."""

    def __init__(self, config: ClientConfig) -> None:
        self._config = config

    @property
    def config(self) -> ClientConfig:
        """The validated client configuration."""
        return self._config

    @property
    def base_url(self) -> str:
        """The configured base URL (scheme and host, no API prefix)."""
        return self._config.base_url

    # --- Request construction ------------------------------------------

    def _auth(self) -> httpx.BasicAuth | None:
        cfg = self._config
        if cfg.customer is None or cfg.api_token is None:
            return None
        return httpx.BasicAuth(cfg.customer, cfg.api_token)

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "User-Agent": self._config.user_agent or default_user_agent(),
        }
        headers.update(self._config.default_headers)
        return headers

    def _timeout(self) -> httpx.Timeout:
        return httpx.Timeout(self._config.timeout)

    def _request_kwargs(self, spec: RequestSpec) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "method": spec.method,
            "url": spec.path.lstrip("/"),
        }
        if spec.json is not None:
            kwargs["json"] = dict(spec.json)
        if spec.params is not None:
            kwargs["params"] = dict(spec.params)
        return kwargs

    # --- Response handling ----------------------------------------------

    def _process(self, raw: httpx.Response) -> Response:
        data = _parse_body(raw)
        log.debug("%s %s -> %s", raw.request.method, raw.request.url, raw.status_code)
        if raw.status_code >= 400:
            raise error_from_response(raw, data)
        return Response(raw, data)

    # --- Retry policy ---------------------------------------------------

    def _should_retry_status(self, method: str, status: int, attempt: int) -> bool:
        return (
            method.upper() in IDEMPOTENT_METHODS
            and status in RETRYABLE_STATUSES
            and attempt < self._config.max_retries
        )

    def _should_retry_error(self, method: str, exc: httpx.HTTPError, attempt: int) -> bool:
        return (
            method.upper() in IDEMPOTENT_METHODS
            and isinstance(exc, httpx.TransportError)
            and not isinstance(exc, httpx.ProtocolError)
            and attempt < self._config.max_retries
        )

    def _backoff(self, attempt: int, raw: httpx.Response | None = None) -> float:
        """Seconds to sleep before retry number ``attempt`` (1-based)."""
        if raw is not None:
            header = raw.headers.get("retry-after")
            if header is not None:
                try:
                    return float(min(max(float(header), 0.0), _BACKOFF_CAP))
                except ValueError:
                    pass
        delay: float = min(_BACKOFF_BASE * (2 ** (attempt - 1)), _BACKOFF_CAP)
        return delay * (0.5 + random.random() / 2)  # noqa: S311 - jitter, not crypto

    @staticmethod
    def _wrap_transport_error(exc: httpx.HTTPError) -> APIConnectionError:
        if isinstance(exc, httpx.TimeoutException):
            err: APIConnectionError = APITimeoutError(f"Request timed out: {exc}")
        else:
            err = APIConnectionError(f"Connection error: {exc}")
        err.__cause__ = exc
        return err


def default_user_agent() -> str:
    """The default ``User-Agent`` header value."""
    return (
        f"onetime-secret-python/{__version__} "
        f"python/{platform.python_version()} httpx/{httpx.__version__}"
    )


def _parse_body(raw: httpx.Response) -> Any:
    if not raw.content:
        return None
    try:
        return raw.json()
    except (json.JSONDecodeError, UnicodeDecodeError):
        # A proxy or load balancer may answer with HTML; keep the text so the
        # caller can see what came back.
        return raw.text
