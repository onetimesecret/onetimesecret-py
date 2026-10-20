"""Secret operations: conceal, generate, reveal, show, status."""

from __future__ import annotations

from typing import TYPE_CHECKING

from . import _specs

if TYPE_CHECKING:
    from collections.abc import Iterable

    from .._client import AsyncClient, Client
    from .._response import Response
    from ._specs import DisplayType


class Secrets:
    """Secret operations on a :class:`onetimesecret.Client`."""

    def __init__(self, client: Client) -> None:
        self._client = client

    def conceal(
        self,
        secret: str,
        *,
        ttl: int | None = None,
        passphrase: str | None = None,
        recipient: str | None = None,
        share_domain: str | None = None,
        display_type: DisplayType | None = None,
        guest: bool = False,
    ) -> Response:
        """Conceal (share) a secret value you already have.

        Args:
            secret: The secret content.
            ttl: Time-to-live in seconds.
            passphrase: Passphrase required to reveal the secret.
            recipient: Email address to notify.
            share_domain: Custom share domain for the link.
            display_type: How the recipient's view renders the value.
            guest: Use the anonymous ``/guest/*`` endpoint.

        Returns:
            The API response. ``res["record"]["receipt"]["identifier"]`` is the
            creator-facing receipt key and ``res["record"]["secret"]["identifier"]``
            the recipient-facing secret key.
        """
        return self._client._send(
            _specs.conceal(
                secret,
                ttl=ttl,
                passphrase=passphrase,
                recipient=recipient,
                share_domain=share_domain,
                display_type=display_type,
                guest=guest,
            )
        )

    share = conceal

    def generate(
        self,
        *,
        ttl: int | None = None,
        passphrase: str | None = None,
        recipient: str | None = None,
        share_domain: str | None = None,
        guest: bool = False,
    ) -> Response:
        """Generate a random secret value server-side."""
        return self._client._send(
            _specs.generate(
                ttl=ttl,
                passphrase=passphrase,
                recipient=recipient,
                share_domain=share_domain,
                guest=guest,
            )
        )

    def reveal(self, key: str, *, passphrase: str | None = None, guest: bool = False) -> Response:
        """Reveal (consume) a secret. This is a one-time, destructive action.

        Args:
            key: The secret identifier, or the full secret URL.
            passphrase: The passphrase, if one was set.
            guest: Use the anonymous ``/guest/*`` endpoint.

        Returns:
            The API response; the value is at ``res["record"]["secret_value"]``.
        """
        return self._client._send(_specs.reveal(key, passphrase=passphrase, guest=guest))

    def show(self, key: str, *, guest: bool = False) -> Response:
        """Show a secret's metadata without revealing its value."""
        return self._client._send(_specs.show_secret(key, guest=guest))

    def status(self, key: str) -> Response:
        """Check a single secret's status."""
        return self._client._send(_specs.secret_status(key))

    def status_list(self, keys: Iterable[str]) -> Response:
        """Check the status of several secrets in one call."""
        return self._client._send(_specs.secret_status_list(keys))


class AsyncSecrets:
    """Secret operations on a :class:`onetimesecret.AsyncClient`."""

    def __init__(self, client: AsyncClient) -> None:
        self._client = client

    async def conceal(
        self,
        secret: str,
        *,
        ttl: int | None = None,
        passphrase: str | None = None,
        recipient: str | None = None,
        share_domain: str | None = None,
        display_type: DisplayType | None = None,
        guest: bool = False,
    ) -> Response:
        """Conceal (share) a secret value you already have. See :meth:`Secrets.conceal`."""
        return await self._client._send(
            _specs.conceal(
                secret,
                ttl=ttl,
                passphrase=passphrase,
                recipient=recipient,
                share_domain=share_domain,
                display_type=display_type,
                guest=guest,
            )
        )

    share = conceal

    async def generate(
        self,
        *,
        ttl: int | None = None,
        passphrase: str | None = None,
        recipient: str | None = None,
        share_domain: str | None = None,
        guest: bool = False,
    ) -> Response:
        """Generate a random secret value server-side."""
        return await self._client._send(
            _specs.generate(
                ttl=ttl,
                passphrase=passphrase,
                recipient=recipient,
                share_domain=share_domain,
                guest=guest,
            )
        )

    async def reveal(
        self, key: str, *, passphrase: str | None = None, guest: bool = False
    ) -> Response:
        """Reveal (consume) a secret. See :meth:`Secrets.reveal`."""
        return await self._client._send(_specs.reveal(key, passphrase=passphrase, guest=guest))

    async def show(self, key: str, *, guest: bool = False) -> Response:
        """Show a secret's metadata without revealing its value."""
        return await self._client._send(_specs.show_secret(key, guest=guest))

    async def status(self, key: str) -> Response:
        """Check a single secret's status."""
        return await self._client._send(_specs.secret_status(key))

    async def status_list(self, keys: Iterable[str]) -> Response:
        """Check the status of several secrets in one call."""
        return await self._client._send(_specs.secret_status_list(keys))
