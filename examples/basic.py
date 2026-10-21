"""Round-trip a secret against a real Onetime Secret server.

Conceals a secret, reads its receipt, reveals the secret, then reads the
receipt again to show the state change. Configuration comes from the
environment variables every Onetime Secret SDK reads:

    ONETIME_BASE_URL=https://eu.onetimesecret.com uv run examples/basic.py

Set ONETIME_CUSTOMER_EXTID and ONETIME_API_TOKEN as well to run as your
account; without them the script runs anonymously through the guest
endpoints. Against a self-hosted server, point ONETIME_BASE_URL at it.
"""

from __future__ import annotations

import sys

from onetimesecret import Client, OnetimeSecretError


def main() -> int:
    """Conceal, inspect, reveal, inspect again. Returns the process exit code."""
    with Client() as client:
        # Anonymous clients must use the guest endpoints; authenticated ones
        # use the account endpoints, where the secret appears in the account's
        # recent receipts.
        guest = client.config.anonymous
        who = "anonymously" if guest else f"as {client.config.customer}"
        print(f"Using {client.base_url} {who}")

        created = client.secrets.conceal("hunter2", ttl=300, guest=guest)
        receipt_key = created["record"]["receipt"]["identifier"]
        secret_key = created["record"]["secret"]["identifier"]
        print(f"Share link: {client.base_url}/secret/{secret_key}")

        before = client.receipts.show(receipt_key, guest=guest)
        print(f"Receipt state before reveal: {before['record']['state']}")

        revealed = client.secrets.reveal(secret_key, guest=guest)
        print(f"Revealed value: {revealed['record']['secret_value']}")

        after = client.receipts.show(receipt_key, guest=guest)
        print(f"Receipt state after reveal:  {after['record']['state']}")

        if before["record"]["state"] == after["record"]["state"]:
            print("Receipt state did not change after reveal", file=sys.stderr)
            return 1
        return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except OnetimeSecretError as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)
