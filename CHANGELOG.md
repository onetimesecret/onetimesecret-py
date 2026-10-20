# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project
adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- Initial `Client` and `AsyncClient` for API v2, built on httpx.
- `secrets` (conceal, generate, reveal, show, status, status_list) and
  `receipts` (show, recent, burn, update) resources, plus `status`, `version`
  and `supported_locales`.
- Typed exception hierarchy following the ADR-013 error contract, with
  `AccountRequiredError` for the "requires account" form error.
- Retries with exponential backoff for idempotent requests; `Retry-After`
  honoured.
- `client.request()` for unwrapped endpoints, with `raise_on_error=False`
  to inspect error responses without an exception.
- Environment fallbacks shared with the other SDKs: `ONETIME_BASE_URL`,
  `ONETIME_CUSTOMER_EXTID`, `ONETIME_API_TOKEN`.

[Unreleased]: https://github.com/onetimesecret/onetimesecret-py/commits/main
