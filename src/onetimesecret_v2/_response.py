"""Response wrapper."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import httpx


class Response(Mapping[str, Any]):
    """A successful API response.

    Behaves as a read-only mapping over the parsed JSON body, so the API's
    own shape is available unchanged::

        res = client.secrets.conceal("hunter2")
        res["record"]["secret"]["identifier"]
        res.get("details")

    The body is not normalised or modelled: v2 returns string-typed fields
    and nests data under ``record`` / ``records`` / ``details``. See
    https://api.onetimesecret.com for the schema of each endpoint.

    Attributes:
        data: The parsed JSON body.
        status_code: HTTP status code.
        headers: Response headers.
        request_id: The ``x-request-id`` correlation id, when present.
    """

    __slots__ = ("_raw", "data")

    def __init__(self, raw: httpx.Response, data: Any) -> None:
        self._raw = raw
        self.data = data

    @property
    def status_code(self) -> int:
        """HTTP status code."""
        return self._raw.status_code

    @property
    def headers(self) -> httpx.Headers:
        """Response headers."""
        return self._raw.headers

    @property
    def request_id(self) -> str | None:
        """The ``x-request-id`` correlation id, when present."""
        value = self._raw.headers.get("x-request-id")
        return str(value) if value is not None else None

    @property
    def http_response(self) -> httpx.Response:
        """The underlying ``httpx.Response``."""
        return self._raw

    # Mapping protocol -------------------------------------------------

    def _mapping(self) -> Mapping[str, Any]:
        if isinstance(self.data, Mapping):
            return self.data
        return {}

    def __getitem__(self, key: str) -> Any:
        return self._mapping()[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._mapping())

    def __len__(self) -> int:
        return len(self._mapping())

    def __repr__(self) -> str:
        return f"Response(status_code={self.status_code}, data={self.data!r})"
