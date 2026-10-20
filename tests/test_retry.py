from __future__ import annotations

from collections.abc import Iterator
from unittest import mock

import httpx
import pytest
import respx

from onetimesecret import APIConnectionError, Client, ServerError
from onetimesecret._base_client import BaseClient

from .conftest import BASE_URL


@pytest.fixture(autouse=True)
def sleep_mock() -> Iterator[mock.MagicMock]:
    with mock.patch("onetimesecret._client.time.sleep") as sleep:
        yield sleep


@pytest.fixture
def retrying() -> Iterator[Client]:
    with Client(base_url=BASE_URL, max_retries=2) as c:
        yield c


def test_get_is_retried_on_retryable_status(api: respx.MockRouter, retrying: Client) -> None:
    route = api.get("/status")
    route.side_effect = [
        httpx.Response(503, json={"error": "busy"}),
        httpx.Response(502, text="bad gateway"),
        httpx.Response(200, json={"status": "nominal"}),
    ]
    assert retrying.status()["status"] == "nominal"
    assert route.call_count == 3


def test_get_gives_up_after_max_retries(api: respx.MockRouter, retrying: Client) -> None:
    route = api.get("/status").respond(503, json={"error": "busy"})
    with pytest.raises(ServerError):
        retrying.status()
    assert route.call_count == 3  # 1 + max_retries


def test_raise_on_error_false_still_retries(api: respx.MockRouter, retrying: Client) -> None:
    route = api.get("/status").respond(503, json={"error": "busy"})
    res = retrying.request("GET", "/status", raise_on_error=False)
    assert res.status_code == 503
    assert route.call_count == 3


def test_get_is_retried_on_connection_errors(api: respx.MockRouter, retrying: Client) -> None:
    route = api.get("/status")
    route.side_effect = [httpx.ConnectError("x"), httpx.Response(200, json={"status": "ok"})]
    assert retrying.status()["status"] == "ok"
    assert route.call_count == 2


def test_connection_errors_surface_after_retries(api: respx.MockRouter, retrying: Client) -> None:
    route = api.get("/status").mock(side_effect=httpx.ConnectError("x"))
    with pytest.raises(APIConnectionError):
        retrying.status()
    assert route.call_count == 3


def test_post_is_never_retried(api: respx.MockRouter, retrying: Client) -> None:
    route = api.post("/secret/conceal").respond(503, json={"error": "busy"})
    with pytest.raises(ServerError):
        retrying.secrets.conceal("x")
    assert route.call_count == 1

    route = api.post("/secret/sec1/reveal").mock(side_effect=httpx.ReadTimeout("slow"))
    with pytest.raises(APIConnectionError):
        retrying.secrets.reveal("sec1")
    assert route.call_count == 1


def test_non_retryable_status_is_not_retried(api: respx.MockRouter, retrying: Client) -> None:
    route = api.get("/status").respond(500, json={"error": "x"})
    # 500 is retryable; 501 is not
    route.respond(501, json={"error": "x"})
    with pytest.raises(ServerError):
        retrying.status()
    assert route.call_count == 1


def test_max_retries_zero_disables_retries(api: respx.MockRouter) -> None:
    route = api.get("/status").respond(503, json={"error": "busy"})
    with Client(base_url=BASE_URL, max_retries=0) as c, pytest.raises(ServerError):
        c.status()
    assert route.call_count == 1


def test_retry_after_header_is_honoured(
    api: respx.MockRouter, retrying: Client, sleep_mock: mock.MagicMock
) -> None:
    route = api.get("/status")
    route.side_effect = [
        httpx.Response(429, json={"error": "slow"}, headers={"retry-after": "2"}),
        httpx.Response(200, json={}),
    ]
    retrying.status()
    sleep_mock.assert_called_once_with(2.0)


def test_backoff_grows_and_is_capped() -> None:
    client = BaseClient.__new__(BaseClient)
    with mock.patch("onetimesecret._base_client.random.random", return_value=1.0):
        delays = [client._backoff(n) for n in range(1, 7)]
    assert delays == [0.5, 1.0, 2.0, 4.0, 8.0, 8.0]


def test_backoff_has_jitter() -> None:
    client = BaseClient.__new__(BaseClient)
    with mock.patch("onetimesecret._base_client.random.random", return_value=0.0):
        assert client._backoff(1) == 0.25


def test_unparseable_retry_after_falls_back_to_backoff() -> None:
    client = BaseClient.__new__(BaseClient)
    raw = httpx.Response(429, headers={"retry-after": "Wed, 21 Oct 2026 07:28:00 GMT"})
    assert 0.25 <= client._backoff(1, raw) <= 0.5
