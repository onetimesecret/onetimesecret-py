"""Secret operations: conceal, generate, reveal, show, status."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from .._exceptions import ClaimError
from . import _specs

if TYPE_CHECKING:
    from collections.abc import Iterable

    from .._client import AsyncClient, Client
    from .._response import Response
    from ._specs import DisplayType

log = logging.getLogger("onetimesecret")


def _receipt_key(data: Any) -> str | None:
    try:
        key = data["record"]["receipt"]["identifier"]
    except (KeyError, TypeError, IndexError):
        return None
    return key if isinstance(key, str) and key else None


def _attach_claim(res: Response, receipt: Response | None, error: ClaimError | None) -> None:
    """Copy the disclosed value (or the failure) into ``res["details"]``.

    The generate response never carries the value; the server discloses it
    once, on the first read of the receipt, as ``details.secret_value``. We
    put it in the same slot of the generate response so callers read the one
    envelope.

    Nothing here logs or stores a response body: the receipt body may hold
    the value, and a malformed one would otherwise leak it through the error.
    """
    data = res.data
    if not isinstance(data, dict):
        log.warning("Cannot attach the generated secret value: response body is not an object")
        return
    details = data.get("details")
    if not isinstance(details, dict):
        details = data["details"] = {}
    if error is None and receipt is not None and not isinstance(receipt.data, Mapping):
        # A 200 whose body did not parse as a JSON object. Do not inspect it.
        error = ClaimError("receipt body is not a JSON object", status_code=receipt.status_code)
    if error is not None:
        details["claim_error"] = error
        log.warning("Could not claim the generated secret value: %s", error)
        return
    value = receipt.get("details", {}).get("secret_value") if receipt is not None else None
    if value is None:
        log.warning("The server did not disclose the generated secret value")
        return
    details["secret_value"] = value


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
        claim_value: bool = True,
    ) -> Response:
        """Generate a random secret value server-side.

        The generate response itself never contains the value. The server
        discloses it exactly once, on the first read of the receipt, and only
        for a short window after creation (60 seconds by default). With
        ``claim_value=True`` this method reads the receipt straight away and
        copies the value into ``res["details"]["secret_value"]``.

        If that read fails the secret still exists and its link is valid, so
        nothing is raised: the generate response is returned without the
        value, a :class:`~onetimesecret.ClaimError` (status and error type
        only, never the body) is attached at ``res["details"]["claim_error"]``
        and a warning is logged. If the server simply declined to disclose
        the value, ``secret_value`` is absent and no error is attached.

        Args:
            ttl: Time-to-live in seconds.
            passphrase: Passphrase required to reveal the secret.
            recipient: Email address to notify.
            share_domain: Custom share domain for the link.
            guest: Use the anonymous ``/guest/*`` endpoints.
            claim_value: Read the receipt once to learn the generated value.
                Pass ``False`` to skip the extra request; the value can then
                only be learned by the first receipt read within the window,
                or by revealing the secret.

        Returns:
            The API response, shaped as for :meth:`conceal`, plus
            ``res["details"]["secret_value"]`` when the value was claimed.
        """
        res = self._client._send(
            _specs.generate(
                ttl=ttl,
                passphrase=passphrase,
                recipient=recipient,
                share_domain=share_domain,
                guest=guest,
            )
        )
        if not claim_value:
            return res
        key = _receipt_key(res.data)
        if key is None:
            _attach_claim(res, None, ClaimError("generate response has no receipt identifier"))
            return res
        try:
            receipt = self._client._send(_specs.show_receipt(key, guest=guest))
        except Exception as exc:  # the secret exists; never raise past this point
            _attach_claim(res, None, ClaimError.from_exception(exc))
        else:
            _attach_claim(res, receipt, None)
        return res

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
        claim_value: bool = True,
    ) -> Response:
        """Generate a random secret value server-side. See :meth:`Secrets.generate`."""
        res = await self._client._send(
            _specs.generate(
                ttl=ttl,
                passphrase=passphrase,
                recipient=recipient,
                share_domain=share_domain,
                guest=guest,
            )
        )
        if not claim_value:
            return res
        key = _receipt_key(res.data)
        if key is None:
            _attach_claim(res, None, ClaimError("generate response has no receipt identifier"))
            return res
        try:
            receipt = await self._client._send(_specs.show_receipt(key, guest=guest))
        except Exception as exc:  # the secret exists; never raise past this point
            _attach_claim(res, None, ClaimError.from_exception(exc))
        else:
            _attach_claim(res, receipt, None)
        return res

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
