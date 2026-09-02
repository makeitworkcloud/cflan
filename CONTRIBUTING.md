# Contributing to CFLAN

## Scope and safety

CFLAN changes Cloudflare DNS from a NetworkManager dispatcher hook. Do not commit API tokens, decrypted SOPS files, real hostnames, DNS values, or root-volume contents. Do not test changes against production DNS as part of a pull request.

Preserve these compatibility contracts unless a change explicitly documents a migration:

- Dispatcher entry point: `/etc/NetworkManager/dispatcher.d/set_dns`
- Preferred root-volume configuration: `/cflan_vars.yaml` or `/cflan_sops_vars.yaml`
- Legacy root-volume aliases: `/vars.yaml` or `/sops_vars.yaml`

## Development workflow

1. Create a focused branch and add unit tests for behavior changes.
2. Install development dependencies with `python -m pip install '.[dev]'`.
3. Run `pre-commit run --all-files`, `python -m pytest --cov`, `mypy set_dns.py`, and `python -m build`.
4. Open a pull request explaining configuration, DNS, and rollback impact.

`python3 set_dns.py --dry-run [--config PATH]` is available as a non-mutating preflight for local configuration checks. It does not validate Cloudflare credentials, SOPS key availability for root, or actual dispatcher execution, and it is not a substitute for CI.

CI is the validation authority. A passing unit-test suite does not prove that a changed dispatcher hook, SOPS configuration, or Cloudflare token works in an installed host.

## Pull requests

Keep changes narrow. Document any changed default configuration name, API permission, record behavior, package version, or installed-path contract. Reviewers must be able to determine whether the change is source-only or requires a separate installation step.
