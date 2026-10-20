# Security Policy

## Reporting a vulnerability

Please report security issues in this library, or in the Onetime Secret
service, by email to **security@onetimesecret.com**. Do not open a public
GitHub issue.

Include the affected version, steps to reproduce, and any proof of concept.
You will receive an acknowledgement within 5 business days. The full policy, including response timelines, is in the main project's [SECURITY.md](https://github.com/onetimesecret/onetimesecret/blob/main/SECURITY.md).

## Supported versions

Only the latest minor release receives security fixes.

## Scope notes

- This client never logs secret values, passphrases, or API tokens.
- Secrets are sent to the server over TLS as provided. Client-side encryption
  before upload is planned; until then, treat the server as a party that can
  read the plaintext while the secret is stored.
