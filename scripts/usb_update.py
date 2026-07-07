#!/usr/bin/env python3
import hashlib
import json
import shutil
import subprocess
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
    PREVIOUS_DIR,
    MANIFEST_FILE,
    UPDATE_LOCK_FILE,
    CONVERT_COMMAND,
    FFMPEG_COMMAND,
    VIDEO_FRAMERATE,
    VIDEO_CRF,
)
from logger import logger

AD_EXTENSIONS       = {".jpg", ".jpeg", ".png", ".mp4", ".mov", ".mkv"}
SHOWCASE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
VIDEO_EXTENSIONS    = {".mp4", ".mov", ".mkv"}
IMAGE_EXTENSIONS    = {".jpg", ".jpeg", ".png"}


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
        try:
            json.load(f)
        except json.JSONDecodeError as e:
            raise RuntimeError(
                f"content_version.json is not valid JSON ({e}). "
                f"Re-create the USB drive with prep_usb.py rather than "
                f"hand-creating this file."
            ) from e


def validate_content(root):
    """Basic sanity check on USB structure before we start syncing."""
    ads_dir      = root / "ads"
    videos_dir   = root / "videos"
    showcase_dir = root / "showcase"

    if not ads_dir.exists():
        raise RuntimeError("Missing ads folder")
    if not videos_dir.exists():
        raise RuntimeError("Missing videos folder")

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
            "-resize", "1280x1080>",
            "-strip",
            "-quality", "90",
            str(destination),
        ],
        check=True,
    )


def normalize_video(source: Path, destination: Path):
    """
    Re-encode to a true constant frame-rate h264 file.
    Variable / mismatched frame rates cause wrong-speed playback on the Pi.
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


def verify_manifest_integrity(manifest: dict):
    """Remove entries where the installed file is missing so they get reinstalled."""
    missing = [rel for rel in list(manifest) if not installed_path(rel).exists()]
    for rel in missing:
        logger.warning(f"Manifest entry missing on disk, will reinstall: {rel}")
        del manifest[rel]


# ---------------------------------------------------------------------------
# Snapshot
# ---------------------------------------------------------------------------

def save_snapshot():
    """
    Save the current installed content to PREVIOUS_DIR before applying an
    update. This gives the rollback button something to restore to.
    Only snapshots if there is content to save.
    """
    if not ADS_DIR.exists():
        return
    logger.info("Saving snapshot of current content...")
    if PREVIOUS_DIR.exists():
        shutil.rmtree(PREVIOUS_DIR)
    PREVIOUS_DIR.mkdir(parents=True, exist_ok=True)
    for src, name in [(ADS_DIR, "ads"), (SHOWCASE_DIR, "showcase"), (VIDEOS_DIR, "videos")]:
        if src.exists():
            shutil.copytree(src, PREVIOUS_DIR / name)
    if MANIFEST_FILE.exists():
        shutil.copy2(MANIFEST_FILE, PREVIOUS_DIR / "manifest.json")
    logger.info("Snapshot saved.")


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
        return VIDEOS_DIR / filename
    raise ValueError(f"Unknown content subdirectory: {subdir}")


def get_usb_files(root: Path) -> dict:
    """
    Scan USB content directories and return:
        { relative_path: (absolute_path, md5_hash) }
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
    manifest = load_manifest()
    verify_manifest_integrity(manifest)
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

    # Snapshot current content before making any changes
    save_snapshot()

    # Install new / changed files
    for rel, (src, src_hash) in to_install.items():
        dest = installed_path(rel)
        logger.info(f"Installing: {rel}")
        normalize_and_install(src, dest)

    # Delete files removed from USB — but skip if the destination was just
    # reinstalled by a different source filename (e.g. video renamed on USB
    # but still maps to the same instruction.mp4 on disk)
    freshly_installed = {installed_path(rel) for rel in to_install}
    for rel in to_delete:
        dest = installed_path(rel)
        if dest in freshly_installed:
            logger.info(f"Skipping delete of {rel} — destination was just reinstalled")
            continue
        if dest.exists():
            dest.unlink()
            logger.info(f"Deleted: {rel}")

    save_manifest({rel: h for rel, (_, h) in usb_files.items()})
    logger.info(f"Sync complete — {len(to_install)} installed, {len(to_delete)} deleted.")
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
