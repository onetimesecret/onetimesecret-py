"""Tests against a real server. Skipped unless ``ONETIME_LIVE=1``.

Uses ``ONETIME_BASE_URL`` and, when set, ``ONETIME_CUSTOMER_EXTID`` /
``ONETIME_API_TOKEN``. Without credentials only the guest and public paths run.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

from onetimesecret import AsyncClient, Client, NotFoundError

pytestmark = pytest.mark.live


@pytest.fixture
def live() -> Iterator[Client]:
    base_url = os.environ.get("ONETIME_BASE_URL")
    if not base_url:
        pytest.skip("ONETIME_BASE_URL is not set")
    with Client(
        base_url=base_url,
        customer=os.environ.get("ONETIME_CUSTOMER_EXTID"),
        api_token=os.environ.get("ONETIME_API_TOKEN"),
    ) as c:
        yield c


@pytest.fixture(autouse=True)
def _restore_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Undo the unit-test fixture that clears the ONETIME_* variables."""
    for name in ("ONETIME_BASE_URL", "ONETIME_CUSTOMER_EXTID", "ONETIME_API_TOKEN"):
        value = _ORIGINAL_ENV.get(name)
        if value is not None:
            monkeypatch.setenv(name, value)


_ORIGINAL_ENV = {
    name: os.environ.get(name)
    for name in ("ONETIME_BASE_URL", "ONETIME_CUSTOMER_EXTID", "ONETIME_API_TOKEN")
}


def test_status(live: Client) -> None:
    res = live.status()
    assert res.status_code == 200
    assert "status" in res


def test_supported_locales(live: Client) -> None:
    assert "en" in live.supported_locales()["locales"]


def test_guest_conceal_show_and_reveal(live: Client) -> None:
    guest = live.config.anonymous
    res = live.secrets.conceal("live test value", ttl=120, guest=guest)
    secret_key = res["record"]["secret"]["identifier"]
    receipt_key = res["record"]["receipt"]["identifier"]

    shown = live.secrets.show(secret_key, guest=guest)
    assert shown["record"]["identifier"] == secret_key

    receipt = live.receipts.show(receipt_key, guest=guest)
    assert receipt["record"]["identifier"] == receipt_key

    revealed = live.secrets.reveal(secret_key, guest=guest)
    assert revealed["record"]["secret_value"] == "live test value"


def test_guest_burn(live: Client) -> None:
    guest = live.config.anonymous
    res = live.secrets.generate(ttl=120, guest=guest)
    receipt_key = res["record"]["receipt"]["identifier"]
    burned = live.receipts.burn(receipt_key, guest=guest)
    assert burned["record"]["state"] == "burned"


def test_missing_secret_raises_not_found(live: Client) -> None:
    with pytest.raises(NotFoundError):
        live.secrets.reveal("doesnotexist000", guest=live.config.anonymous)


def test_recent_requires_credentials(live: Client) -> None:
    if live.config.anonymous:
        pytest.skip("needs ONETIME_CUSTOMER_EXTID and ONETIME_API_TOKEN")
    assert isinstance(live.receipts.recent()["records"], list)


async def test_async_status() -> None:
    base_url = os.environ.get("ONETIME_BASE_URL")
    if not base_url:
        pytest.skip("ONETIME_BASE_URL is not set")
    async with AsyncClient(base_url=base_url) as client:
        assert (await client.status()).status_code == 200
