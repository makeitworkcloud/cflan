#!/usr/bin/env python3
"""Update one Cloudflare A record when a NetworkManager interface comes up."""

from __future__ import annotations

import os
import socket
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from ipaddress import AddressValueError, IPv4Address
from pathlib import Path
from typing import Any

import netifaces
import yaml
from cloudflare import Cloudflare

PREFERRED_PLAIN_CONFIG = Path("/cflan_vars.yaml")
PREFERRED_SOPS_CONFIG = Path("/cflan_sops_vars.yaml")
LEGACY_PLAIN_CONFIG = Path("/vars.yaml")
LEGACY_SOPS_CONFIG = Path("/sops_vars.yaml")
DEFAULT_CONFIG_PATHS: tuple[tuple[Path, bool], ...] = (
    (PREFERRED_PLAIN_CONFIG, False),
    (PREFERRED_SOPS_CONFIG, True),
    (LEGACY_PLAIN_CONFIG, False),
    (LEGACY_SOPS_CONFIG, True),
)


class CflanError(RuntimeError):
    """An expected configuration, network, or Cloudflare update failure."""


@dataclass(frozen=True)
class CflanConfig:
    """Validated configuration needed to update one A record."""

    token: str
    domain_name: str
    record_name: str | None
    ttl: int
    proxied: bool


def get_local_ip() -> str:
    """Resolve the host's primary IPv4 address without accepting loopback values."""
    hostname = socket.gethostname()
    errors: list[OSError] = []

    for candidate in (f"{hostname}.local", f"{hostname}.lan", hostname):
        try:
            return validate_ipv4(socket.gethostbyname(candidate))
        except OSError as error:
            errors.append(error)

    raise CflanError(
        "Could not resolve a usable IPv4 address for this host."
    ) from errors[-1]


def validate_ipv4(value: str) -> str:
    """Return a usable IPv4 address or raise without contacting Cloudflare."""
    try:
        address = IPv4Address(value)
    except AddressValueError as error:
        raise CflanError("The detected address is not a valid IPv4 address.") from error

    if address.is_loopback or address.is_multicast or address.is_unspecified:
        raise CflanError("The detected address is not suitable for a DNS A record.")
    return str(address)


def validate_network_manager_args(
    local_ip_addr: str, argv: Sequence[str] | None = None
) -> bool:
    """Validate dispatcher arguments; return False for events that should be skipped."""
    args = tuple(sys.argv if argv is None else argv)
    if len(args) < 3:
        print("NetworkManager arguments were not set; proceeding as a standalone run.")
        return True

    interface, action = args[1], args[2]
    if action != "up":
        print(f"Skipping NetworkManager action {action!r}; only 'up' updates DNS.")
        return False

    try:
        interface_ip = netifaces.ifaddresses(interface)[netifaces.AF_INET][0]["addr"]
    except (KeyError, ValueError, IndexError) as error:
        raise CflanError("The NetworkManager interface has no IPv4 address.") from error

    if interface_ip != local_ip_addr:
        raise CflanError(
            "The NetworkManager interface IPv4 address does not match the primary IPv4 address."
        )
    return True


def resolve_config_path(
    override: str | None = None,
    config_paths: Sequence[tuple[Path, bool]] = DEFAULT_CONFIG_PATHS,
) -> tuple[Path, bool]:
    """Find the root-volume configuration, preferring the cflan-prefixed names."""
    selected = override or os.environ.get("CFLAN_CONFIG")
    if selected:
        path = Path(selected)
        return path, path.name in {
            PREFERRED_SOPS_CONFIG.name,
            LEGACY_SOPS_CONFIG.name,
        }

    for path, encrypted in config_paths:
        if path.is_file():
            return path, encrypted

    searched = ", ".join(str(path) for path, _ in config_paths)
    raise CflanError(f"No configuration file was found. Searched: {searched}")


