from __future__ import annotations

import json
from unittest import mock

import httpx
import pytest
import respx

from onetimesecret import APIConnectionError, AsyncClient, NotFoundError, ServerError

from .conftest import BASE_URL


async def test_conceal_and_reveal(api: respx.MockRouter, async_client: AsyncClient) -> None:
    conceal = api.post("/secret/conceal").respond(
        200, json={"record": {"secret": {"identifier": "sec1"}}}
    )
    reveal = api.post("/secret/sec1/reveal").respond(
        200, json={"record": {"secret_value": "hunter2"}}
    )
    async with async_client as client:
        res = await client.secrets.conceal("hunter2", ttl=60)
        key = res["record"]["secret"]["identifier"]
        shown = await client.secrets.reveal(key)
    assert shown["record"]["secret_value"] == "hunter2"
    assert json.loads(conceal.calls.last.request.content) == {
        "secret": {"secret": "hunter2", "ttl": 60}
    }
    assert json.loads(reveal.calls.last.request.content) == {"continue": True}


async def test_receipts_and_meta(api: respx.MockRouter, async_client: AsyncClient) -> None:
    api.get("/receipt/recent").respond(200, json={"records": []})
    api.get("/receipt/r1").respond(200, json={"record": {}})
    api.post("/receipt/r1/burn").respond(200, json={"record": {"state": "burned"}})
    api.patch("/receipt/r1").respond(200, json={"record": {"memo": "m"}})
    api.get("/status").respond(200, json={"status": "nominal"})
    api.get("/version").respond(200, json={"version": "1"})
    api.get("/supported-locales").respond(200, json={"locales": ["en"]})
    api.get("/secret/s1").respond(200, json={})
    api.get("/secret/s1/status").respond(200, json={})
    api.post("/secret/status").respond(200, json={"records": []})
    api.post("/secret/generate").respond(200, json={})
    api.post("/x").respond(200, json={"ok": True})

    async with async_client as client:
        assert (await client.receipts.recent())["records"] == []
        await client.receipts.show("r1")
        assert (await client.receipts.burn("r1"))["record"]["state"] == "burned"
        assert (await client.receipts.update("r1", memo="m"))["record"]["memo"] == "m"
        assert (await client.status())["status"] == "nominal"
        assert (await client.version())["version"] == "1"
        assert (await client.supported_locales())["locales"] == ["en"]
        await client.secrets.show("s1")
        await client.secrets.status("s1")
        await client.secrets.status_list(["s1"])
        await client.secrets.generate()
        assert (await client.request("POST", "/x"))["ok"] is True


async def test_errors_are_mapped(api: respx.MockRouter, async_client: AsyncClient) -> None:
    api.get("/secret/nope/status").respond(
        404, json={"error": "gone", "error_type": "RecordNotFound"}
    )
    async with async_client as client:
        with pytest.raises(NotFoundError, match="gone"):
            await client.secrets.status("nope")


async def test_get_is_retried(api: respx.MockRouter) -> None:
    route = api.get("/status")
    route.side_effect = [
        httpx.ConnectError("x"),
        httpx.Response(503, json={"error": "busy"}),
        httpx.Response(200, json={"status": "ok"}),
    ]
    with mock.patch("onetimesecret._client.anyio.sleep") as sleep:
        async with AsyncClient(base_url=BASE_URL, max_retries=2) as client:
            assert (await client.status())["status"] == "ok"
    assert route.call_count == 3
    assert sleep.await_count == 2


async def test_post_is_not_retried(api: respx.MockRouter) -> None:
    route = api.post("/secret/conceal").respond(503, json={"error": "busy"})
    async with AsyncClient(base_url=BASE_URL, max_retries=2) as client:
        with pytest.raises(ServerError):
            await client.secrets.conceal("x")
    assert route.call_count == 1


async def test_connection_error_is_wrapped(
    api: respx.MockRouter, async_client: AsyncClient
) -> None:
    api.get("/status").mock(side_effect=httpx.ConnectError("refused"))
    async with async_client as client:
        with pytest.raises(APIConnectionError):
            await client.status()


async def test_injected_http_client() -> None:
    transport = httpx.MockTransport(lambda req: httpx.Response(200, json={"status": "ok"}))
    http = httpx.AsyncClient(transport=transport)
    async with AsyncClient(base_url=BASE_URL, http_client=http) as client:
        assert (await client.status())["status"] == "ok"
    assert http.is_closed
