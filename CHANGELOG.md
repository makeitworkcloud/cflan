# Changelog

All notable changes to CFLAN are documented here.

## Unreleased

### Changed

- Migrated the updater to the supported Cloudflare Python SDK interface.
- Replaced delete-and-create record changes with an in-place Cloudflare PATCH update.
- Added preferred root-volume configuration names: `cflan_vars.yaml` and `cflan_sops_vars.yaml`.
- Preserved `vars.yaml` and `sops_vars.yaml` as root-volume compatibility aliases.
- Added configuration validation, safer IPv4 checks, duplicate-record protection, package build verification, and public contributor/security guidance.
