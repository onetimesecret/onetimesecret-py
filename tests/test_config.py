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


@pytest.mark.parametrize("bad", ["acct-123", "delano@example.com", "ur", "ur-1", "1234"])
def test_customer_must_look_like_an_extid(bad: str) -> None:
    with pytest.raises(ConfigurationError, match="not a customer extid"):
        ClientConfig.create(base_url=BASE_URL, customer=bad, api_token=TOKEN)


def test_extid_is_case_insensitive() -> None:
    cfg = ClientConfig.create(base_url=BASE_URL, customer="UR1ABC23DEF", api_token=TOKEN)
    assert cfg.customer == "UR1ABC23DEF"


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
