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
- `secrets.generate()` claims the generated value, which the server discloses
  only on the first read of the receipt, and returns it at
  `res["details"]["secret_value"]`. A failed claim is attached as a
  `ClaimError` (status and error type only, never the body) at
  `res["details"]["claim_error"]` instead of raising; `claim_value=False`
  skips the extra request.
- Typed exception hierarchy following the ADR-013 error contract, with
  `AccountRequiredError` for the "requires account" form error.
- Retries with exponential backoff for idempotent requests; `Retry-After`
  honoured.
- `client.request()` for unwrapped endpoints, with `raise_on_error=False`
  to inspect error responses without an exception.
- Environment fallbacks shared with the other SDKs: `ONETIME_BASE_URL`,
  `ONETIME_CUSTOMER_EXTID`, `ONETIME_API_TOKEN`.
- `examples/basic.py`, an end-to-end conceal / receipt / reveal walkthrough
  configured from the same environment variables.

[Unreleased]: https://github.com/onetimesecret/onetimesecret-py/commits/main
[0.1.0]: https://github.com/onetimesecret/onetimesecret-py/releases/tag/v0.1.0
