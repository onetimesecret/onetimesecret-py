"""Synchronous and asynchronous clients."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

import anyio
import httpx

from ._base_client import BaseClient, RequestSpec
from ._config import ClientConfig
from .resources import _specs
from .resources.receipts import AsyncReceipts, Receipts
from .resources.secrets import AsyncSecrets, Secrets

if TYPE_CHECKING:
    from collections.abc import Mapping
    from types import TracebackType

    from typing_extensions import Self

    from ._response import Response


class Client(BaseClient):
    """Synchronous client for the Onetime Secret API (v2).

    Example:
        >>> client = Client(
        ...     base_url="https://ca.onetimesecret.com",
        ...     customer="ur1abc23def",
        ...     api_token="...",
        ... )
        >>> res = client.secrets.conceal("hunter2", ttl=3600)
        >>> res["record"]["secret"]["identifier"]

    A client holds one ``httpx.Client`` with a connection pool, so reuse it
    across requests and close it when done (or use it as a context manager).
    It is safe to share between threads.

    Args:
        base_url: Your region's API host, self-hosted domain, or custom domain
            (``ONETIME_BASE_URL``). Required; the apex ``onetimesecret.com`` is
            the company website and is rejected.
        customer: Your customer extid, the ``ur…`` identifier
            (``ONETIME_CUSTOMER_EXTID``).
        api_token: Your API token (``ONETIME_API_TOKEN``).
        timeout: Per-request timeout in seconds (default 30).
        max_retries: Retries for idempotent (GET, HEAD) requests on connection
            errors and 429/5xx responses (default 2). POST requests are never
            retried.
        user_agent: Overrides the default ``User-Agent``.
        default_headers: Extra headers sent with every request.
        http_client: A preconfigured ``httpx.Client`` (proxies, custom TLS,
            transports for testing). The client takes ownership and closes it.
    """

    def __init__(
        self,
        *,
        base_url: str | None = None,
        customer: str | None = None,
        api_token: str | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
        user_agent: str | None = None,
        default_headers: Mapping[str, str] | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        config = ClientConfig.create(
            base_url=base_url,
            customer=customer,
            api_token=api_token,
            timeout=timeout,
            max_retries=max_retries,
            user_agent=user_agent,
            default_headers=dict(default_headers) if default_headers else None,
        )
        super().__init__(config)
        self._http = http_client or httpx.Client(timeout=self._timeout())
        self._http.base_url = httpx.URL(config.api_base + "/")
        self._http.headers.update(self._headers())
        auth = self._auth()
        if auth is not None:
            self._http.auth = auth
        self.secrets = Secrets(self)
        self.receipts = Receipts(self)

    # --- Meta endpoints -------------------------------------------------

    def status(self) -> Response:
        """Service status (public)."""
        return self._send(_specs.status())

    def version(self) -> Response:
        """Service version (requires authentication)."""
        return self._send(_specs.version())

    def supported_locales(self) -> Response:
        """Locales supported by the service (public)."""
        return self._send(_specs.supported_locales())

    # --- Low-level -------------------------------------------------------

    def request(
        self,
        method: str,
        path: str,
        *,
        json: Mapping[str, Any] | None = None,
        params: Mapping[str, Any] | None = None,
        raise_on_error: bool = True,
    ) -> Response:
        """Issue a request against an arbitrary path under ``/api/v2``.

        Useful for endpoints this library does not wrap yet. ``path`` is
        relative to the version prefix, e.g. ``"/secret/conceal"``. With
        ``raise_on_error=False`` an error status is returned as a
        :class:`Response` instead of raising; retries still apply.
        """
        spec = RequestSpec(method.upper(), path, json=json, params=params)
        return self._send(spec, raise_on_error=raise_on_error)

    def _send(self, spec: RequestSpec, *, raise_on_error: bool = True) -> Response:
        attempt = 0
        while True:
            try:
                raw = self._http.request(**self._request_kwargs(spec))
            except httpx.HTTPError as exc:
                if self._should_retry_error(spec.method, exc, attempt):
                    attempt += 1
                    time.sleep(self._backoff(attempt))
                    continue
                raise self._wrap_transport_error(exc) from exc
            if self._should_retry_status(spec.method, raw.status_code, attempt):
                attempt += 1
                time.sleep(self._backoff(attempt, raw))
                continue
            return self._process(raw, raise_on_error=raise_on_error)

    # --- Lifecycle -------------------------------------------------------

    def close(self) -> None:
        """Close the underlying connection pool."""
        self._http.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()


class AsyncClient(BaseClient):
    """Asynchronous client for the Onetime Secret API (v2).

    Accepts the same arguments as :class:`Client`; ``http_client`` is an
    ``httpx.AsyncClient``. Works with asyncio and trio.

    Example:
        >>> async with AsyncClient(base_url="https://eu.onetimesecret.com") as client:
        ...     res = await client.secrets.conceal("hunter2", guest=True)
    """

    def __init__(
        self,
        *,
        base_url: str | None = None,
        customer: str | None = None,
        api_token: str | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
        user_agent: str | None = None,
        default_headers: Mapping[str, str] | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        config = ClientConfig.create(
            base_url=base_url,
            customer=customer,
            api_token=api_token,
            timeout=timeout,
            max_retries=max_retries,
            user_agent=user_agent,
            default_headers=dict(default_headers) if default_headers else None,
        )
        super().__init__(config)
        self._http = http_client or httpx.AsyncClient(timeout=self._timeout())
        self._http.base_url = httpx.URL(config.api_base + "/")
        self._http.headers.update(self._headers())
        auth = self._auth()
        if auth is not None:
            self._http.auth = auth
        self.secrets = AsyncSecrets(self)
        self.receipts = AsyncReceipts(self)

    # --- Meta endpoints -------------------------------------------------

    async def status(self) -> Response:
        """Service status (public)."""
        return await self._send(_specs.status())

    async def version(self) -> Response:
        """Service version (requires authentication)."""
        return await self._send(_specs.version())

    async def supported_locales(self) -> Response:
        """Locales supported by the service (public)."""
        return await self._send(_specs.supported_locales())

    # --- Low-level -------------------------------------------------------

    async def request(
        self,
        method: str,
        path: str,
        *,
        json: Mapping[str, Any] | None = None,
        params: Mapping[str, Any] | None = None,
        raise_on_error: bool = True,
    ) -> Response:
        """Issue a request against an arbitrary path under ``/api/v2``.

        See :meth:`Client.request`.
        """
        spec = RequestSpec(method.upper(), path, json=json, params=params)
        return await self._send(spec, raise_on_error=raise_on_error)

    async def _send(self, spec: RequestSpec, *, raise_on_error: bool = True) -> Response:
        attempt = 0
        while True:
            try:
                raw = await self._http.request(**self._request_kwargs(spec))
            except httpx.HTTPError as exc:
                if self._should_retry_error(spec.method, exc, attempt):
                    attempt += 1
                    await anyio.sleep(self._backoff(attempt))
                    continue
                raise self._wrap_transport_error(exc) from exc
            if self._should_retry_status(spec.method, raw.status_code, attempt):
                attempt += 1
                await anyio.sleep(self._backoff(attempt, raw))
                continue
            return self._process(raw, raise_on_error=raise_on_error)

    # --- Lifecycle -------------------------------------------------------

    async def aclose(self) -> None:
        """Close the underlying connection pool."""
        await self._http.aclose()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.aclose()
