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
import CloudFlare
import sys
import yaml
import subprocess
import netifaces

local_ip_addr = ""
try:
    local_ip_addr = socket.gethostbyname(socket.gethostname() + ".local")
except Exception:
    local_ip_addr = socket.gethostbyname(socket.gethostname() + ".lan")
else:
    local_ip_addr = socket.gethostbyname(socket.gethostname())

print("Using IP address " + local_ip_addr + " ...")
if "127.0.0" in local_ip_addr:
    print("Failed!")
    sys.exit("The IP address is a value for localhost.")

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

print("Getting unencrypted values from vars.yaml ...")
try:
    f = open("vars.yaml", "r")
    yaml_vars = yaml.safe_load(f.read())
except Exception:
    print("Failed to get unencrypted values from vars.yaml ...")
    print("Getting sops encrypted values from sops_vars.yaml ...")
    try:
        r = subprocess.run(
            ["sops", "decrypt", "sops_vars.yaml"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if r.returncode != 0:
            print(r.stderr.decode("utf-8"))
            sys.exit("Failed getting sops values.")
    except FileNotFoundError:
        print("Failed!")
        sys.exit("sops must be installed and configured to use this script.")

    print("Getting YAML variables from sops output...")
    yaml_vars = yaml.safe_load(r.stdout.decode("utf-8"))

print("Initiating CloudFlare object using API Token...")
cf = CloudFlare.CloudFlare(token=yaml_vars["cf_token"])

print("Getting CloudFlare DNS Zone ID and Name...")
zone_id = cf.zones.get(params={"per_page": "1", "name": yaml_vars["cf_domain_name"]})[
    0
]["id"]
zone_name = cf.zones.get(params={"per_page": "1", "name": yaml_vars["cf_domain_name"]})[
    0
]["name"]

print(
    "Attempting to get existing DNS record for "
    + socket.gethostname()
    + "."
    + yaml_vars["cf_domain_name"]
    + " ..."
)
try:
    dns_id = cf.zones.dns_records.get(
        zone_id,
        params={
            "name": socket.gethostname() + "." + zone_name,
            "match": "all",
            "type": "A",
        },
    )[0]["id"]
except Exception:
    print("Record not found...")
    print(
        "Creating new record for "
        + socket.gethostname()
        + "."
        + yaml_vars["cf_domain_name"]
        + " ..."
    )
    try:
        cf.zones.dns_records.post(
            zone_id,
            data={"name": socket.gethostname(), "type": "A", "content": local_ip_addr},
        )
    except CloudFlare.exceptions.CloudFlareAPIError as e:
        sys.exit("/zones.dns_records.post %s - %d %s" % (e, e, e))
    print("Success!")
    sys.exit()

print("Getting IP address for existing record...")
dns_content = cf.zones.dns_records.get(
    zone_id,
    params={
        "name": socket.gethostname() + "." + zone_name,
        "match": "all",
        "type": "A",
    },
)[0]["content"]

print("Evaluating if existing record matches current IP address...")
if dns_content == local_ip_addr:
    print("Record matches, exiting...")
    sys.exit()

print("Deleting existing record...")
cf.zones.dns_records.delete(zone_id, dns_id)

print(
    "Creating new record for "
    + socket.gethostname()
    + "."
    + yaml_vars["cf_domain_name"]
    + " ..."
)
try:
    cf.zones.dns_records.post(
        zone_id,
        data={"name": socket.gethostname(), "type": "A", "content": local_ip_addr},
    )
except CloudFlare.exceptions.CloudFlareAPIError as e:
    sys.exit("/zones.dns_records.post %s - %d %s" % (e, e, e))

print("Success!")
