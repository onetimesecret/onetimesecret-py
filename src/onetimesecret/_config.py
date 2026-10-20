"""Client configuration and validation.

Authentication uses HTTP Basic, where the username is the *customer extid*
(the ``ur…`` identifier shown at the bottom of the user menu when signed in)
and the password is an API token.

Values fall back to environment variables shared across the Onetime Secret
SDK family:

- ``ONETIME_BASE_URL`` → ``base_url``
- ``ONETIME_CUSTOMER_EXTID`` → ``customer``
- ``ONETIME_API_TOKEN`` → ``api_token``
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from ._exceptions import ConfigurationError

API_PATH_PREFIX = "/api/v2"

DEFAULT_TIMEOUT = 30.0  # seconds; applied to connect, read, write and pool
DEFAULT_MAX_RETRIES = 2

ENV_BASE_URL = "ONETIME_BASE_URL"
ENV_CUSTOMER = "ONETIME_CUSTOMER_EXTID"
ENV_API_TOKEN = "ONETIME_API_TOKEN"  # noqa: S105 - an env var name, not a secret

#: Regional API hosts. Self-hosted and custom domains are also valid.
REGIONAL_HOSTS: dict[str, str] = {
    "us": "https://us.onetimesecret.com",
    "eu": "https://eu.onetimesecret.com",
    "uk": "https://uk.onetimesecret.com",
    "ca": "https://ca.onetimesecret.com",
    "nz": "https://nz.onetimesecret.com",
}

# The apex domain and its www host serve the company website, not the API.
_APEX_HOSTS = frozenset({"onetimesecret.com", "www.onetimesecret.com"})

# A customer extid is a short, opaque, case-insensitive identifier that always
# begins with "ur", e.g. "ur1abc23def".
_CUSTOMER_EXTID_PATTERN = re.compile(r"^ur[a-z0-9]+$", re.IGNORECASE)

_CUSTOMER_EXTID_HINT = (
    'Your customer extid is the "ur…" identifier at the bottom of the user menu '
    "when you are signed in (there is a copy button next to it). Pass it as "
    f"customer= or set {ENV_CUSTOMER}."
)


@dataclass(frozen=True, slots=True)
class ClientConfig:
    """Validated, immutable configuration for a client.

    Construct via :meth:`ClientConfig.create`, which applies environment
    fallbacks and validates; the dataclass constructor performs no checks.
    """

    base_url: str
    customer: str | None = None
    api_token: str | None = field(default=None, repr=False)
    timeout: float = DEFAULT_TIMEOUT
    max_retries: int = DEFAULT_MAX_RETRIES
    user_agent: str | None = None
    default_headers: dict[str, str] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        *,
        base_url: str | None = None,
        customer: str | None = None,
        api_token: str | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
        user_agent: str | None = None,
        default_headers: dict[str, str] | None = None,
    ) -> ClientConfig:
        """Resolve environment fallbacks and validate.

        Raises:
            ConfigurationError: for a missing or non-API ``base_url``, a
                malformed customer extid, or partial credentials.
        """
        base_url = _validate_base_url(base_url or os.environ.get(ENV_BASE_URL))
        customer = _blank_to_none(
            customer if customer is not None else os.environ.get(ENV_CUSTOMER)
        )
        api_token = _blank_to_none(
            api_token if api_token is not None else os.environ.get(ENV_API_TOKEN)
        )
        _validate_credentials(customer, api_token)

        if max_retries is not None and max_retries < 0:
            raise ConfigurationError("max_retries must be >= 0")
        if timeout is not None and timeout <= 0:
            raise ConfigurationError("timeout must be > 0 seconds")

        return cls(
            base_url=base_url,
            customer=customer,
            api_token=api_token,
            timeout=DEFAULT_TIMEOUT if timeout is None else timeout,
            max_retries=DEFAULT_MAX_RETRIES if max_retries is None else max_retries,
            user_agent=user_agent,
            default_headers=dict(default_headers or {}),
        )

    @property
    def anonymous(self) -> bool:
        """True when no credentials are configured.

        Anonymous clients can still use public and ``/guest/*`` endpoints.
        """
        return self.customer is None and self.api_token is None

    @property
    def api_base(self) -> str:
        """The versioned API root, e.g. ``https://ca.onetimesecret.com/api/v2``."""
        return f"{self.base_url}{API_PATH_PREFIX}"


def _blank_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


def _validate_base_url(value: str | None) -> str:
    examples = ", ".join(list(REGIONAL_HOSTS.values())[:3])
    if not value or not value.strip():
        raise ConfigurationError(
            "base_url is required. Use your region's API host "
            f"(e.g. {examples}), your self-hosted domain, or your custom domain. "
            f"Pass base_url= or set {ENV_BASE_URL}."
        )
    value = value.strip().rstrip("/")
    parts = urlsplit(value)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise ConfigurationError(f"base_url must be an absolute http(s) URL, got {value!r}")
    if parts.hostname.lower() in _APEX_HOSTS:
        raise ConfigurationError(
            f"{parts.hostname} is the Onetime Secret company website, not an API host. "
            f"Use a regional host (e.g. {REGIONAL_HOSTS['us']}), your self-hosted "
            "domain, or your custom domain."
        )
    return value


def _validate_credentials(customer: str | None, api_token: str | None) -> None:
    if customer is not None and not _CUSTOMER_EXTID_PATTERN.match(customer):
        raise ConfigurationError(
            f"customer {customer!r} is not a customer extid: extids begin with "
            f'"ur" (e.g. "ur1abc23def"). {_CUSTOMER_EXTID_HINT}'
        )
    # Partial credentials are almost always a mistake; fail loudly.
    if (customer is None) != (api_token is None):
        missing = "customer" if customer is None else "api_token"
        raise ConfigurationError(f"Incomplete credentials: {missing} is missing")
