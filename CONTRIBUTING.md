# Contributing

Thanks for helping improve the Onetime Secret Python client.

## Setup

Install [uv](https://docs.astral.sh/uv/), then:

```sh
git clone https://github.com/onetimesecret/onetimesecret-py
cd onetimesecret-py
uv sync            # creates .venv with the pinned dev dependencies
uv run pytest      # unit tests; no network access needed
```

Optional, to run the linters on each commit:

```sh
uvx pre-commit install
```

## Checks

CI runs exactly these, so run them before opening a pull request:

```sh
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest
```

Unit tests mock HTTP with [respx](https://lundberg.github.io/respx/) and never
touch the network. Live tests are opt-in:

```sh
ONETIME_LIVE=1 ONETIME_BASE_URL=https://eu.onetimesecret.com uv run pytest -m live
```

Set `ONETIME_CUSTOMER_EXTID` and `ONETIME_API_TOKEN` as well to exercise the
authenticated endpoints.

Against a local server, start it with `HOST` set to the host and port in
`ONETIME_BASE_URL` (for example `HOST=127.0.0.1:7143`): the server builds the
links in receipts from `HOST`, which defaults to `localhost:3000`.

## Guidelines

- Keep the wire contract in `src/onetimesecret/resources/_specs.py`. The sync
  and async resource classes only dispatch; they should not know paths or
  payload shapes.
- Do not normalise API responses. The library returns the server's shape so
  that the [API reference](https://api.onetimesecret.com) stays the source of
  truth.
- POST requests are never retried. Concealing twice creates two secrets;
  revealing or burning is destructive.
- Never log secret values or credentials.
- Every behaviour change gets a unit test and a line under `[Unreleased]` in
  `CHANGELOG.md`.
- Public API is typed and documented with Google-style docstrings; `mypy
  --strict` must pass.

## Conduct

This project follows the [Code of Conduct](CODE_OF_CONDUCT.md).

## Reporting security issues

See [SECURITY.md](SECURITY.md). Please do not open public issues for
vulnerabilities.
