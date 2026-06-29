#!/usr/bin/env python3
import hashlib
import json
import subprocess
import shutil
from datetime import datetime
from pathlib import Path
from ipc import IPCClient
from config import (
    USB_MOUNT_POINT,
    UPDATE_KEY_FILENAME,
    UPDATE_KEY_CONTENT,
    UPDATE_VERSION_FILE,
    ADS_DIR,
    SHOWCASE_DIR,
    VIDEOS_DIR,
    UPDATE_LOCK_FILE,
    INSTALLED_VIDEO_NAME,
    CONVERT_COMMAND,
    FFMPEG_COMMAND,
    VIDEO_FRAMERATE,
    VIDEO_CRF,
)
from logger import logger

# Tracks which USB source files are installed and what their hash was.
# Lives next to the content dirs so everything stays in one place.
MANIFEST_FILE = ADS_DIR.parent / "installed_manifest.json"

AD_EXTENSIONS      = {".jpg", ".jpeg", ".png", ".mp4", ".mov", ".mkv"}
SHOWCASE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
VIDEO_EXTENSIONS   = {".mp4", ".mov", ".mkv"}
IMAGE_EXTENSIONS   = {".jpg", ".jpeg", ".png"}


# ---------------------------------------------------------------------------
# USB detection / mount
# ---------------------------------------------------------------------------

def find_mounted_update_drive():
    result = subprocess.run(
        ["lsblk", "-P", "-o", "NAME,RM,FSTYPE,MOUNTPOINT"],
        capture_output=True, text=True, check=True,
    )
    for line in result.stdout.splitlines():
        fields = {}
        for item in line.split():
            key, value = item.split("=", 1)
            fields[key] = value.strip('"')
        if (
            fields.get("RM") == "1"
            and fields.get("FSTYPE") == "exfat"
            and fields.get("MOUNTPOINT")
        ):
            return fields["NAME"], Path(fields["MOUNTPOINT"])
    return None


def find_exfat_device():
    result = subprocess.run(
        ["blkid"], capture_output=True, text=True, check=True
    )
    for line in result.stdout.splitlines():
        if 'TYPE="exfat"' in line:
            return line.split(":")[0]
    return None


def mount_usb():
    """
    Returns (root_path, mounted_here).
    mounted_here is True if we mounted it and should unmount when done.
    """
    mounted = find_mounted_update_drive()
    if mounted is not None:
        device, mountpoint = mounted
        logger.info(f"Using already-mounted USB: {device} at {mountpoint}")
        return mountpoint, False

    device = find_exfat_device()
    if device is None:
        raise RuntimeError("No exFAT update drive found.")

    Path(USB_MOUNT_POINT).mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["mount", "-t", "exfat", device, USB_MOUNT_POINT], check=True
    )
    logger.info(f"Mounted {device} at {USB_MOUNT_POINT}")
    return Path(USB_MOUNT_POINT), True


def unmount_usb(root):
    subprocess.run(["umount", str(root)], check=True)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_key(root):
    key_file = root / UPDATE_KEY_FILENAME
    if not key_file.exists():
        raise RuntimeError("Missing update key")
    if key_file.read_text().strip() != UPDATE_KEY_CONTENT:
        raise RuntimeError("Invalid update key")


def validate_version(root):
    version_file = root / UPDATE_VERSION_FILE
    if not version_file.exists():
        raise RuntimeError("Missing content_version.json")
    with open(version_file) as f:
        json.load(f)


def validate_content(root):
    """Basic sanity check on USB structure before we start syncing."""
    ads_dir     = root / "ads"
    videos_dir  = root / "videos"
    showcase_dir = root / "showcase"

    if not ads_dir.exists():
        raise RuntimeError("Missing ads folder")
    if not videos_dir.exists():
        raise RuntimeError("Missing videos folder")

    # showcase is optional — create it if absent so iteration is safe
    showcase_dir.mkdir(exist_ok=True)

    ad_media = [f for f in ads_dir.iterdir()
                if f.is_file() and f.suffix.lower() in AD_EXTENSIONS]
    videos   = [f for f in videos_dir.iterdir()
                if f.is_file() and f.suffix.lower() in VIDEO_EXTENSIONS]

    if not ad_media:
        raise RuntimeError("No ad media found")
    if len(videos) != 1:
        raise RuntimeError(f"Expected 1 video, found {len(videos)}")


# ---------------------------------------------------------------------------
# Hashing
# ---------------------------------------------------------------------------

