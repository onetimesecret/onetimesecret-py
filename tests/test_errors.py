from __future__ import annotations

import httpx
import pytest
import respx

from onetimesecret import (
    AccountRequiredError,
    APIConnectionError,
    APIError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    Client,
    ConflictError,
    EntitlementError,
    ForbiddenError,
    NotFoundError,
    OnetimeSecretError,
    RateLimitError,
    ServerError,
)

from .conftest import BASE_URL


def test_adr013_fields_are_exposed(api: respx.MockRouter, client: Client) -> None:
    api.get("/secret/nope/status").respond(
        404,
        json={
            "error": "Secret not found",
            "error_type": "RecordNotFound",
            "error_key": "web.COMMON.error_secret_not_found",
            "request_id": "req-42",
        },
    )
    with pytest.raises(NotFoundError) as info:
        client.secrets.status("nope")
    err = info.value
    assert err.message == "Secret not found"
    assert err.error_type == "RecordNotFound"
    assert err.error_key == "web.COMMON.error_secret_not_found"
    assert err.status_code == 404
    assert err.request_id == "req-42"
    assert err.body["error_type"] == "RecordNotFound"
    assert err.response.status_code == 404
    assert str(err) == "Secret not found (status=404 type=RecordNotFound request_id=req-42)"
    assert isinstance(err, APIError)
    assert isinstance(err, OnetimeSecretError)


def test_request_id_falls_back_to_header(api: respx.MockRouter, client: Client) -> None:
    api.get("/status").respond(500, json={"error": "boom"}, headers={"x-request-id": "hdr-1"})
    with pytest.raises(ServerError) as info:
        client.status()
    assert info.value.request_id == "hdr-1"


@pytest.mark.parametrize(
    ("error_type", "status", "cls"),
    [
        ("FormError", 400, BadRequestError),
        ("RecordNotFound", 404, NotFoundError),
        ("NotFound", 404, NotFoundError),
        ("Forbidden", 403, ForbiddenError),
        ("GuestRoutesDisabled", 403, ForbiddenError),
        ("EntitlementRequired", 403, EntitlementError),
        ("LimitExceeded", 429, RateLimitError),
        ("ServerError", 500, ServerError),
        # error_type wins over the status code
        ("RecordNotFound", 400, NotFoundError),
    ],
)
def test_error_type_mapping(
    api: respx.MockRouter, client: Client, error_type: str, status: int, cls: type[APIError]
) -> None:
    api.get("/status").respond(status, json={"error": "x", "error_type": error_type})
    with pytest.raises(cls):
        client.status()


@pytest.mark.parametrize(
    ("status", "cls"),
    [
        (400, BadRequestError),
        (401, AuthenticationError),
        (403, ForbiddenError),
        (404, NotFoundError),
        (409, ConflictError),
        (422, BadRequestError),
        (429, RateLimitError),
        (500, ServerError),
        (502, ServerError),
        (503, ServerError),
        (418, APIError),
    ],
)
def test_status_code_fallback(
    api: respx.MockRouter, client: Client, status: int, cls: type[APIError]
) -> None:
    api.get("/status").respond(status, json={"error": "x"})
    with pytest.raises(cls) as info:
        client.status()
    assert type(info.value) is cls


def test_unknown_error_type_falls_back_to_status(api: respx.MockRouter, client: Client) -> None:
    api.get("/status").respond(404, json={"error": "x", "error_type": "SomethingNew"})
    with pytest.raises(NotFoundError) as info:
        client.status()
    assert info.value.error_type == "SomethingNew"


def test_entitlement_error_subclasses_forbidden(api: respx.MockRouter, client: Client) -> None:
    api.post("/secret/conceal").respond(
        403,
        json={
            "error": "Upgrade required",
            "error_type": "EntitlementRequired",
            "entitlement": "custom_domains",
        },
    )
    with pytest.raises(ForbiddenError) as info:
        client.secrets.conceal("x", share_domain="d.example.com")
    assert isinstance(info.value, EntitlementError)
    assert info.value.entitlement == "custom_domains"


def test_guest_routes_disabled_keeps_code(api: respx.MockRouter, guest: Client) -> None:
    api.post("/guest/secret/conceal").respond(
        403,
        json={
            "error": "Guest access is disabled",
            "error_type": "GuestRoutesDisabled",
            "code": "GUEST_CONCEAL_DISABLED",
        },
    )
    with pytest.raises(ForbiddenError) as info:
        guest.secrets.conceal("x", guest=True)
    assert info.value.code == "GUEST_CONCEAL_DISABLED"


