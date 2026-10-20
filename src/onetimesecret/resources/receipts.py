"""Receipt operations (creator-facing secret metadata): show, recent, burn, update."""

from __future__ import annotations

from typing import TYPE_CHECKING

from . import _specs

if TYPE_CHECKING:
    from .._client import AsyncClient, Client
    from .._response import Response


class Receipts:
    """Receipt operations on a :class:`onetimesecret.Client`."""

    def __init__(self, client: Client) -> None:
        self._client = client

    def show(self, key: str, *, guest: bool = False) -> Response:
        """Show a receipt by its key."""
        return self._client._send(_specs.show_receipt(key, guest=guest))

    def recent(self) -> Response:
        """List the authenticated customer's recent receipts (``res["records"]``)."""
        return self._client._send(_specs.recent_receipts())

    def burn(self, key: str, *, passphrase: str | None = None, guest: bool = False) -> Response:
        """Burn (destroy) an unread secret by its receipt key."""
        return self._client._send(_specs.burn(key, passphrase=passphrase, guest=guest))

    def update(self, key: str, *, memo: str) -> Response:
        """Update a receipt's memo (up to 500 characters)."""
        return self._client._send(_specs.update_receipt(key, memo=memo))


class AsyncReceipts:
    """Receipt operations on a :class:`onetimesecret.AsyncClient`."""

    def __init__(self, client: AsyncClient) -> None:
        self._client = client

    async def show(self, key: str, *, guest: bool = False) -> Response:
        """Show a receipt by its key."""
        return await self._client._send(_specs.show_receipt(key, guest=guest))

    async def recent(self) -> Response:
        """List the authenticated customer's recent receipts (``res["records"]``)."""
        return await self._client._send(_specs.recent_receipts())

    async def burn(
        self, key: str, *, passphrase: str | None = None, guest: bool = False
    ) -> Response:
        """Burn (destroy) an unread secret by its receipt key."""
        return await self._client._send(_specs.burn(key, passphrase=passphrase, guest=guest))

    async def update(self, key: str, *, memo: str) -> Response:
        """Update a receipt's memo (up to 500 characters)."""
        return await self._client._send(_specs.update_receipt(key, memo=memo))
