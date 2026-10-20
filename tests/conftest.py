from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
import respx

from onetimesecret import AsyncClient, Client

BASE_URL = "https://ca.onetimesecret.com"
API = f"{BASE_URL}/api/v2"
CUSTOMER = "ur1abc23def"
TOKEN = "tok-123"

ENV_VARS = ("ONETIME_BASE_URL", "ONETIME_CUSTOMER_EXTID", "ONETIME_API_TOKEN")


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unit tests must not pick up a developer's real credentials."""
    for name in ENV_VARS:
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def api() -> Iterator[respx.MockRouter]:
    with respx.mock(base_url=API, assert_all_called=False) as router:
        yield router


@pytest.fixture
def client() -> Iterator[Client]:
    with Client(base_url=BASE_URL, customer=CUSTOMER, api_token=TOKEN, max_retries=0) as c:
        yield c


@pytest.fixture
def guest() -> Iterator[Client]:
    with Client(base_url=BASE_URL, max_retries=0) as c:
        yield c


@pytest.fixture
async def async_client() -> AsyncClient:
    return AsyncClient(base_url=BASE_URL, customer=CUSTOMER, api_token=TOKEN, max_retries=0)


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    if os.environ.get("ONETIME_LIVE") == "1":
        return
    skip = pytest.mark.skip(reason="set ONETIME_LIVE=1 to run against a real server")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip)
