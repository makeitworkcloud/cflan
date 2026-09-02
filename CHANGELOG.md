# Changelog

All notable changes to CFLAN are documented here.

## Unreleased

### Added

- GitHub-Release-only CD: a successful `ci` run for a push to `main` automatically creates a GitHub Release tagged `v<version>` (from `pyproject.toml`) with the built wheel, sdist, and `SHA256SUMS` when no release for that version exists. The version must be increased before a new release; a tag that exists without a release fails closed. No PyPI publishing is used, and a release is artifact publication, not installed-host validation.

### Changed

- Migrated the updater to the supported Cloudflare Python SDK interface.
- Replaced delete-and-create record changes with an in-place Cloudflare PATCH update.
- Added preferred root-volume configuration names: `cflan_vars.yaml` and `cflan_sops_vars.yaml`.
- Preserved `vars.yaml` and `sops_vars.yaml` as root-volume compatibility aliases.
- Added configuration validation, safer IPv4 checks, duplicate-record protection, package build verification, and public contributor/security guidance.
