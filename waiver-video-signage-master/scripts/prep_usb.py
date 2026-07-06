#!/usr/bin/env python3
"""
prep_usb.py — Prepare a USB drive for signage content updates.

Detects removable USB drives, optionally formats one as exFAT, then
creates the required folder structure and update key so the drive is
ready to receive content.

Usage:
    sudo python3 /opt/signage/scripts/prep_usb.py
"""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import (
    UPDATE_KEY_FILENAME,
    UPDATE_KEY_CONTENT,
    UPDATE_VERSION_FILE,
    USB_MOUNT_POINT,
)

# ---------------------------------------------------------------------------
# Colour helpers
# ---------------------------------------------------------------------------

RED    = '\033[0;31m'
GREEN  = '\033[0;32m'
YELLOW = '\033[1;33m'
BLUE   = '\033[0;34m'
BOLD   = '\033[1m'
NC     = '\033[0m'

def info(msg):    print(f"{BLUE}[INFO]{NC}  {msg}")
def success(msg): print(f"{GREEN}[OK]{NC}    {msg}")
def warn(msg):    print(f"{YELLOW}[WARN]{NC}  {msg}")
def error(msg):   print(f"{RED}[ERROR]{NC} {msg}"); sys.exit(1)
def header(msg):  print(f"\n{BOLD}--- {msg} ---{NC}")


# ---------------------------------------------------------------------------
# Drive detection
# ---------------------------------------------------------------------------

def lsblk_fields():
    """Return list of dicts, one per block device line from lsblk."""
    result = subprocess.run(
        ["lsblk", "-P", "-o", "NAME,RM,TYPE,SIZE,FSTYPE,LABEL,MOUNTPOINT"],
        capture_output=True, text=True, check=True,
    )
    rows = []
    for line in result.stdout.splitlines():
        fields = {}
        for token in line.split():
            k, _, v = token.partition("=")
            fields[k] = v.strip('"')
        rows.append(fields)
    return rows


def find_removable_drives():
    """
    Return two lists: (partitions, bare_disks).
    partitions  — removable devices of TYPE=part (already partitioned)
    bare_disks  — removable devices of TYPE=disk with no child partitions detected
    """
    rows = lsblk_fields()
    removable = [r for r in rows if r.get("RM") == "1"]

    # Names of disks that have at least one partition child
    disk_names_with_parts = set()
    for r in removable:
        if r.get("TYPE") == "part":
            # e.g. sda1 → parent disk is sda
            disk_names_with_parts.add(r["NAME"].rstrip("0123456789"))

    partitions = [r for r in removable if r.get("TYPE") == "part"]
    bare_disks = [
        r for r in removable
        if r.get("TYPE") == "disk" and r["NAME"] not in disk_names_with_parts
    ]
    return partitions, bare_disks


def device_path(name):
    return f"/dev/{name}"


def choose_device(partitions, bare_disks):
    """
    Let the user pick which device to prepare.
    Returns (device_path, needs_format).
    needs_format is True if the device has no exFAT filesystem yet.
    """
    candidates = []

    for p in partitions:
        candidates.append({
            "dev":    device_path(p["NAME"]),
            "size":   p.get("SIZE", "?"),
            "fstype": p.get("FSTYPE", ""),
            "label":  p.get("LABEL", ""),
            "mount":  p.get("MOUNTPOINT", ""),
            "format": p.get("FSTYPE", "") != "exfat",
        })

    for d in bare_disks:
        candidates.append({
            "dev":    device_path(d["NAME"]),
            "size":   d.get("SIZE", "?"),
            "fstype": "none",
            "label":  d.get("LABEL", ""),
            "mount":  "",
            "format": True,
        })

    if not candidates:
        error(
            "No removable USB drive detected.\n"
            "  Make sure the drive is plugged in and recognised by the Pi,\n"
            "  then run this script again."
        )

    print()
    print(f"{BOLD}Removable drives found:{NC}")
    for i, c in enumerate(candidates, 1):
        fs_note = c["fstype"] if c["fstype"] else "unknown"
        fmt_note = f"{YELLOW}will format as exFAT{NC}" if c["format"] else f"{GREEN}exFAT — ready{NC}"
        print(f"  [{i}] {c['dev']}  {c['size']}  fs={fs_note}  {fmt_note}")

    print()
    if len(candidates) == 1:
        choice = input("Press Enter to use the drive above, or Ctrl-C to cancel: ").strip()
        return candidates[0]
    else:
        while True:
            choice = input(f"Select drive [1-{len(candidates)}]: ").strip()
            if choice.isdigit() and 1 <= int(choice) <= len(candidates):
                return candidates[int(choice) - 1]
            print("  Invalid selection — try again.")


