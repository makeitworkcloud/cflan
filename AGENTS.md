# Agent Instructions

Python utility for NetworkManager-dispatcher-driven Cloudflare DNS updates.

Preserve dispatcher integration, idempotent DNS behavior, and test coverage. Use GitHub MCP and PR CI as validation authority; do not install packages, run local network hooks, or execute live DNS updates from this server.

Never expose Cloudflare tokens, API responses containing credentials, host-specific private data, or production DNS values not already intended for public repository content.

## Changelog and release policy

- Every pull request must update `CHANGELOG.md` with a reader-ready, user-facing note under `## Unreleased`. CI enforces this and fails pull requests that do not change the changelog.
- When `version` in `pyproject.toml` is increased, promote the accumulated Unreleased notes into a `## [<version>] - YYYY-MM-DD` section in the same commit.
- The release CD extracts exactly the `## [<version>]` section and publishes it as the GitHub Release body; it fails closed before creating any tag or release when that section is missing or empty.
- Release publication is artifact publication only. It does not prove installation, host, or DNS behavior; never claim installed-host validation from a published release.
