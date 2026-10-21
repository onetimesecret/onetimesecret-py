"""Request specifications for each API operation.

The sync and async resource classes are thin dispatchers over these
functions, so the wire contract lives in exactly one place.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, Literal

from .._base_client import RequestSpec

if TYPE_CHECKING:
    from collections.abc import Iterable

DisplayType = Literal["text", "markdown"]

_SECRET_URL_PATTERN = re.compile(r"/secret/([A-Za-z0-9]+)")


def extract_secret_key(key: str) -> str:
    """Return the bare identifier from either a key or a full secret URL.

    Only ``/secret/<key>`` URLs are recognised. A receipt URL
    (``/receipt/<key>``) is not a secret URL and is returned unchanged apart
    from surrounding whitespace; the receipt key opens the receipt, not the
    secret.
    """
    match = _SECRET_URL_PATTERN.search(key)
    return match.group(1) if match else key.strip()


def _compact(**fields: Any) -> dict[str, Any]:
    return {k: v for k, v in fields.items() if v is not None}


def _guest(path: str, guest: bool) -> str:
    return f"/guest{path}" if guest else path


# --- Secrets ------------------------------------------------------------


def conceal(
    secret: str,
    *,
    ttl: int | None,
    passphrase: str | None,
    recipient: str | None,
    share_domain: str | None,
    display_type: DisplayType | None,
    guest: bool,
) -> RequestSpec:
    """Conceal (share) a secret value you already have."""
    payload = _compact(
        secret=secret,
        ttl=ttl,
        passphrase=passphrase,
        recipient=recipient,
        share_domain=share_domain,
        display_type=display_type,
    )
    return RequestSpec("POST", _guest("/secret/conceal", guest), json={"secret": payload})


def generate(
    *,
    ttl: int | None,
    passphrase: str | None,
    recipient: str | None,
    share_domain: str | None,
    guest: bool,
) -> RequestSpec:
    """Generate a random secret value server-side."""
    payload = _compact(
        ttl=ttl, passphrase=passphrase, recipient=recipient, share_domain=share_domain
    )
    return RequestSpec("POST", _guest("/secret/generate", guest), json={"secret": payload})


def reveal(key: str, *, passphrase: str | None, guest: bool) -> RequestSpec:
    """Reveal (consume) a secret. This is a one-time, destructive action."""
    identifier = extract_secret_key(key)
    # Spec drift: the v2 OpenAPI spec types `continue` as a string, but the
    # server accepts a JSON boolean as well and that is what the other SDKs
    # send. The server wins (see AGENTS.md); test_reveal_sends_continue_as_a_
    # json_boolean pins this.
    body = _compact(passphrase=passphrase, **{"continue": True})
    return RequestSpec("POST", _guest(f"/secret/{identifier}/reveal", guest), json=body)


def show_secret(key: str, *, guest: bool) -> RequestSpec:
    """Show a secret's metadata without revealing its value."""
    identifier = extract_secret_key(key)
    return RequestSpec("GET", _guest(f"/secret/{identifier}", guest))


def secret_status(key: str) -> RequestSpec:
    """Check a single secret's status."""
    return RequestSpec("GET", f"/secret/{extract_secret_key(key)}/status")


def secret_status_list(keys: Iterable[str]) -> RequestSpec:
    """Check the status of several secrets in one call.

    The server parses ``identifiers`` as a comma-separated string.
    """
    identifiers = ",".join(extract_secret_key(k) for k in keys)
    return RequestSpec("POST", "/secret/status", json={"identifiers": identifiers})


# --- Receipts -----------------------------------------------------------


def show_receipt(key: str, *, guest: bool) -> RequestSpec:
    """Show a receipt (creator-facing metadata) by its key."""
    return RequestSpec("GET", _guest(f"/receipt/{key.strip()}", guest))


def recent_receipts() -> RequestSpec:
    """List the authenticated customer's recent receipts."""
    return RequestSpec("GET", "/receipt/recent")


def burn(key: str, *, passphrase: str | None, guest: bool) -> RequestSpec:
    """Burn (destroy) an unread secret by its receipt key."""
    # Same spec drift as reveal(): the spec says string, the server takes a
    # boolean; test_burn_sends_continue_as_a_json_boolean pins this.
    body = _compact(passphrase=passphrase, **{"continue": True})
    return RequestSpec("POST", _guest(f"/receipt/{key.strip()}/burn", guest), json=body)


def update_receipt(key: str, *, memo: str) -> RequestSpec:
    """Update a receipt's memo."""
    return RequestSpec("PATCH", f"/receipt/{key.strip()}", json={"memo": memo})


# --- Meta ---------------------------------------------------------------


def status() -> RequestSpec:
    """Service status (public)."""
    return RequestSpec("GET", "/status")


def version() -> RequestSpec:
    """Service version (authenticated)."""
    return RequestSpec("GET", "/version")


def supported_locales() -> RequestSpec:
    """Locales supported by the service (public)."""
    return RequestSpec("GET", "/supported-locales")
