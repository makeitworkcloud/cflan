#!/usr/bin/env python3
"""Install the cflan NetworkManager dispatcher script and root-volume config."""

from __future__ import annotations

import os
import shutil
import sys
from collections.abc import Sequence
from pathlib import Path

DISPATCHER_PATH = Path("/etc/NetworkManager/dispatcher.d/set_dns")
CONFIG_FILES: tuple[tuple[str, str], ...] = (
    ("cflan_vars.yaml", "/cflan_vars.yaml"),
    ("cflan_sops_vars.yaml", "/cflan_sops_vars.yaml"),
    # Legacy root-volume aliases remain supported for the existing installation.
    ("vars.yaml", "/vars.yaml"),
    ("sops_vars.yaml", "/sops_vars.yaml"),
)


def install(
    source_dir: Path | None = None,
    dispatcher_path: Path = DISPATCHER_PATH,
    config_files: Sequence[tuple[str, str]] = CONFIG_FILES,
) -> None:
    """Install only files supplied by the operator; never create configuration values."""
    if os.getuid() != 0:
        sys.exit("Error: Must run as root")

    source_root = Path(__file__).resolve().parent if source_dir is None else source_dir
    if not dispatcher_path.parent.is_dir():
        sys.exit(
            f"Error: NetworkManager dispatcher directory is missing: {dispatcher_path.parent}"
        )

    print("Deploying NetworkManager dispatcher script...")
    shutil.copyfile(source_root / "set_dns.py", dispatcher_path)
    os.chown(dispatcher_path, 0, 0)
    os.chmod(dispatcher_path, 0o700)
    print(f"  Installed: {dispatcher_path}")

    print("\nDeploying configuration...")
    for source_name, target_name in config_files:
        source_path = source_root / source_name
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