def read_config_file(path: Path, encrypted: bool) -> dict[str, Any]:
    """Read plaintext YAML or decrypt a SOPS YAML file without writing plaintext."""
    try:
        if encrypted:
            result = subprocess.run(
                ["sops", "decrypt", str(path)],
                check=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
            loaded = yaml.safe_load(result.stdout)
        else:
            loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise CflanError(
            f"Configuration file or SOPS executable was not found: {path}"
        ) from error
    except subprocess.CalledProcessError as error:
        raise CflanError("SOPS could not decrypt the configuration file.") from error
    except subprocess.TimeoutExpired as error:
        raise CflanError("SOPS decryption timed out.") from error
    except (OSError, yaml.YAMLError) as error:
        raise CflanError("Configuration could not be read as YAML.") from error

    if not isinstance(loaded, dict):
        raise CflanError("Configuration must be a YAML mapping.")
    return loaded


def get_yaml_vars(config_path: str | None = None) -> dict[str, Any]:
    """Compatibility helper that returns validated-path YAML values."""
    path, encrypted = resolve_config_path(config_path)
    print(f"Loading configuration from {path}.")
    return read_config_file(path, encrypted)


def parse_config(values: dict[str, Any]) -> CflanConfig:
    """Validate user-controlled values before creating a Cloudflare client."""
    token = values.get("cf_token")
    domain_name = values.get("cf_domain_name")
    record_name = values.get("cf_record_name")
    ttl = values.get("cf_ttl", 1)
    proxied = values.get("cf_proxied", False)

    if not isinstance(token, str) or not token.strip():
        raise CflanError("Configuration requires a non-empty cf_token.")
    if not isinstance(domain_name, str) or not domain_name.strip():
        raise CflanError("Configuration requires a non-empty cf_domain_name.")
    if record_name is not None and (
        not isinstance(record_name, str) or not record_name.strip()
    ):
        raise CflanError("cf_record_name must be a non-empty string when provided.")
    if (
        isinstance(ttl, bool)
        or not isinstance(ttl, int)
        or (ttl != 1 and not 60 <= ttl <= 86400)
    ):
        raise CflanError("cf_ttl must be 1 or an integer from 60 through 86400.")
    if not isinstance(proxied, bool):
        raise CflanError("cf_proxied must be a boolean.")

    return CflanConfig(
        token=token,
        domain_name=domain_name.rstrip("."),
        record_name=record_name.rstrip(".") if record_name else None,
        ttl=ttl,
        proxied=proxied,
    )


def get_record_name(config: CflanConfig) -> str:
    """Return a fully qualified record name, preserving the legacy hostname default."""
    hostname = config.record_name or socket.gethostname()
    if hostname.endswith(f".{config.domain_name}"):
        return hostname
    return f"{hostname}.{config.domain_name}"


def get_zone_info(client: Any, domain_name: str) -> tuple[str, str]:
    """Find exactly the configured Cloudflare zone."""
    zones = list(client.zones.list(name=domain_name, per_page=1))
    matches = [zone for zone in zones if getattr(zone, "name", None) == domain_name]
    if len(matches) != 1:
        raise CflanError("Cloudflare did not return exactly one matching zone.")

    zone = matches[0]
    zone_id = getattr(zone, "id", None)
    zone_name = getattr(zone, "name", None)
    if not isinstance(zone_id, str) or not isinstance(zone_name, str):
        raise CflanError("Cloudflare returned an invalid zone response.")
    return zone_id, zone_name


def get_dns_record(client: Any, zone_id: str, record_name: str) -> Any | None:
    """Find one A record, refusing to mutate an ambiguous record set."""
    records = list(
        client.dns.records.list(
            zone_id=zone_id,
            name=record_name,
            type="A",
            per_page=100,
        )
    )
    if len(records) > 1:
        raise CflanError(
            "More than one matching A record exists; refusing to choose one."
        )
    return records[0] if records else None


def create_dns_record(
    client: Any,
    zone_id: str,
    record_name: str,
    ip_addr: str,
    config: CflanConfig,
) -> None:
    """Create the configured A record with explicit safe defaults."""
    client.dns.records.create(
        zone_id=zone_id,
        name=record_name,
        type="A",
        content=ip_addr,
        ttl=config.ttl,
        proxied=config.proxied,
    )
    print(f"Created DNS record {record_name}.")


def update_dns_record(
    client: Any,
    zone_id: str,
    record: Any,
    record_name: str,
    ip_addr: str,
) -> None:
    """Patch only the A-record content, retaining the record's existing settings."""
    if getattr(record, "content", None) == ip_addr:
        print(f"DNS record {record_name} already matches the local IPv4 address.")
        return

    record_id = getattr(record, "id", None)
    ttl = getattr(record, "ttl", None)
    if not isinstance(record_id, str) or not isinstance(ttl, int):
        raise CflanError("Cloudflare returned an invalid DNS record response.")

    client.dns.records.edit(
        record_id,
        zone_id=zone_id,
        name=record_name,
        type="A",
        content=ip_addr,
        ttl=ttl,
        proxied=bool(getattr(record, "proxied", False)),
    )
    print(f"Updated DNS record {record_name}.")


def set_dns(
    argv: Sequence[str] | None = None,
    config_path: str | None = None,
    client_factory: Any = Cloudflare,
) -> None:
    """Reconcile the configured Cloudflare A record with this host's IPv4 address."""
    local_ip_addr = get_local_ip()
    if not validate_network_manager_args(local_ip_addr, argv):
        return

    config = parse_config(get_yaml_vars(config_path))
    record_name = get_record_name(config)
    client = client_factory(api_token=config.token, timeout=10.0)
    zone_id, _ = get_zone_info(client, config.domain_name)
    record = get_dns_record(client, zone_id, record_name)

    if record is None:
        create_dns_record(client, zone_id, record_name, local_ip_addr, config)
    else:
        update_dns_record(client, zone_id, record, record_name, local_ip_addr)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the dispatcher entry point without leaking configuration values."""
    try:
        set_dns(argv=argv)
    except CflanError as error:
        print(f"cflan: {error}", file=sys.stderr)
        return 1
    except (
        Exception
    ) as error:  # Cloudflare SDK exceptions vary by transport and status.
        print(
            f"cflan: Cloudflare update failed ({type(error).__name__}).",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
