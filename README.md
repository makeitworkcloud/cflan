# CFLAN

[![CI](https://github.com/makeitworkcloud/cflan/actions/workflows/ci.yml/badge.svg)](https://github.com/makeitworkcloud/cflan/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)

> NetworkManager-driven Cloudflare DNS updates for LAN hosts.

CFLAN reconciles one Cloudflare A record with a machine's active IPv4 address when a NetworkManager interface comes up. It is designed for root-owned configuration supplied from the host's root/volume area; it does not create, persist, or print credentials.

## Requirements

- Linux with NetworkManager dispatcher support
- Python 3.10 or later
- A Cloudflare API token limited to **Zone / DNS / Edit** for the target zone
- Optional: SOPS available and configured for root when using encrypted configuration

## Configuration contract

CFLAN searches these root-volume paths in order:

1. `/cflan_vars.yaml` — preferred plaintext name
2. `/cflan_sops_vars.yaml` — preferred SOPS-encrypted name
3. `/vars.yaml` — supported legacy alias
4. `/sops_vars.yaml` — supported legacy SOPS alias

`CFLAN_CONFIG` can override the path for a controlled deployment. The existing `/vars.yaml` and `/sops_vars.yaml` contract remains supported; no secret is copied into another directory by the updater.

Example structure (do **not** commit a real token):

```yaml
cf_token: "replace-with-a-Cloudflare-API-token"
cf_domain_name: "example.com"
# Optional full FQDN; defaults to <hostname>.<cf_domain_name>
# cf_record_name: "host.example.com"
# Optional; 1 means Cloudflare automatic TTL
# cf_ttl: 1
# Optional; defaults to false to avoid proxying a LAN address
# cf_proxied: false
```

## Installation

The existing installation model is preserved: place one configuration file beside the scripts, then run the root-only installer.

```bash
git clone https://github.com/makeitworkcloud/cflan.git
cd cflan
sudo python3 install.py
```

The installer copies `set_dns.py` to `/etc/NetworkManager/dispatcher.d/set_dns` with mode `0700`. It copies the first configuration filename it finds in the priority listed above to its matching root-volume path with mode `0600`.

> A Cloudflare DNS record containing an RFC1918 address is useful only for clients that can route to that LAN. CFLAN does not make a private address reachable from the public Internet.

## Behavior and safety

- Only NetworkManager `up` events update DNS; other dispatcher events are skipped.
- The interface IPv4 address must equal the resolved primary host IPv4 address.
- Loopback, multicast, unspecified, and malformed addresses are rejected before any API call.
- Exactly one matching zone and zero or one matching A record are required. Duplicate records fail closed.
- Existing records are updated with Cloudflare PATCH rather than delete-and-recreate, preserving the record and avoiding an avoidable DNS gap.
- SOPS plaintext exists only in the updater process memory.

## Development

```bash
python -m pip install '.[dev]'
python -m pytest --cov
ruff check .
ruff format --check .
mypy set_dns.py
python -m build
```

CI runs formatting/linting hooks, unit tests and coverage on Python 3.10–3.13, mypy, and a wheel build/install smoke test. Unit tests do not contact Cloudflare or invoke NetworkManager.

See [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md) before opening an issue or pull request.

## License

CFLAN is licensed under [GPL-3.0](LICENSE).
