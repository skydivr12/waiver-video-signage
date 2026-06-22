#!/usr/bin/env python3

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
    BACKUP_DIR,
    STAGING_DIR,
    BACKUP_RETENTION,
    ADS_DIR,
    SHOWCASE_DIR,
    VIDEOS_DIR,
    UPDATE_LOCK_FILE,
    INSTALLED_VIDEO_NAME,
    CONVERT_COMMAND,
)

from logger import logger


def find_usb_device():

    result = subprocess.run(
        ["blkid"],
        capture_output=True,
        text=True
    )

    for line in result.stdout.splitlines():

        if 'TYPE="exfat"' in line:

            return line.split(":")[0]

    return None


def mount_usb(device):

    subprocess.run(
        [
            "mount",
            "-t",
            "exfat",
            device,
            USB_MOUNT_POINT
        ],
        check=True
    )


def unmount_usb():

    subprocess.run(
        [
            "umount",
            USB_MOUNT_POINT
        ],
        check=True
    )


def validate_key(root):

    key_file = (
        root / UPDATE_KEY_FILENAME
    )

    if not key_file.exists():

        raise RuntimeError(
            "Missing update key"
        )

    content = (
        key_file.read_text()
        .strip()
    )

    if content != UPDATE_KEY_CONTENT:

        raise RuntimeError(
            "Invalid update key"
        )


def validate_version(root):

    version_file = (
        root / UPDATE_VERSION_FILE
    )

    if not version_file.exists():

        raise RuntimeError(
            "Missing content_version.json"
        )

    with open(version_file) as f:

        json.load(f)


def validate_content(root):

    ads_dir = root / "ads"

    showcase_dir = root / "showcase"

    videos_dir = root / "videos"

    if not ads_dir.exists():
        raise RuntimeError(
            "Missing ads folder"
        )

    if not showcase_dir.exists():
        showcase_dir.mkdir(exist_ok=True)

    if not videos_dir.exists():

        raise RuntimeError(
            "Missing videos folder"
        )

    ads = []

    for item in ads_dir.iterdir():

        if item.suffix.lower() in (
            ".jpg",
            ".jpeg",
            ".png",   # comma was missing — Python was silently joining ".png" and ".mp4" into ".png.mp4"
            ".mp4",
            ".mov",
            ".mkv"
        ):

            ads.append(item)

    showcase_images = []

    for item in showcase_dir.iterdir():

        if item.suffix.lower() in (
            ".jpg",
            ".jpeg",
            ".png"
        ):

            showcase_images.append(item)

    videos = []

    for item in videos_dir.iterdir():

        if item.suffix.lower() in (
            ".mp4",
            ".mov",
            ".mkv"
        ):

            videos.append(item)

    if len(ads) < 1:

        raise RuntimeError(
            "No images found"
        )

    if len(videos) != 1:

        raise RuntimeError(
            f"Expected 1 video, found {len(videos)}"
        )

    return ads, showcase_images, videos


def create_backup():

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    backup_path = (
        BACKUP_DIR / timestamp
    )

    backup_path.mkdir(
        parents=True,
        exist_ok=True
    )

    shutil.copytree(
        ADS_DIR,
        backup_path / "ads"
    )

    shutil.copytree(
        SHOWCASE_DIR,
        backup_path / "showcase"
    )

    shutil.copytree(
        VIDEOS_DIR,
        backup_path / "videos"
    )

    print(
        f"Backup created: {backup_path}"
    )

    logger.info(
        f"Backup created: {backup_path}"
    )

    return backup_path


def cleanup_old_backups():

    backups = sorted(
        [
            item
            for item in BACKUP_DIR.iterdir()
            if item.is_dir()
        ]
    )

    while len(backups) > BACKUP_RETENTION:

        oldest = backups.pop(0)

        shutil.rmtree(oldest)

        print(
            f"Removed old backup: {oldest}"
        )

        logger.info(
            f"Removed old backup: {oldest}"
        )

def normalize_image(source, destination):

    logger.info(
        f"Normalizing image: {source.name}"
    )

    subprocess.run(
        [
            CONVERT_COMMAND,   # was "convert" — now uses the full path from config.py so it works even if ImageMagick isn't on PATH

            str(source),

            "-auto-orient",

            "-resize",
            "1920x1080>",

            "-strip",

            "-quality",
            "90",

            str(destination)
        ],
        check=True
    )