# ---------------------------------------------------------------------------
# Format
# ---------------------------------------------------------------------------

def format_exfat(dev, label="SIGNAGE_USB"):
    warn(f"About to format {dev} as exFAT — ALL DATA ON THE DRIVE WILL BE LOST.")
    confirm = input("  Type YES to confirm: ").strip()
    if confirm != "YES":
        error("Format cancelled.")
    info(f"Formatting {dev} as exFAT...")
    subprocess.run(["mkfs.exfat", "-n", label, dev], check=True)
    success(f"Formatted {dev} as exFAT (label: {label})")


# ---------------------------------------------------------------------------
# Mount / unmount
# ---------------------------------------------------------------------------

def mount_device(dev):
    """Mount dev at USB_MOUNT_POINT. Returns (mount_path, mounted_by_us)."""
    # Check if already mounted somewhere
    result = subprocess.run(
        ["lsblk", "-P", "-o", "NAME,MOUNTPOINT"],
        capture_output=True, text=True, check=True,
    )
    for line in result.stdout.splitlines():
        fields = {}
        for token in line.split():
            k, _, v = token.partition("=")
            fields[k] = v.strip('"')
        if device_path(fields.get("NAME", "")) == dev and fields.get("MOUNTPOINT"):
            info(f"{dev} is already mounted at {fields['MOUNTPOINT']}")
            return Path(fields["MOUNTPOINT"]), False

    mount_point = Path(USB_MOUNT_POINT)
    mount_point.mkdir(parents=True, exist_ok=True)
    subprocess.run(["mount", "-t", "exfat", dev, str(mount_point)], check=True)
    info(f"Mounted {dev} at {mount_point}")
    return mount_point, True


def unmount_device(mount_point):
    subprocess.run(["umount", str(mount_point)], check=True)
    info(f"Unmounted {mount_point}")


# ---------------------------------------------------------------------------
# Create structure
# ---------------------------------------------------------------------------

def create_structure(root: Path):
    header("Creating folder structure")

    # Directories
    for folder in ["ads", "showcase", "videos"]:
        d = root / folder
        d.mkdir(exist_ok=True)
        success(f"Created: {folder}/")

    # Update key
    key_file = root / UPDATE_KEY_FILENAME
    key_file.write_text(UPDATE_KEY_CONTENT)
    success(f"Created: {UPDATE_KEY_FILENAME}  (content: {UPDATE_KEY_CONTENT})")

    # content_version.json
    version_data = {
        "version": "1.0",
        "created": datetime.now().isoformat(),
        "description": "Signage content",
    }
    version_file = root / UPDATE_VERSION_FILE
    version_file.write_text(json.dumps(version_data, indent=4))
    success(f"Created: {UPDATE_VERSION_FILE}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if os.geteuid() != 0:
        error("This script must be run as root.  Try: sudo python3 prep_usb.py")

    print()
    print(f"{BOLD}============================================={NC}")
    print(f"{BOLD}  Signage USB Drive Preparation             {NC}")
    print(f"{BOLD}============================================={NC}")

    header("Detecting removable drives")
    partitions, bare_disks = find_removable_drives()
    candidate = choose_device(partitions, bare_disks)

    dev = candidate["dev"]

    # Format if needed
    if candidate["format"]:
        format_exfat(dev)
    else:
        info(f"{dev} is already exFAT — skipping format")

    # Mount
    header("Mounting drive")
    mount_path, mounted_by_us = mount_device(dev)

    try:
        create_structure(mount_path)
    finally:
        if mounted_by_us:
            header("Unmounting drive")
            unmount_device(mount_path)

    print()
    print(f"{BOLD}============================================={NC}")
    print(f"{BOLD}  USB Drive Ready{NC}")
    print(f"{BOLD}============================================={NC}")
    print()
    print("  The drive now contains:")
    print(f"    {GREEN}✓{NC} ads/               — copy ad images and videos here")
    print(f"    {GREEN}✓{NC} showcase/          — copy showcase images here (optional)")
    print(f"    {GREEN}✓{NC} videos/            — copy exactly 1 instructional video here")
    print(f"    {GREEN}✓{NC} {UPDATE_KEY_FILENAME}")
    print(f"    {GREEN}✓{NC} {UPDATE_VERSION_FILE}")
    print()
    print("  Next steps:")
    print("  1. Copy your content into the folders above")
    print("  2. Safely eject the drive")
    print("  3. Insert it into the signage Pi — the update runs automatically")
    print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nCancelled.")
        sys.exit(0)
