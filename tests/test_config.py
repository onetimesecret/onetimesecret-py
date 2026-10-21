from __future__ import annotations

import pytest

from onetimesecret import Client, ClientConfig, ConfigurationError

from .conftest import BASE_URL, CUSTOMER, TOKEN


def test_base_url_is_required() -> None:
    with pytest.raises(ConfigurationError, match="base_url is required"):
        ClientConfig.create()


@pytest.mark.parametrize("url", ["onetimesecret.com", "ftp://x.example", "https://", "   "])
def test_base_url_must_be_absolute_http(url: str) -> None:
    with pytest.raises(ConfigurationError):
        ClientConfig.create(base_url=url)


@pytest.mark.parametrize(
    "host", ["onetimesecret.com", "www.onetimesecret.com", "OneTimeSecret.com"]
)
def test_apex_domain_is_rejected(host: str) -> None:
    with pytest.raises(ConfigurationError, match="company website"):
        ClientConfig.create(base_url=f"https://{host}")


def test_trailing_slash_is_stripped() -> None:
    cfg = ClientConfig.create(base_url=f"{BASE_URL}/")
    assert cfg.base_url == BASE_URL
    assert cfg.api_base == f"{BASE_URL}/api/v2"


def test_self_hosted_and_custom_domains_are_fine() -> None:
    for url in ("http://localhost:3000", "https://secrets.example.com", "https://10.0.0.5:7143"):
        assert ClientConfig.create(base_url=url).base_url == url


def test_environment_fallbacks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ONETIME_BASE_URL", BASE_URL)
    monkeypatch.setenv("ONETIME_CUSTOMER_EXTID", CUSTOMER)
    monkeypatch.setenv("ONETIME_API_TOKEN", TOKEN)
    cfg = ClientConfig.create()
    assert (cfg.base_url, cfg.customer, cfg.api_token) == (BASE_URL, CUSTOMER, TOKEN)
    assert not cfg.anonymous


def test_explicit_arguments_override_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ONETIME_BASE_URL", "https://eu.onetimesecret.com")
    assert ClientConfig.create(base_url=BASE_URL).base_url == BASE_URL


def test_anonymous_when_no_credentials() -> None:
    cfg = ClientConfig.create(base_url=BASE_URL)
    assert cfg.anonymous
    assert cfg.customer is None
    assert cfg.api_token is None


def test_blank_credentials_count_as_absent() -> None:
    assert ClientConfig.create(base_url=BASE_URL, customer="  ", api_token="").anonymous


@pytest.mark.parametrize(
    "bad",
    [
        "018f3c9e-7b1a-4c2d-9f8e-2a1b3c4d5e6f",  # record UUID
        "018f3c9e7b1a4c2d9f8e2a1b3c4d5e6f",
        "on1abc23def",  # an extid, but not the customer's
        "user@example.com",  # the 0.5.x custid; also rejected by onetimesecret-ruby
        "cust_123",
        "1abc23def",
        "ur",
        "ur-1",
    ],
)
def test_customer_must_look_like_an_extid(bad: str) -> None:
    with pytest.raises(ConfigurationError, match="not a customer extid") as info:
        ClientConfig.create(base_url=BASE_URL, customer=bad, api_token=TOKEN)
    # The message must say where to find the extid.
    assert "user menu" in str(info.value)


@pytest.mark.parametrize("extid", ["ur1abc23def", "UR1ABC23DEF", "urabcdef"])
def test_accepts_customer_extids(extid: str) -> None:
    cfg = ClientConfig.create(base_url=BASE_URL, customer=extid, api_token=TOKEN)
    assert cfg.customer == extid


def test_surrounding_whitespace_is_stripped() -> None:
    cfg = ClientConfig.create(base_url=BASE_URL, customer=" ur1abc ", api_token=" tok ")
    assert (cfg.customer, cfg.api_token) == ("ur1abc", "tok")


@pytest.mark.parametrize(
    ("customer", "token", "missing"),
    [(CUSTOMER, None, "api_token"), (None, TOKEN, "customer")],
)
def test_partial_credentials_fail_loudly(
    customer: str | None, token: str | None, missing: str
) -> None:
    with pytest.raises(ConfigurationError, match=f"{missing} is missing"):
        ClientConfig.create(base_url=BASE_URL, customer=customer, api_token=token)


def test_invalid_timeout_and_retries() -> None:
    with pytest.raises(ConfigurationError, match="timeout"):
        ClientConfig.create(base_url=BASE_URL, timeout=0)
    with pytest.raises(ConfigurationError, match="max_retries"):
        ClientConfig.create(base_url=BASE_URL, max_retries=-1)


def test_defaults() -> None:
    cfg = ClientConfig.create(base_url=BASE_URL)
    assert cfg.timeout == 30.0
    assert cfg.max_retries == 2
    assert cfg.default_headers == {}


def test_token_is_not_in_repr() -> None:
    cfg = ClientConfig.create(base_url=BASE_URL, customer=CUSTOMER, api_token="s3cret")
    assert "s3cret" not in repr(cfg)


def test_config_is_immutable() -> None:
    cfg = ClientConfig.create(base_url=BASE_URL)
    with pytest.raises(AttributeError):
        cfg.base_url = "https://eu.onetimesecret.com"  # type: ignore[misc]


def test_client_validates_at_construction() -> None:
    with pytest.raises(ConfigurationError):
        Client(base_url=BASE_URL, customer="nope", api_token=TOKEN)
