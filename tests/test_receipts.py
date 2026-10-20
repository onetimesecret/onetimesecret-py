from __future__ import annotations

import json

import respx

from onetimesecret import Client


def body(route: respx.Route) -> dict[str, object]:
    data: dict[str, object] = json.loads(route.calls.last.request.content)
    return data


def test_show(api: respx.MockRouter, client: Client) -> None:
    route = api.get("/receipt/rcpt123").respond(200, json={"record": {"state": "new"}})
    assert client.receipts.show("rcpt123")["record"]["state"] == "new"
    assert route.called


def test_show_guest_path(api: respx.MockRouter, guest: Client) -> None:
    route = api.get("/guest/receipt/rcpt123").respond(200, json={})
    guest.receipts.show("rcpt123", guest=True)
    assert route.called


def test_recent(api: respx.MockRouter, client: Client) -> None:
    api.get("/receipt/recent").respond(200, json={"records": [{"identifier": "r1"}]})
    assert client.receipts.recent()["records"] == [{"identifier": "r1"}]


def test_burn(api: respx.MockRouter, client: Client) -> None:
    route = api.post("/receipt/rcpt123/burn").respond(200, json={"record": {"state": "burned"}})
    client.receipts.burn("rcpt123", passphrase="pw")
    assert body(route) == {"passphrase": "pw", "continue": True}


def test_burn_guest_path(api: respx.MockRouter, guest: Client) -> None:
    route = api.post("/guest/receipt/rcpt123/burn").respond(200, json={})
    guest.receipts.burn("rcpt123", guest=True)
    assert body(route) == {"continue": True}


def test_update_memo(api: respx.MockRouter, client: Client) -> None:
    route = api.patch("/receipt/rcpt123").respond(200, json={"record": {"memo": "hello"}})
    client.receipts.update("rcpt123", memo="hello")
    assert body(route) == {"memo": "hello"}
