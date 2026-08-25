# CFLAN

[![CI](https://github.com/welchworks/cflan/actions/workflows/ci.yml/badge.svg)](https://github.com/welchworks/cflan/actions/workflows/ci.yml)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
[![Code style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

> Integrating LAN infrastructure with Cloudflare services

CFLAN automatically updates Cloudflare DNS records with your local machine's IP address whenever your network connection changes. This is particularly useful for home servers, NAS devices, or any machine that needs a consistent DNS name despite having a dynamic local IP.

## Features

- **Automatic DNS Updates**: Updates Cloudflare DNS A records when network interfaces come up
- **NetworkManager Integration**: Runs as a NetworkManager dispatcher script
- **SOPS Support**: Supports encrypted configuration using [SOPS](https://github.com/getsops/sops)
- **IP Validation**: Ensures the correct interface IP is used before updating
- **Idempotent**: Only updates DNS when the IP address has actually changed

## Prerequisites

- Python 3.9 or higher
- NetworkManager (for dispatcher script functionality)
- Root access (for installing dispatcher scripts)
- Cloudflare API Token with DNS edit permissions
- (Optional) SOPS for encrypted configuration files

## Installation

### From Source

```bash
# Clone the repository
git clone https://github.com/welchworks/cflan.git
cd cflan

# Create configuration file (see Configuration section below)
# Then install (requires root)
sudo python install.py
```

### Development Installation

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
pre-commit install
```

## Configuration

Create a configuration file with your Cloudflare credentials:

### Option 1: Plain YAML (`vars.yaml`)

```yaml
cf_token: "your-cloudflare-api-token"
cf_domain_name: "example.com"
```

### Option 2: Encrypted with SOPS (`sops_vars.yaml`)

```bash
# Create encrypted config
cat > vars.yaml <<EOF
cf_token: "your-cloudflare-api-token"
cf_domain_name: "example.com"
EOF

# Encrypt with SOPS
sops encrypt vars.yaml > sops_vars.yaml
rm vars.yaml
```

### Cloudflare API Token Setup

1. Go to [Cloudflare API Tokens](https://dash.cloudflare.com/profile/api-tokens)
2. Click "Create Token"
3. Use the "Edit zone DNS" template
4. Select your zone (domain)
5. Create the token and copy it for your config

## Usage

### As a NetworkManager Dispatcher Script

When installed via `install.py`, the script runs automatically when network interfaces change:

```bash
# Trigger manually (for testing)
sudo /etc/NetworkManager/dispatcher.d/set_dns eth0 up
```

### Standalone Execution

```bash
# From the project directory
python set_dns.py
```

The script will:
1. Detect your local IP address
2. Read configuration from `vars.yaml` or decrypt `sops_vars.yaml`
3. Find the Cloudflare zone for your domain
4. Check for an existing DNS record
5. Create or update the A record with your current IP

## Project Structure

```
cflan/
├── .github/workflows/    # CI/CD configuration
├── tests/                # Test suite
├── set_dns.py           # Main application script
├── install.py           # Installation script
├── vars.yaml            # Configuration (unencrypted)
├── pyproject.toml       # Project metadata and tool config
├── requirements.txt     # Production dependencies
├── requirements-dev.txt # Development dependencies
└── README.md            # This file
```

## Development

### Running Tests

```bash
pytest
```

With coverage:

```bash
pytest --cov=cflan --cov-report=term-missing
```

### Code Quality

This project uses:
- **Ruff**: Fast Python linter and formatter
- **MyPy**: Static type checking
- **Pre-commit**: Git hooks for code quality

```bash
# Run linting
ruff check .
ruff format .

# Run type checking
mypy set_dns.py

# Run all pre-commit hooks
pre-commit run --all-files
```

### Continuous Integration

GitHub Actions runs the following on every push and PR:
- Pre-commit hooks
- Tests across Python 3.9-3.13
- Type checking with mypy
- Coverage reporting

## Security Notes

- The configuration file (`vars.yaml` or `sops_vars.yaml`) is installed with `600` permissions (readable only by root)
- The dispatcher script is installed with `700` permissions (executable only by root)
- Use SOPS encryption for production deployments to protect API tokens
- Store your Cloudflare API Token securely; it grants DNS edit access

## Troubleshooting

### "Must run as root"
The install script requires root privileges to install files to `/etc/NetworkManager/dispatcher.d/`.

### "sops must be installed"
If using `sops_vars.yaml`, ensure SOPS is installed: https://github.com/getsops/sops

### "The IP address is a value for localhost"
The script prevents updating DNS with localhost addresses (127.0.0.x). Check your network configuration.

## License

This project is licensed under the GNU General Public License v3.0 - see the [LICENSE](LICENSE) file for details.

## Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests and linting
5. Submit a pull request

## Author

**Steven Welch** - steven@makeitwork.cloud

Project Link: [https://github.com/welchworks/cflan](https://github.com/welchworks/cflan)