def hash_file(path: Path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------

def normalize_image(source: Path, destination: Path):
    logger.info(f"Normalizing image: {source.name}")
    subprocess.run(
        [
            CONVERT_COMMAND,
            str(source),
            "-auto-orient",
            "-resize", "1280x1080>",   # 1920 caused 1440-wide images to be skipped by the Pi GPU
            "-strip",
            "-quality", "90",
            str(destination),
        ],
        check=True,
    )


def normalize_video(source: Path, destination: Path):
    """
    Re-encode to a true constant frame-rate h264 file.
    Variable / mismatched frame rates cause wrong-speed playback on the Pi
    (e.g. 28.95fps encoded as 30fps plays at half speed in VLC).
    Also significantly reduces bitrate with no visible quality loss at
    signage viewing distances.
    """
    logger.info(f"Normalizing video: {source.name}")
    subprocess.run(
        [
            FFMPEG_COMMAND,
            "-y",
            "-i", str(source),
            "-vf", f"fps={VIDEO_FRAMERATE}",
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", str(VIDEO_CRF),
            "-c:a", "aac",
            "-b:a", "192k",
            str(destination),
        ],
        check=True,
    )


def normalize_and_install(src: Path, dest: Path):
    dest.parent.mkdir(parents=True, exist_ok=True)
    if src.suffix.lower() in IMAGE_EXTENSIONS:
        normalize_image(src, dest)
    else:
        normalize_video(src, dest)


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------

def load_manifest() -> dict:
    if MANIFEST_FILE.exists():
        return json.loads(MANIFEST_FILE.read_text())
    return {}


def save_manifest(manifest: dict):
    MANIFEST_FILE.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_FILE.write_text(json.dumps(manifest, indent=2))


# ---------------------------------------------------------------------------
# Sync
# ---------------------------------------------------------------------------

def installed_path(rel: str) -> Path:
    """Map a USB-relative path (e.g. 'ads/foo.jpg') to its installed location."""
    subdir, filename = rel.split("/", 1)
    if subdir == "ads":
        return ADS_DIR / filename
    if subdir == "showcase":
        return SHOWCASE_DIR / filename
    if subdir == "videos":
        # All videos are installed under a single canonical name.
        return VIDEOS_DIR / INSTALLED_VIDEO_NAME
    raise ValueError(f"Unknown content subdirectory: {subdir}")


def get_usb_files(root: Path) -> dict:
    """
    Scan USB content directories and return:
        { relative_path: (absolute_path, md5_hash) }
    relative_path is e.g. 'ads/foo.jpg', 'videos/promo.mp4'
    """
    files = {}
    scan = [
        ("ads",      AD_EXTENSIONS),
        ("showcase", SHOWCASE_EXTENSIONS),
        ("videos",   VIDEO_EXTENSIONS),
    ]
    for subdir, exts in scan:
        src_dir = root / subdir
        if not src_dir.exists():
            continue
        for item in src_dir.iterdir():
            if item.is_file() and item.suffix.lower() in exts:
                rel = f"{subdir}/{item.name}"
                logger.info(f"Hashing {rel} ...")
                files[rel] = (item, hash_file(item))
    return files


def sync_content(root: Path) -> bool:
    """
    Sync USB content to installed dirs.
    Returns True if anything changed (caller should reload signage).
    """
    manifest  = load_manifest()
    usb_files = get_usb_files(root)

    to_install = {
        rel: (src, h)
        for rel, (src, h) in usb_files.items()
        if manifest.get(rel) != h
    }
    to_delete = [rel for rel in manifest if rel not in usb_files]

    if not to_install and not to_delete:
        logger.info("Content already up to date — nothing to do.")
        return False

    # Install new / changed files
    for rel, (src, src_hash) in to_install.items():
        dest = installed_path(rel)
        logger.info(f"Installing: {rel}")
        normalize_and_install(src, dest)

    # Delete files that were removed from the USB
    for rel in to_delete:
        dest = installed_path(rel)
        if dest.exists():
            dest.unlink()
            logger.info(f"Deleted: {rel}")

    # Persist updated manifest (USB source hashes, pre-normalization)
    save_manifest({rel: h for rel, (_, h) in usb_files.items()})

    logger.info(
        f"Sync complete — {len(to_install)} installed, {len(to_delete)} deleted."
    )
    return True


# ---------------------------------------------------------------------------
# Lock / reload
# ---------------------------------------------------------------------------

def create_update_lock():
    UPDATE_LOCK_FILE.write_text(datetime.now().isoformat())
    logger.info("Update lock created")


def remove_update_lock():
    if UPDATE_LOCK_FILE.exists():
        UPDATE_LOCK_FILE.unlink()
        logger.info("Update lock removed")


def reload_signage():
    IPCClient().send("RELOAD_CONTENT")
    logger.info("Reload command sent")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    root, mounted_here = mount_usb()
    try:
        validate_key(root)
        validate_version(root)
        validate_content(root)

        create_update_lock()
        try:
            changed = sync_content(root)
            if changed:
                reload_signage()
                logger.info("Update successful.")
            else:
                logger.info("No update needed.")
        finally:
            remove_update_lock()

    finally:
        if mounted_here:
            try:
                unmount_usb(root)
            except Exception as e:
                logger.warning(f"Could not unmount USB: {e}")


if __name__ == "__main__":
    main()
