"""Live, real-API integration tests.

These hit a real Onetime Secret deployment and create real, short-lived
secrets. They are opt-in: unless ``ONETIME_LIVE=1`` is set they are skipped,
so a default ``pytest`` run never touches the network.

    ONETIME_LIVE=1 uv run pytest -m live

Configuration:
    ONETIME_LIVE            set to enable these tests
    ONETIME_BASE_URL        target host (default: the Canadian production host)
    ONETIME_CUSTOMER_EXTID  optional; with ONETIME_API_TOKEN, exercises the
    ONETIME_API_TOKEN       authenticated endpoints as well

Created secrets use a short TTL and clearly marked test content. Assertions
check structure and round trips rather than exact server-supplied values.
"""

from __future__ import annotations

import os
import secrets
import time
from collections.abc import Iterator

import pytest

from onetimesecret import APIError, AsyncClient, Client

pytestmark = pytest.mark.live

DEFAULT_BASE_URL = "https://ca.onetimesecret.com"
TTL = 60

# Captured at import, before the unit-test fixture clears the variables.
_ENV = {
    name: os.environ.get(name)
    for name in ("ONETIME_BASE_URL", "ONETIME_CUSTOMER_EXTID", "ONETIME_API_TOKEN")
}


def _unique_value(label: str) -> str:
    return f"onetimesecret-py live test {label} {int(time.time())}-{secrets.token_hex(4)}"


@pytest.fixture
def live() -> Iterator[Client]:
    with Client(
        base_url=_ENV["ONETIME_BASE_URL"] or DEFAULT_BASE_URL,
        customer=_ENV["ONETIME_CUSTOMER_EXTID"],
        api_token=_ENV["ONETIME_API_TOKEN"],
    ) as client:
        yield client


# --- Public / meta endpoints ---------------------------------------------


def test_status_is_nominal(live: Client) -> None:
    res = live.status()
    assert res.status_code == 200
    assert res["status"] == "nominal"


def test_supported_locales(live: Client) -> None:
    res = live.supported_locales()
    assert res.status_code == 200
    assert res.data


def test_version_is_present(live: Client) -> None:
    if live.config.anonymous:
        pytest.skip("/version requires credentials")
    res = live.version()
    assert res.status_code == 200
    assert res.get("version")


# --- Guest secret flows --------------------------------------------------


def test_guest_conceal_reveal_round_trip(live: Client) -> None:
    guest = live.config.anonymous
    value = _unique_value("conceal-reveal")

    concealed = live.secrets.conceal(value, ttl=TTL, guest=guest)
    assert concealed.status_code == 200
    key = concealed["record"]["secret"]["identifier"]
    assert key

    revealed = live.secrets.reveal(key, guest=guest)
    assert revealed.status_code == 200
    assert revealed["record"]["secret_value"] == value


def test_guest_generate_returns_receipt_and_secret(live: Client) -> None:
    res = live.secrets.generate(ttl=TTL, guest=live.config.anonymous)
    assert res.status_code == 200
    assert res["record"]["receipt"]
    assert res["record"]["secret"]


def test_guest_receipt_show_and_burn(live: Client) -> None:
    guest = live.config.anonymous
    concealed = live.secrets.conceal(_unique_value("receipt"), ttl=TTL, guest=guest)
    receipt_key = concealed["record"]["receipt"]["identifier"]
    secret_key = concealed["record"]["secret"]["identifier"]
    assert receipt_key
    assert secret_key

    shown = live.receipts.show(receipt_key, guest=guest)
    assert shown.status_code == 200
    assert shown["record"]["identifier"] == receipt_key

    # The burn response's `record` is the receipt as dumped; `success` and
    # `details.title` are the reliable signals. The secret must be gone after.
    burned = live.receipts.burn(receipt_key, guest=guest)
    assert burned.status_code == 200
    assert burned["success"] in (True, "true")
    assert burned["details"]["title"] == "Secret burned"
    with pytest.raises(APIError) as info:
        live.secrets.reveal(secret_key, guest=guest)
    assert 400 <= info.value.status_code < 500


# --- Authenticated flows -------------------------------------------------


def test_recent_receipts(live: Client) -> None:
    if live.config.anonymous:
        pytest.skip("needs ONETIME_CUSTOMER_EXTID and ONETIME_API_TOKEN")
    assert isinstance(live.receipts.recent()["records"], list)


# --- Error mapping -------------------------------------------------------


def test_revealing_unknown_key_raises_api_error(live: Client) -> None:
    # Prefer NotFoundError when the service maps it that way, but tolerate any
    # 4xx mapped onto the APIError hierarchy.
    with pytest.raises(APIError) as info:
        live.secrets.reveal("doesnotexist000000000000000000000", guest=live.config.anonymous)
    assert 400 <= info.value.status_code < 500


# --- Async ---------------------------------------------------------------


async def test_async_status() -> None:
    async with AsyncClient(base_url=_ENV["ONETIME_BASE_URL"] or DEFAULT_BASE_URL) as client:
        assert (await client.status())["status"] == "nominal"
