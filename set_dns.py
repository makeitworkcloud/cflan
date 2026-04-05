#!/usr/bin/env python3
# steven@makeitwork.cloud
# https://github.com/welchworks/cflan/blob/main/set_dns.py
#
# To run as NetworkManager script, place in /etc/NetworkManager/disapatcher.d/
# Accepts two optional positional arguments: 1) the NIC interface name, 2) the action, i.e. "up"
#
# Requires two YAML variables to be set in vars.yaml or alternatively as sops encrypted values in sops_vars.yaml:
# cf_token - Cloudflare API Token with DNS edit permissions
# cf_domain_name - Name of the DNS Zone in Cloudflare, i.e. mydomain.com

import socket
import subprocess
import sys
from typing import Any

import CloudFlare
import netifaces
import yaml


def get_local_ip() -> str:
    """Get the local IP address."""
    local_ip_addr = ""
    try:
        local_ip_addr = socket.gethostbyname(socket.gethostname() + ".local")
    except Exception:
        local_ip_addr = socket.gethostbyname(socket.gethostname() + ".lan")
    else:
        local_ip_addr = socket.gethostbyname(socket.gethostname())
    return local_ip_addr


def validate_network_manager_args(local_ip_addr: str) -> None:
    """Validate NetworkManager arguments."""
    print("Parsing NetworkManager arguments...")
    try:
        if (
            netifaces.ifaddresses(sys.argv[1])[netifaces.AF_INET][0]["addr"]
            != local_ip_addr
        ):
            print("Failed!")
            sys.exit(
                "The IP address "
                + netifaces.ifaddresses(sys.argv[1])[netifaces.AF_INET][0]["addr"]
                + " for the interface "
                + sys.argv[1]
                + " is not the same as the primary IP address of "
                + local_ip_addr
                + " ."
            )
        if sys.argv[2] != "up":
            print("Failed!")
            sys.exit(
                "The NetworkManager action '"
                + sys.argv[2]
                + "' does not match the required action of 'up'."
            )
    except KeyError:
        print("Failed!")
        sys.exit("IP address for interface not set.")
    except ValueError:
        print("Failed!")
        sys.exit("Invalid NetworkManager interface value for this script.")
    except IndexError:
        print("NetworkManager argument(s) were not set. Proceeding...")


def get_yaml_vars() -> dict[str, Any]:
    """Get YAML variables from vars.yaml or sops_vars.yaml."""
    print("Getting unencrypted values from vars.yaml ...")
    try:
        with open("vars.yaml") as f:
            result: dict[str, Any] = yaml.safe_load(f.read())
            return result
    except Exception:
        print("Failed to get unencrypted values from vars.yaml ...")
        print("Getting sops encrypted values from sops_vars.yaml ...")
        try:
            r = subprocess.run(
                ["sops", "decrypt", "sops_vars.yaml"],
                capture_output=True,
            )
            if r.returncode != 0:
                print(r.stderr.decode("utf-8"))
                sys.exit("Failed getting sops values.")
        except FileNotFoundError:
            print("Failed!")
            sys.exit("sops must be installed and configured to use this script.")

        print("Getting YAML variables from sops output...")
        sops_result: dict[str, Any] = yaml.safe_load(r.stdout.decode("utf-8"))
        return sops_result


def get_zone_info(cf: CloudFlare.CloudFlare, domain_name: str) -> tuple[str, str]:
    """Get CloudFlare DNS Zone ID and Name."""
    print("Getting CloudFlare DNS Zone ID and Name...")
    zone_data = cf.zones.get(params={"per_page": "1", "name": domain_name})[0]
    return zone_data["id"], zone_data["name"]


def get_dns_record_id(
    cf: CloudFlare.CloudFlare, zone_id: str, hostname: str, zone_name: str
) -> str:
    """Get existing DNS record ID if it exists."""
    print(
        "Attempting to get existing DNS record for "
        + hostname
        + "."
        + zone_name
        + " ..."
    )
    try:
        records = cf.zones.dns_records.get(
            zone_id,
            params={
                "name": hostname + "." + zone_name,
                "match": "all",
                "type": "A",
            },
        )
        if records and len(records) > 0:
            record_id: str = records[0]["id"]
            return record_id
    except Exception:
        pass
    return ""


def create_dns_record(
    cf: CloudFlare.CloudFlare, zone_id: str, hostname: str, ip_addr: str
) -> None:
    """Create a new DNS record."""
    print("Record not found...")
    print("Creating new record for " + hostname + "...")
    try:
        cf.zones.dns_records.post(
            zone_id,
            data={"name": hostname, "type": "A", "content": ip_addr},
        )
    except CloudFlare.exceptions.CloudFlareAPIError as e:
        sys.exit(f"/zones.dns_records.post {e} - {e} {e}")
    print("Success!")


def update_dns_record(
    cf: CloudFlare.CloudFlare, zone_id: str, dns_id: str, hostname: str, ip_addr: str
) -> None:
    """Update existing DNS record with new IP."""
    print("Getting IP address for existing record...")
    dns_content = cf.zones.dns_records.get(
        zone_id,
        params={
            "name": hostname,
            "match": "all",
            "type": "A",
        },
    )[0]["content"]

    print("Evaluating if existing record matches current IP address...")
    if dns_content == ip_addr:
        print("Record matches, exiting...")
        sys.exit()

    print("Deleting existing record...")
    cf.zones.dns_records.delete(zone_id, dns_id)

    print("Creating new record for " + hostname + "...")
    try:
        cf.zones.dns_records.post(
            zone_id,
            data={"name": hostname, "type": "A", "content": ip_addr},
        )
    except CloudFlare.exceptions.CloudFlareAPIError as e:
        sys.exit(f"/zones.dns_records.post {e} - {e} {e}")

    print("Success!")


def set_dns() -> None:
    """Main function to set DNS records."""
    local_ip_addr = get_local_ip()

    print("Using IP address " + local_ip_addr + " ...")
    if "127.0.0" in local_ip_addr:
        print("Failed!")
        sys.exit("The IP address is a value for localhost.")

    validate_network_manager_args(local_ip_addr)

    yaml_vars = get_yaml_vars()

    print("Initiating CloudFlare object using API Token...")
    cf = CloudFlare.CloudFlare(token=yaml_vars["cf_token"])

    zone_id, zone_name = get_zone_info(cf, yaml_vars["cf_domain_name"])
    hostname = socket.gethostname()

    dns_id = get_dns_record_id(cf, zone_id, hostname, zone_name)

    if not dns_id:
        create_dns_record(cf, zone_id, hostname, local_ip_addr)
        sys.exit()
    else:
        update_dns_record(
            cf, zone_id, dns_id, hostname + "." + zone_name, local_ip_addr
        )


if __name__ == "__main__":
    set_dns()
