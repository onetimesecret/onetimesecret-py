from __future__ import annotations

import json

import pytest
import respx

from onetimesecret import Client
from onetimesecret.resources import extract_secret_key

CONCEAL_RESPONSE = {
    "success": True,
    "record": {
        "receipt": {"identifier": "rcpt123", "state": "new"},
        "secret": {"identifier": "sec456", "state": "new"},
        "share_domain": "",
    },
    "details": {"kind": "conceal"},
}


def body(route: respx.Route) -> dict[str, object]:
    data: dict[str, object] = json.loads(route.calls.last.request.content)
    return data


def test_conceal_nests_params_under_secret(api: respx.MockRouter, client: Client) -> None:
    route = api.post("/secret/conceal").respond(200, json=CONCEAL_RESPONSE)
    res = client.secrets.conceal(
        "hunter2",
        ttl=3600,
        passphrase="pw",
        recipient="a@example.com",
        share_domain="s.example.com",
        display_type="markdown",
    )
    assert res["record"]["secret"]["identifier"] == "sec456"
    assert body(route) == {
        "secret": {
            "secret": "hunter2",
            "ttl": 3600,
            "passphrase": "pw",
            "recipient": "a@example.com",
            "share_domain": "s.example.com",
            "display_type": "markdown",
        }
    }


def test_conceal_omits_unset_fields(api: respx.MockRouter, client: Client) -> None:
    route = api.post("/secret/conceal").respond(200, json=CONCEAL_RESPONSE)
    client.secrets.conceal("hunter2")
    assert body(route) == {"secret": {"secret": "hunter2"}}


def test_share_is_an_alias_for_conceal() -> None:
    from onetimesecret.resources import AsyncSecrets, Secrets

    assert Secrets.share is Secrets.conceal
    assert AsyncSecrets.share is AsyncSecrets.conceal


def test_conceal_guest_uses_guest_path(api: respx.MockRouter, guest: Client) -> None:
    route = api.post("/guest/secret/conceal").respond(200, json=CONCEAL_RESPONSE)
    guest.secrets.conceal("hi", guest=True)
    assert route.called


def test_generate(api: respx.MockRouter, client: Client) -> None:
    route = api.post("/secret/generate").respond(200, json=CONCEAL_RESPONSE)
    client.secrets.generate(ttl=60, passphrase="pw")
    assert body(route) == {"secret": {"ttl": 60, "passphrase": "pw"}}


def test_generate_with_no_options_sends_empty_secret_object(
    api: respx.MockRouter, client: Client
) -> None:
    route = api.post("/secret/generate").respond(200, json=CONCEAL_RESPONSE)
    client.secrets.generate()
    assert body(route) == {"secret": {}}


def test_generate_guest_path(api: respx.MockRouter, guest: Client) -> None:
    route = api.post("/guest/secret/generate").respond(200, json=CONCEAL_RESPONSE)
    guest.secrets.generate(guest=True)
    assert route.called


def test_reveal_sends_continue_and_passphrase(api: respx.MockRouter, client: Client) -> None:
    route = api.post("/secret/sec456/reveal").respond(
        200, json={"record": {"secret_value": "hunter2"}}
    )
    res = client.secrets.reveal("sec456", passphrase="pw")
    assert res["record"]["secret_value"] == "hunter2"
    assert body(route) == {"passphrase": "pw", "continue": True}


def test_reveal_sends_continue_as_a_json_boolean(api: respx.MockRouter, client: Client) -> None:
    # The v2 OpenAPI spec types `continue` as a string; the server accepts a
    # boolean too and that is what we send. `== True` would also pass for 1,
    # so check the wire bytes and the decoded type explicitly.
    route = api.post("/secret/sec456/reveal").respond(200, json={})
    client.secrets.reveal("sec456")
    raw = route.calls.last.request.content
    assert b'"continue":true' in raw or b'"continue": true' in raw
    assert body(route)["continue"] is True


def test_reveal_without_passphrase(api: respx.MockRouter, client: Client) -> None:
    route = api.post("/secret/sec456/reveal").respond(200, json={"record": {}})
    client.secrets.reveal("sec456")
    assert body(route) == {"continue": True}


@pytest.mark.parametrize(
    "key",
    [
        "sec456",
        "  sec456 ",
        "https://ca.onetimesecret.com/secret/sec456",
        "https://custom.example.com/secret/sec456#fragment",
        "https://ca.onetimesecret.com/en/secret/sec456",
    ],
)
def test_reveal_accepts_full_urls(api: respx.MockRouter, client: Client, key: str) -> None:
    route = api.post("/secret/sec456/reveal").respond(200, json={})
    client.secrets.reveal(key)
    assert route.called


def test_extract_secret_key() -> None:
    assert extract_secret_key("abc") == "abc"
    assert extract_secret_key("  abc ") == "abc"
    assert extract_secret_key("https://x.example/secret/abc123") == "abc123"


def test_extract_secret_key_leaves_receipt_urls_unchanged() -> None:
    # A receipt URL is not a secret URL. The receipt key would open the
    # receipt, not the secret, so it is passed through rather than guessed.
    url = "https://x.example/receipt/abc123"
    assert extract_secret_key(url) == url
    assert extract_secret_key(f"  {url} ") == url


def test_reveal_guest_path(api: respx.MockRouter, guest: Client) -> None:
    route = api.post("/guest/secret/sec456/reveal").respond(200, json={})
    guest.secrets.reveal("sec456", guest=True)
    assert route.called


def test_show(api: respx.MockRouter, client: Client) -> None:
    route = api.get("/secret/sec456").respond(200, json={"record": {"state": "new"}})
    assert client.secrets.show("https://ca.onetimesecret.com/secret/sec456")["record"] == {
        "state": "new"
    }
    assert route.called


def test_show_guest_path(api: respx.MockRouter, guest: Client) -> None:
    route = api.get("/guest/secret/sec456").respond(200, json={})
    guest.secrets.show("sec456", guest=True)
    assert route.called


def test_status(api: respx.MockRouter, client: Client) -> None:
    route = api.get("/secret/sec456/status").respond(200, json={"record": {"state": "new"}})
    client.secrets.status("sec456")
    assert route.called


def test_status_list_sends_comma_separated_identifiers(
    api: respx.MockRouter, client: Client
) -> None:
    # The server parses `identifiers` as a comma-separated string.
    route = api.post("/secret/status").respond(200, json={"records": []})
    client.secrets.status_list(["a1", "https://ca.onetimesecret.com/secret/b2", "c3"])
    assert body(route) == {"identifiers": "a1,b2,c3"}


def test_status_list_accepts_any_iterable(api: respx.MockRouter, client: Client) -> None:
    route = api.post("/secret/status").respond(200, json={"records": []})
    client.secrets.status_list(k for k in ("a1", "b2"))
    assert body(route) == {"identifiers": "a1,b2"}
