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
    IMAGES_DIR,
    VIDEOS_DIR,
    UPDATE_LOCK_FILE,
    INSTALLED_VIDEO_NAME,
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

    images_dir = root / "images"

    videos_dir = root / "videos"

    if not images_dir.exists():

        raise RuntimeError(
            "Missing images folder"
        )

    if not videos_dir.exists():

        raise RuntimeError(
            "Missing videos folder"
        )

    images = []

    for item in images_dir.iterdir():

        if item.suffix.lower() in (
            ".jpg",
            ".jpeg",
            ".png"
        ):

            images.append(item)

    videos = []

    for item in videos_dir.iterdir():

        if item.suffix.lower() in (
            ".mp4",
            ".mov",
            ".mkv"
        ):

            videos.append(item)

    if len(images) < 1:

        raise RuntimeError(
            "No images found"
        )

    if len(videos) != 1:

        raise RuntimeError(
            f"Expected 1 video, found {len(videos)}"
        )

    return images, videos


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
        IMAGES_DIR,
        backup_path / "images"
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

def stage_update(root):

    if STAGING_DIR.exists():

        shutil.rmtree(
            STAGING_DIR
        )

    STAGING_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    shutil.copytree(
        root / "images",
        STAGING_DIR / "images"
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

    images_dir = (
        STAGING_DIR / "images"
    )

    videos_dir = (
        STAGING_DIR / "videos"
    )

    images = []

    for item in images_dir.iterdir():

        if item.suffix.lower() in (
            ".jpg",
            ".jpeg",
            ".png"
        ):

            images.append(item)

    videos = []

    for item in videos_dir.iterdir():

        if item.suffix.lower() in (
            ".mp4",
            ".mov",
            ".mkv"
        ):

            videos.append(item)

    if len(images) < 1:

        raise RuntimeError(
            "Staging contains no images"
        )

    if len(videos) != 1:

        raise RuntimeError(
            f"Staging expected 1 video, found {len(videos)}"
        )

    print(
        f"Staging validation OK ({len(images)} images)"
    )

    logger.info(
        f"Staging validation OK ({len(images)} images)"
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

    shutil.rmtree(IMAGES_DIR)
    shutil.rmtree(VIDEOS_DIR)

    shutil.move(
        STAGING_DIR / "images",
        IMAGES_DIR
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

        images, videos = validate_content(root)

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
            f"Images found: {len(images)}"
        )

        print(
            f"Video found: {videos[0].name}"
        )

        print(
            "Update successful."
        )

        logger.info(
            f"Images found: {len(images)}"
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