def stage_update(root):

    if STAGING_DIR.exists():

        shutil.rmtree(
            STAGING_DIR
        )

    STAGING_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    (STAGING_DIR / "ads").mkdir(
        parents=True,
        exist_ok=True
    )

    # showcase directory must be created before we try to copy files into it
    (STAGING_DIR / "showcase").mkdir(
        parents=True,
        exist_ok=True
    )

    for item in (root / "ads").iterdir():

        if not item.is_file():
            continue

        if item.suffix.lower() in (
            ".jpg",
            ".jpeg",
            ".png"
        ):

            normalize_image(
                item,
                STAGING_DIR / "ads" / item.name
            )

        elif item.suffix.lower() in (
            ".mp4",
            ".mov",
            ".mkv"
        ):

            shutil.copy2(
                item,
                STAGING_DIR / "ads" / item.name
            )

    for image in (root / "showcase").iterdir():

        if not image.is_file():
            continue

        # Only process supported image types — previously any stray file
        # (e.g. .DS_Store, .txt) would be passed to ImageMagick and cause a crash
        if image.suffix.lower() in (
            ".jpg",
            ".jpeg",
            ".png"
        ):

            normalize_image(
                image,
                STAGING_DIR / "showcase" / image.name
            )

    shutil.copytree(
        root / "videos",
        STAGING_DIR / "videos"
    )

    print(
        "Content copied to staging."
    )

    logger.info(
        "Content copied to staging."
    )

def validate_staging():

    ads_dir = STAGING_DIR / "ads"
    showcase_dir = STAGING_DIR / "showcase"
    videos_dir = STAGING_DIR / "videos"

    ads = []

    for item in ads_dir.iterdir():

        if item.suffix.lower() in (
            ".jpg",
            ".jpeg",
            ".png",   # same missing comma fix as validate_content above
            ".mp4",
            ".mov",
            ".mkv"
        ):

            ads.append(item)

    showcase = []

    for item in showcase_dir.iterdir():

        if item.suffix.lower() in (
            ".jpg",
            ".jpeg",
            ".png"
        ):

            showcase.append(item)

    videos = []

    for item in videos_dir.iterdir():

        if item.suffix.lower() in (
            ".mp4",
            ".mov",
            ".mkv"
        ):

            videos.append(item)

    if len(ads) < 1:

        raise RuntimeError(
            "Staging contains no images"
        )

    if len(videos) != 1:

        raise RuntimeError(
            f"Staging expected 1 video, found {len(videos)}"
        )

    ad_images = 0
    ad_videos = 0

    for item in ads:

        if item.suffix.lower() in (
            ".jpg",
            ".jpeg",
            ".png"
        ):
            ad_images += 1
        else:
            ad_videos += 1

    print(
        f"Staging validation OK "
        f"({ad_images} ad images, "
        f"{ad_videos} ad videos, "
        f"{len(showcase)} showcase)"
    )

    logger.info(
        f"Staging validation OK  ({ad_images} ad images, {ad_videos} ad videos, {len(showcase)} showcase)"
    )

def create_update_lock():

    UPDATE_LOCK_FILE.write_text(
        datetime.now().isoformat()
    )

    logger.info(
        "Update lock created"
    )

def remove_update_lock():

    if UPDATE_LOCK_FILE.exists():

        UPDATE_LOCK_FILE.unlink()

        logger.info(
            "Update lock removed"
        )

def install_update():

    if ADS_DIR.exists():
        shutil.rmtree(ADS_DIR)

    if SHOWCASE_DIR.exists():
        shutil.rmtree(SHOWCASE_DIR)

    if VIDEOS_DIR.exists():
        shutil.rmtree(VIDEOS_DIR)

    shutil.move(
        STAGING_DIR / "ads",
        ADS_DIR
    )

    shutil.move(
        STAGING_DIR / "showcase",
        SHOWCASE_DIR
    )

    VIDEOS_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    video = next(
        (STAGING_DIR / "videos").iterdir()
    )

    shutil.move(
        str(video),
        VIDEOS_DIR / INSTALLED_VIDEO_NAME
    )

    shutil.rmtree(
        STAGING_DIR,
        ignore_errors=True
    )

    logger.info(
        "Content installed"
    )

def reload_signage():

    IPCClient().send(
        "RELOAD_CONTENT"
    )

    logger.info(
        "Reload command sent"
    )

def main():

    device = find_usb_device()

    if not device:

        print(
            "No USB device found."
        )

        logger.info(
            "No USB device found."
        )
        return

    print(
        f"USB device: {device}"
    )

    logger.info(
        f"USB device: {device}"
    )

    mount_usb(device)

    try:

        root = Path(
            USB_MOUNT_POINT
        )

        validate_key(root)

        validate_version(root)

        ads, showcase_images, videos = validate_content(root)

        create_backup()

        cleanup_old_backups()

        stage_update(root)

        validate_staging()

        create_update_lock()

        try:

            install_update()

            reload_signage()

        finally:

            remove_update_lock()

        print(
            f"Ads found: {len(ads)}"
        )

        print(
            f"Showcase images found: {len(showcase_images)}"
        )


        print(
            f"Video found: {videos[0].name}"
        )

        print(
            "Update successful."
        )

        logger.info(
            f"Ads found: {len(ads)}"
        )

        logger.info(
            f"Showcase images found: {len(showcase_images)}"
        )

        logger.info(
            f"Video found: {videos[0].name}"
        )

        logger.info(
            "Update successful."
        )

    finally:

        try:
            unmount_usb()

        except Exception as e:

            logger.error(
                f"Unmount failed: {e}"
            )

if __name__ == "__main__":

    main()
