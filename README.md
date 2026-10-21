# Onetime Secret Python Client

The official Python client for the [Onetime Secret](https://onetimesecret.com)
API. Share sensitive information through a link that can only be viewed once.

The package on PyPI is **`onetime-secret`**; the import name is
**`onetimesecret`**. This repository, **`onetimesecret-py`**, is the Python SDK
in the Onetime Secret SDK family. Each language has its own repository, and the
repository name is not the package name.

- **Sync and async**: `Client` and `AsyncClient` share one API, built on
  [httpx](https://www.python-httpx.org/).
- **Typed**: ships `py.typed`; passes `mypy --strict`.
- **API v2**: the stable, recommended API. The response shape is the API's,
  unchanged.
- **Python 3.10+**.

API reference: [api.onetimesecret.com](https://api.onetimesecret.com).

## Installation

```sh
pip install onetime-secret
# or
uv add onetime-secret
```

## Quick start

```python
from onetimesecret import Client

client = Client(
    base_url="https://ca.onetimesecret.com",  # your region's API host (required)
    customer="ur1abc23defghijklmnop",  # customer extid (see below)
    api_token="...",  # API token from your account page
)

# Conceal a secret you already have
res = client.secrets.conceal("hunter2", ttl=3600, passphrase="pw12")
res["record"]["receipt"]["identifier"]  # the receipt (creator) key
res["record"]["secret"]["identifier"]  # the secret (recipient) key

# Generate a random secret server-side
client.secrets.generate(ttl=86_400)

# Reveal (consume) a secret, one-time only. Accepts a key or the full link.
secret = client.secrets.reveal("abc123secretkey", passphrase="pw12")
secret["record"]["secret_value"]

# Service status
client.status()
```

Async:

```python
from onetimesecret import AsyncClient

async with AsyncClient(base_url="https://eu.onetimesecret.com") as client:
    res = await client.secrets.conceal("no account needed", guest=True)
```

### Authentication

Authentication uses HTTP Basic, where the **customer extid** is the username
and your **API token** is the password.

The customer extid is a short, opaque identifier that begins with `ur`, for
example `ur1abc23def`. It is shown, with a copy button, at the bottom of the
user menu when you are signed in.

The format is checked at construction, so a value of the wrong kind fails
immediately rather than at the first request:

```python
Client(base_url="https://ca.onetimesecret.com", customer="acct-123", api_token="...")
# ConfigurationError: customer 'acct-123' is not a customer extid: extids begin
# with "ur" (e.g. "ur1abc23def"). ...
```

### Base URL (required)

`base_url` must be the API host for your region, your self-hosted domain, or
your custom domain. There is no default: deployments are region-isolated for
data sovereignty, so the client cannot guess one for you.

| Region | Host |
|---|---|
| United States | `https://us.onetimesecret.com` |
| Europe | `https://eu.onetimesecret.com` |
| United Kingdom | `https://uk.onetimesecret.com` |
| Canada | `https://ca.onetimesecret.com` |
| Aotearoa New Zealand | `https://nz.onetimesecret.com` |

The apex `onetimesecret.com` is the company website, not an API host, and is
rejected with a helpful error. The hosts are also available as
`onetimesecret.REGIONAL_HOSTS`.

### Configuration

| Option | Default | Notes |
|---|---|---|
| `base_url` | (**required**) | Region, self-hosted, or custom domain |
| `customer` | `$ONETIME_CUSTOMER_EXTID` | Customer extid (`ur…`) |
| `api_token` | `$ONETIME_API_TOKEN` | API token |
| `timeout` | `30` | Seconds, per request |
| `max_retries` | `2` | Retries for idempotent (GET, HEAD) requests only |
| `user_agent` | `onetime-secret-python/<version> …` | |
| `default_headers` | `{}` | Sent with every request |
| `http_client` | none | A preconfigured `httpx.Client` / `httpx.AsyncClient` |

Environment fallback: `base_url` ← `ONETIME_BASE_URL`. The variable names are
shared across the Onetime Secret SDKs.

A client owns an `httpx` connection pool. Reuse it, and close it when you are
done (`client.close()` / `await client.aclose()`, or use it as a context
manager). It is safe to share between threads.

### Retries

Connection errors and `429`/`5xx` responses are retried with exponential
backoff for idempotent requests (GET, HEAD) only, up to `max_retries` times. A
`Retry-After` header is honoured. POST requests are never retried: concealing
twice creates two secrets, and revealing or burning is destructive.

## Anonymous and guest usage

A client created without credentials is anonymous and can use public and guest
endpoints:

```python
guest = Client(base_url="https://ca.onetimesecret.com")  # no credentials
guest.secrets.conceal("no account needed", guest=True)
```

## Resources

### `client.secrets`

| Method | |
|---|---|
| `conceal(secret, *, ttl, passphrase, recipient, share_domain, display_type, guest)` | alias `share` |
| `generate(*, ttl, passphrase, recipient, share_domain, guest)` | |
| `reveal(key, *, passphrase, guest)` | key or full URL |
| `show(key, *, guest)` | metadata without the value |
| `status(key)` | |
| `status_list(keys)` | |

### `client.receipts`

| Method | |
|---|---|
| `show(key, *, guest)` | |
| `recent()` | |
| `burn(key, *, passphrase, guest)` | |
| `update(key, *, memo)` | |

### Meta

`client.status()`, `client.version()` (authenticated), `client.supported_locales()`.

### Anything else

`client.request(method, path, json=..., params=...)` issues a request against
any path under `/api/v2` and applies the same auth, retry and error handling.
Pass `raise_on_error=False` to get an error status back as a `Response`
instead of an exception.

## Responses

Resource methods return an `onetimesecret.Response`, a read-only mapping over
the parsed JSON body with the HTTP metadata alongside:

```python
res = client.secrets.conceal("hi")
res["record"]  # the API's own shape, unchanged
res.get("details")
res.data  # the parsed body
res.status_code  # 200
res.request_id  # x-request-id, for support requests
```

The body is not normalised or modelled. v2 returns string-typed fields and
nests data under `record` / `records` / `details`; read the
[API reference](https://api.onetimesecret.com/doc/api-v2) for each endpoint's
schema.

## Errors

HTTP errors (status >= 400) raise typed exceptions following the API's
ADR-013 error contract (`{"error": ..., "error_type": ..., ...}`):

```python
from onetimesecret import APIError, NotFoundError, RateLimitError

try:
    client.secrets.reveal("missing")
except NotFoundError as e:
    e.message  # human-readable ("error" field)
    e.error_type  # machine-readable ("RecordNotFound")
    e.status_code  # 404
    e.request_id  # quote this when reporting a problem
except RateLimitError as e:
    e.retry_after
except APIError as e:
    ...  # any other API error
```

| Exception | When |
|---|---|
| `BadRequestError` | 400 / 422 / `FormError` (see `.field`) |
| `AuthenticationError` | 401 |
| `AccountRequiredError` | the operation needs an authenticated account; subclasses `AuthenticationError` |
| `ForbiddenError` | 403 / `Forbidden`, `GuestRoutesDisabled` (see `.code`) |
| `EntitlementError` | `EntitlementRequired` (see `.entitlement`); subclasses `ForbiddenError` |
| `NotFoundError` | 404 / `RecordNotFound` |
| `ConflictError` | 409 |
| `RateLimitError` | 429 / `LimitExceeded` (see `.retry_after`) |
| `ServerError` | 5xx |
| `APIConnectionError` / `APITimeoutError` | network failures (`__cause__` is the `httpx` exception) |
| `ConfigurationError` | bad `base_url`, malformed customer extid, incomplete credentials (raised at construction) |

All inherit from `OnetimeSecretError`.

`AccountRequiredError` exists because the service reports "this needs an
account" inside a `400` form-error body (`field: "requires_account"`). Mapping
that to `BadRequestError` sends people auditing a request payload that was
never the problem.

## Logging

The library logs one `DEBUG` line per request to the `onetimesecret` logger.
Secret values and credentials are never logged.

## Example

[`examples/basic.py`](examples/basic.py) round-trips a secret against a real
server: conceal, read the receipt, reveal, and read the receipt again to see
the state change from `new` to `revealed`. It reads `ONETIME_BASE_URL` and,
optionally, `ONETIME_CUSTOMER_EXTID` / `ONETIME_API_TOKEN` from the
environment, and runs anonymously through the guest endpoints when no
credentials are set:

```sh
ONETIME_BASE_URL=https://eu.onetimesecret.com uv run examples/basic.py
```

Point `ONETIME_BASE_URL` at your own deployment to run it against a
self-hosted server.

## Development

```sh
uv sync                 # create .venv with dev dependencies
uv run pytest           # unit tests (no network)
uv run ruff check .     # lint
uv run ruff format .    # format
uv run mypy             # type-check

ONETIME_LIVE=1 uv run pytest -m live   # ONETIME_BASE_URL overrides the default (EU) host
```

See [CONTRIBUTING.md](CONTRIBUTING.md). Maintainers: see
[docs/releasing.md](docs/releasing.md).

## License

MIT. See [LICENSE](LICENSE).
