#!/usr/bin/env python3
"""Install the cflan NetworkManager dispatcher script and root-volume config."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

DISPATCHER_PATH = Path("/etc/NetworkManager/dispatcher.d/set_dns")
CONFIG_FILES: tuple[tuple[str, str], ...] = (
    ("cflan_vars.yaml", "/cflan_vars.yaml"),
    ("cflan_sops_vars.yaml", "/cflan_sops_vars.yaml"),
    # Legacy root-volume aliases remain supported for the existing installation.
    ("vars.yaml", "/vars.yaml"),
    ("sops_vars.yaml", "/sops_vars.yaml"),
)


def install() -> None:
    """Install only files supplied by the operator; never create configuration values."""
    if os.getuid() != 0:
        sys.exit("Error: Must run as root")

    script_dir = Path(__file__).resolve().parent
    if not DISPATCHER_PATH.parent.is_dir():
        sys.exit(
            f"Error: NetworkManager dispatcher directory is missing: {DISPATCHER_PATH.parent}"
        )

    print("Deploying NetworkManager dispatcher script...")
    shutil.copyfile(script_dir / "set_dns.py", DISPATCHER_PATH)
    os.chown(DISPATCHER_PATH, 0, 0)
    os.chmod(DISPATCHER_PATH, 0o700)
    print(f"  Installed: {DISPATCHER_PATH}")

    print("\nDeploying configuration...")
    for source_name, target_name in CONFIG_FILES:
        source_path = script_dir / source_name
        if not source_path.is_file():
            continue

        target_path = Path(target_name)
        shutil.copyfile(source_path, target_path)
        os.chown(target_path, 0, 0)
        os.chmod(target_path, 0o600)
        print(f"  Installed: {target_path}")
        if source_name.startswith("cflan_"):
            print(
                "  Using the preferred cflan-prefixed root-volume configuration name."
            )
        if source_name in {"cflan_sops_vars.yaml", "sops_vars.yaml"}:
            print("  Note: Ensure SOPS is configured for the root user.")
        break
    else:
        print("  Warning: No configuration file found.")
        print(
            "  Expected cflan_vars.yaml or cflan_sops_vars.yaml; legacy aliases remain valid."
        )

    print("\nInstallation complete!")
    print("Configuration remains root-owned on the root/volume area.")


if __name__ == "__main__":
    install()