@pytest.mark.parametrize(
    "payload",
    [
        {"error": "Account required", "error_type": "FormError", "field": "requires_account"},
        {"error": "Account required", "error_type": "RequiresAccount"},
        {"error": "Account required", "error_key": "web.COMMON.requires_account"},
        {"error": "Account required", "code": "GUEST_CONCEAL_REQUIRES_ACCOUNT"},
        {"error": "Account required", "field": "account-required"},
    ],
)
def test_account_required_detected_in_any_slot(
    api: respx.MockRouter, guest: Client, payload: dict[str, str]
) -> None:
    api.post("/secret/conceal").respond(400, json=payload)
    with pytest.raises(AuthenticationError) as info:
        guest.secrets.conceal("x")
    err = info.value
    assert isinstance(err, AccountRequiredError)
    assert err.status_code == 400
    assert err.field == payload.get("field")


def test_account_required_message_when_server_sends_none(
    api: respx.MockRouter, guest: Client
) -> None:
    api.post("/secret/conceal").respond(400, json={"field": "requires_account"})
    with pytest.raises(AccountRequiredError, match="requires an authenticated account"):
        guest.secrets.conceal("x")


def test_requires_account_substring_is_not_enough(api: respx.MockRouter, client: Client) -> None:
    # "myrequires_accountx" must not match; only a bounded token does.
    api.get("/status").respond(400, json={"error": "x", "field": "myrequires_accountx"})
    with pytest.raises(BadRequestError) as info:
        client.status()
    assert not isinstance(info.value, AccountRequiredError)


def test_legacy_message_field_is_used(api: respx.MockRouter, client: Client) -> None:
    api.get("/status").respond(400, json={"message": "legacy shape"})
    with pytest.raises(BadRequestError, match="legacy shape"):
        client.status()


@pytest.mark.parametrize(
    ("status", "message"),
    [
        (400, "Bad request"),
        (401, "Authentication failed"),
        (403, "Forbidden"),
        (404, "Not found"),
        (429, "Rate limit exceeded"),
        (503, "Server error (503)"),
        (418, "Request failed (418)"),
    ],
)
def test_default_messages(
    api: respx.MockRouter, client: Client, status: int, message: str
) -> None:
    api.get("/status").respond(status, json={})
    with pytest.raises(APIError) as info:
        client.status()
    assert info.value.message == message


def test_non_json_error_body_is_kept_as_text(api: respx.MockRouter, client: Client) -> None:
    api.get("/status").respond(502, text="<html>Bad Gateway</html>")
    with pytest.raises(ServerError) as info:
        client.status()
    assert info.value.body == "<html>Bad Gateway</html>"
    assert info.value.message == "Server error (502)"


def test_retry_after_from_body_and_header(api: respx.MockRouter, client: Client) -> None:
    api.get("/status").respond(429, json={"error": "slow down", "retry_after": 7})
    with pytest.raises(RateLimitError) as info:
        client.status()
    assert info.value.retry_after == 7.0

    api.get("/status").respond(429, json={"error": "slow down"}, headers={"retry-after": "3"})
    with pytest.raises(RateLimitError) as info:
        client.status()
    assert info.value.retry_after == 3.0


def test_connection_error_is_wrapped(api: respx.MockRouter, client: Client) -> None:
    api.get("/status").mock(side_effect=httpx.ConnectError("refused"))
    with pytest.raises(APIConnectionError) as info:
        client.status()
    assert isinstance(info.value.__cause__, httpx.ConnectError)


def test_timeout_is_wrapped(api: respx.MockRouter, client: Client) -> None:
    api.post("/secret/conceal").mock(side_effect=httpx.ReadTimeout("slow"))
    with pytest.raises(APITimeoutError) as info:
        client.secrets.conceal("x")
    assert isinstance(info.value, APIConnectionError)


def test_connection_error_mentions_cause() -> None:
    transport = httpx.MockTransport(lambda req: (_ for _ in ()).throw(httpx.ConnectError("nope")))
    with (
        Client(base_url=BASE_URL, http_client=httpx.Client(transport=transport)) as c,
        pytest.raises(APIConnectionError, match="nope"),
    ):
        c.status()
