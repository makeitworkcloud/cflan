#!/usr/bin/env python3
"""Install script for cflan - NetworkManager dispatcher setup."""

import os
import shutil
import sys


def install() -> None:
    """Deploy NetworkManager dispatcher script and configuration files."""
    if os.getuid() != 0:
        sys.exit("Error: Must run as root")

    script_dir = os.path.dirname(os.path.abspath(__file__))

    print("Deploying NetworkManager dispatcher script...")
    dispatcher_path = "/etc/NetworkManager/dispatcher.d/set_dns"
    shutil.copyfile(os.path.join(script_dir, "set_dns.py"), dispatcher_path)
    os.chown(dispatcher_path, 0, 0)
    os.chmod(dispatcher_path, 0o700)
    print(f"  Installed: {dispatcher_path}")

    print("\nDeploying configuration...")
    config_deployed = False

    # Try unencrypted config first
    vars_path = os.path.join(script_dir, "vars.yaml")
    if os.path.exists(vars_path):
        target_path = "/vars.yaml"
        shutil.copyfile(vars_path, target_path)
        os.chown(target_path, 0, 0)
        os.chmod(target_path, 0o600)
        print(f"  Installed: {target_path}")
        config_deployed = True

    # Fall back to sops encrypted config
    sops_path = os.path.join(script_dir, "sops_vars.yaml")
    if not config_deployed and os.path.exists(sops_path):
        target_path = "/sops_vars.yaml"
        shutil.copyfile(sops_path, target_path)
        os.chown(target_path, 0, 0)
        os.chmod(target_path, 0o600)
        print(f"  Installed: {target_path}")
        print("  Note: Ensure SOPS is configured for root user")
        config_deployed = True

    if not config_deployed:
        print("  Warning: No configuration file found (vars.yaml or sops_vars.yaml)")
        print("  Create one before running the script!")

    print("\nInstallation complete!")
    print("\nNext steps:")
    print("1. Verify your configuration in /vars.yaml or /sops_vars.yaml")
    print("2. Test with: sudo /etc/NetworkManager/dispatcher.d/set_dns eth0 up")


if __name__ == "__main__":
    install()
