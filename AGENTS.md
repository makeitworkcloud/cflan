# Agent Instructions

Python utility for NetworkManager-dispatcher-driven Cloudflare DNS updates.

Preserve dispatcher integration, idempotent DNS behavior, and test coverage. Use GitHub MCP and PR CI as validation authority; do not install packages, run local network hooks, or execute live DNS updates from this server.

Never expose Cloudflare tokens, API responses containing credentials, host-specific private data, or production DNS values not already intended for public repository content.
