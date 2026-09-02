# Changelog

All notable changes to CFLAN are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Every pull request must add a reader-ready, user-facing note under `## Unreleased`;
CI fails pull requests that do not change this file. When `version` in
`pyproject.toml` is increased, the accumulated Unreleased notes are promoted into a
`## [<version>] - YYYY-MM-DD` section in the same commit. The release CD extracts
exactly that versioned section and publishes it as the GitHub Release body.

## Unreleased

## [1.1.0] - 2026-09-02

### Added

- Preferred root-volume configuration names `cflan_vars.yaml` and `cflan_sops_vars.yaml`, with `vars.yaml` and `sops_vars.yaml` preserved as root-volume compatibility aliases; no configuration migration is required.
- Non-mutating preflight dry run (`set_dns.py --dry-run [--config PATH]`) that validates root-volume configuration selection and parsing, the resolved local IPv4 address, the dispatcher positional arguments, and the derived FQDN, then prints the intended reconciliation without constructing a Cloudflare client or performing any Cloudflare API call.
- Configuration validation, safer IPv4 checks, duplicate-record protection, package build verification, unit tests for the updater and installer, and public contributor/security guidance.
- GitHub-Release-only CD: a successful `ci` run for a push to `main` automatically creates a GitHub Release tagged `v<version>` (from `pyproject.toml`) with the built wheel, sdist, and `SHA256SUMS` when no release for that version exists. The release body is exactly this changelog section; a missing or empty section fails closed before any tag or release is created, and a tag that exists without a release is never moved or reused. No PyPI publishing is used, and a release is artifact publication, not installed-host validation.

### Changed

- Migrated the updater to the supported Cloudflare Python SDK interface.
- Replaced delete-and-create record changes with an in-place Cloudflare PATCH update, preserving the record and avoiding an avoidable DNS gap.
