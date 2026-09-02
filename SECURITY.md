# Security policy

## Reporting a vulnerability

Do **not** disclose Cloudflare tokens, decrypted SOPS data, host-specific paths, internal DNS values, or reproduction data containing credentials in a public issue.

Use GitHub private vulnerability reporting for this repository when it is available. If it is unavailable, contact the maintainer through the public address in the project metadata and include only the minimum information needed to establish impact.

## Supported versions

Security fixes are made against the current `main` branch until versioned releases are published. No release branch or older version currently receives security support.

## Deployment guidance

Use a Cloudflare API token restricted to the specific zone and the minimum DNS-edit capability. Keep plaintext and encrypted configuration files root-owned with mode `0600`. CFLAN never needs a global API key.
