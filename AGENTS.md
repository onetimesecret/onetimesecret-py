# AGENTS.md

Official Python SDK for the Onetime Secret API (v2). Distribution
`onetime-secret`, import `onetimesecret`.

## Commands

```sh
uv sync                        # dev environment
uv run pytest                  # unit tests (mocked HTTP, no network)
uv run ruff check . && uv run ruff format --check . && uv run mypy
```

## Layout

- `src/onetimesecret/_config.py`: `ClientConfig` with env fallbacks and
  validation (base URL, extid format, credential pairing).
- `src/onetimesecret/_exceptions.py`: exception hierarchy and the ADR-013
  `error`/`error_type` → class mapping.
- `src/onetimesecret/_base_client.py`: request building, response parsing,
  retry policy. No I/O.
- `src/onetimesecret/_client.py`: `Client` / `AsyncClient` own the httpx
  client and run the retry loop.
- `src/onetimesecret/resources/_specs.py`: the wire contract, one function
  per operation returning a `RequestSpec`. Change paths and payloads here only.
- `src/onetimesecret/resources/{secrets,receipts}.py`: sync and async
  dispatchers over `_specs`.
- `examples/basic.py`: end-to-end walkthrough against a real server; linted
  and type-checked with the package.

## Rules

- Follow idiomatic Python; do not mirror the Ruby SDK's internals. The
  cross-SDK contract is limited to env var names, auth, error semantics, and
  the resource vocabulary.
- Responses are returned in the server's shape. Do not add models or
  normalise fields without a design discussion.
- POST is never retried.
- Never log secret values or credentials.
- The API reference is https://api.onetimesecret.com (v2 spec at
  `/doc/api-v2.json`). When the spec and server disagree, the server wins;
  note the discrepancy in a comment and a test.
