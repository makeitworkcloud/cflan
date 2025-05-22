#!/usr/bin/env python3
# steven@makeitwork.cloud
# https://github.com/welchworks/cflan/blob/main/setup.py
# setup.py - Creates NetworkManager dispatcher script

import os
import sys
import shutil

if os.getuid() != 0:
    sys.exit("Must run as root")

print("Deploying NetworkManager script...")
shutil.copyfile("set_dns.py", "/etc/NetworkManager/dispatcher.d/set_dns")
os.chown("/etc/NetworkManager/dispatcher.d/set_dns", 0, 0)
os.chmod("/etc/NetworkManager/dispatcher.d/set_dns", 0o700)

print("Attempting to deploy vars.yaml ...")
try:
    shutil.copyfile("vars.yaml", "/vars.yaml")
    os.chown("/vars.yaml", 0, 0)
    os.chmod("/vars.yaml", 0o600)
except Exception:
    print("Could not deploy vars.yaml ...")
    print("Deploying sops_vars.yaml ...")
    print(
        "Ensure that the sops environment & encryption standards are setup for root..."
    )
    shutil.copyfile("sops_vars.yaml", "/sops_vars.yaml")
    os.chown("/sops_vars.yaml", 0, 0)
    os.chmod("/sops_vars.yaml", 0o600)

print("Success!")
