"""Official Python client for the Onetime Secret API.

Example:
    >>> from onetimesecret import Client
    >>> client = Client(
    ...     base_url="https://ca.onetimesecret.com",
    ...     customer="ur1abc23def",
    ...     api_token="...",
    ... )
    >>> res = client.secrets.conceal("hunter2", ttl=3600)
    >>> res["record"]["secret"]["identifier"]
"""

from ._client import AsyncClient, Client
from ._config import REGIONAL_HOSTS, ClientConfig
from ._exceptions import (
    AccountRequiredError,
    APIConnectionError,
    APIError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    ConfigurationError,
    ConflictError,
    EntitlementError,
    ForbiddenError,
    NotFoundError,
    OnetimeSecretError,
    RateLimitError,
    ServerError,
)
from ._response import Response
from ._version import __version__

__all__ = [
    "REGIONAL_HOSTS",
    "APIConnectionError",
    "APIError",
    "APITimeoutError",
    "AccountRequiredError",
    "AsyncClient",
    "AuthenticationError",
    "BadRequestError",
    "Client",
    "ClientConfig",
    "ConfigurationError",
    "ConflictError",
    "EntitlementError",
    "ForbiddenError",
    "NotFoundError",
    "OnetimeSecretError",
    "RateLimitError",
    "Response",
    "ServerError",
    "__version__",
]
