from __future__ import annotations

import base64
import json

import httpx
import pytest
import respx

import onetimesecret
from onetimesecret import Client, Response

from .conftest import API, BASE_URL, CUSTOMER, TOKEN


def test_sends_basic_auth_with_extid_and_token(api: respx.MockRouter, client: Client) -> None:
    route = api.get("/status").respond(200, json={"status": "nominal"})
    client.status()
    header = route.calls.last.request.headers["authorization"]
    expected = base64.b64encode(f"{CUSTOMER}:{TOKEN}".encode()).decode()
    assert header == f"Basic {expected}"


def test_anonymous_client_sends_no_auth(api: respx.MockRouter, guest: Client) -> None:
    route = api.get("/status").respond(200, json={"status": "nominal"})
    guest.status()
    assert "authorization" not in route.calls.last.request.headers


def test_default_headers_and_user_agent(api: respx.MockRouter, client: Client) -> None:
    route = api.get("/status").respond(200, json={})
    client.status()
    headers = route.calls.last.request.headers
    assert headers["accept"] == "application/json"
    assert headers["user-agent"].startswith(f"onetime-secret-python/{onetimesecret.__version__}")


def test_custom_user_agent_and_extra_headers(api: respx.MockRouter) -> None:
    route = api.get("/status").respond(200, json={})
    with Client(
        base_url=BASE_URL, user_agent="my-app/1.0", default_headers={"X-Team": "ops"}
    ) as c:
        c.status()
    headers = route.calls.last.request.headers
    assert headers["user-agent"] == "my-app/1.0"
    assert headers["x-team"] == "ops"


def test_paths_are_prefixed_with_api_v2(api: respx.MockRouter, client: Client) -> None:
    route = api.get("/supported-locales").respond(200, json={"locales": ["en"]})
    client.supported_locales()
    assert str(route.calls.last.request.url) == f"{API}/supported-locales"


def test_version_endpoint(api: respx.MockRouter, client: Client) -> None:
    api.get("/version").respond(200, json={"version": "0.99.0"})
    assert client.version()["version"] == "0.99.0"


def test_response_is_a_mapping_with_metadata(api: respx.MockRouter, client: Client) -> None:
    api.get("/status").respond(
        200, json={"status": "nominal", "locale": "en"}, headers={"x-request-id": "req-1"}
    )
    res = client.status()
    assert isinstance(res, Response)
    assert res["status"] == "nominal"
    assert res.get("missing") is None
    assert dict(res) == {"status": "nominal", "locale": "en"}
    assert len(res) == 2
    assert res.status_code == 200
    assert res.request_id == "req-1"
    assert res.headers["x-request-id"] == "req-1"
    assert res.http_response.status_code == 200
    assert "nominal" in repr(res)


def test_non_object_body_is_kept_on_data(api: respx.MockRouter, client: Client) -> None:
    api.get("/status").respond(200, json=["a", "b"])
    res = client.status()
    assert res.data == ["a", "b"]
    assert len(res) == 0


def test_empty_body(api: respx.MockRouter, client: Client) -> None:
    api.get("/status").respond(204)
    assert client.status().data is None


def test_text_success_body_is_kept_as_text(api: respx.MockRouter, client: Client) -> None:
    # A proxy may answer 200 with a non-JSON body; the text is kept on `.data`.
    api.get("/status").respond(200, text="<html>ok</html>", headers={"x-request-id": "r"})
    res = client.status()
    assert res.status_code == 200
    assert res.data == "<html>ok</html>"
    assert res.request_id == "r"
    assert len(res) == 0
    assert dict(res) == {}


def test_generic_request_helper(api: respx.MockRouter, client: Client) -> None:
    route = api.post("/some/new/endpoint").respond(200, json={"ok": True})
    res = client.request("post", "/some/new/endpoint", json={"a": 1}, params={"q": "x"})
    assert res["ok"] is True
    req = route.calls.last.request
    assert req.url.params["q"] == "x"
    assert json.loads(req.content) == {"a": 1}


def test_raise_on_error_false_returns_the_error_response(
    api: respx.MockRouter, client: Client
) -> None:
    api.get("/secret/nope/status").respond(
        404, json={"error": "gone", "error_type": "RecordNotFound"}
    )
    res = client.request("GET", "/secret/nope/status", raise_on_error=False)
    assert res.status_code == 404
    assert res["error_type"] == "RecordNotFound"


def test_injected_http_client_is_used_and_closed() -> None:
    transport = httpx.MockTransport(lambda req: httpx.Response(200, json={"status": "ok"}))
    http = httpx.Client(transport=transport)
    with Client(base_url=BASE_URL, http_client=http) as c:
        assert c.status()["status"] == "ok"
    assert http.is_closed


def test_context_manager_closes(api: respx.MockRouter) -> None:
    api.get("/status").respond(200, json={})
    c = Client(base_url=BASE_URL)
    with c:
        c.status()
    with pytest.raises(RuntimeError):  # httpx: client has been closed
        c.status()


def test_timeout_is_applied() -> None:
    c = Client(base_url=BASE_URL, timeout=5)
    assert c._http.timeout == httpx.Timeout(5)
    c.close()


def test_injected_http_client_keeps_its_own_timeout() -> None:
    # The SDK `timeout` configures the client it creates; a preconfigured
    # `http_client` is used as given, so its timeout wins.
    http = httpx.Client(timeout=1)
    with Client(base_url=BASE_URL, timeout=5, http_client=http) as c:
        assert c.config.timeout == 5
        assert c._http.timeout == httpx.Timeout(1)
