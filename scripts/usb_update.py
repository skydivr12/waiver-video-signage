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
    FFMPEG_COMMAND,
    VIDEO_FRAMERATE,
    VIDEO_CRF,
)

from logger import logger


def find_mounted_update_drive():

    result = subprocess.run(
        [
            "lsblk",
            "-P",
            "-o",
            "NAME,RM,FSTYPE,MOUNTPOINT"
        ],
        capture_output=True,
        text=True,
        check=True
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

            return (
                fields["NAME"],
                Path(fields["MOUNTPOINT"])
            )

    return None


def find_exfat_device():

    result = subprocess.run(
        [
            "blkid"
        ],
        capture_output=True,
        text=True,
        check=True
    )

    for line in result.stdout.splitlines():

        if 'TYPE="exfat"' in line:

            return line.split(":")[0]

    return None

def mount_usb():
    """
    Returns:
        (root_path, mounted_here)

    root_path     - Path to the mounted update drive.
    mounted_here  - True if we mounted it ourselves and should unmount later.
                    False if the OS had already mounted it.
    """

    mounted = find_mounted_update_drive()

    if mounted is not None:

        device, mountpoint = mounted

        logger.info(
            f"Using already-mounted USB: {device} at {mountpoint}"
        )

        return mountpoint, False

    device = find_exfat_device()

    if device is None:
        raise RuntimeError(
            "No exFAT update drive found."
        )

    Path(USB_MOUNT_POINT).mkdir(
        parents=True,
        exist_ok=True
    )

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

    logger.info(
        f"Mounted {device} at {USB_MOUNT_POINT}"
    )

    return Path(USB_MOUNT_POINT), True

def unmount_usb(root):
    subprocess.run(
        [
            "umount",
            str(root)
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

    ad_media = []

    for item in ads_dir.iterdir():

        if item.suffix.lower() in (
            ".jpg",
            ".jpeg",
            ".png",
            ".mp4",
            ".mov",
            ".mkv"
        ):

            ad_media.append(item)

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

    if len(ad_media) < 1:

        raise RuntimeError(
            "No ad media found"
        )

    if len(videos) != 1:

        raise RuntimeError(
            f"Expected 1 video, found {len(videos)}"
        )

    return ad_media, showcase_images, videos


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
            CONVERT_COMMAND,    # full path from config — works even if convert is not on PATH

            str(source),

            "-auto-orient",

            "-resize",
            "1280x1080>",       # 1920 caused 1440-wide images to be skipped by the Pi GPU

            "-strip",

            "-quality",
            "90",

            str(destination)
        ],
        check=True
    )


def normalize_video(source, destination):
    """
    Re-encode a video to a clean constant 30fps h264 file.

    Source videos with variable or mismatched frame rates play at the wrong
    speed on the Pi (e.g. a 28.95fps video encoded as 30fps plays at half
    speed in VLC). Re-encoding to a true constant frame rate fixes this.

    Also reduces bitrate significantly — the original 17Mbps source became
    ~5Mbps after re-encoding with no visible quality loss at signage viewing
    distances.
    """

    logger.info(
        f"Normalizing video: {source.name}"
    )

    subprocess.run(
        [
            FFMPEG_COMMAND,

            "-y",               # overwrite output without asking

            "-i",
            str(source),

            "-vf",
            f"fps={VIDEO_FRAMERATE}",   # force constant frame rate

            "-c:v",
            "libx264",

            "-preset",
            "fast",             # faster encode, slightly larger file than 'medium'

            "-crf",
            str(VIDEO_CRF),     # quality level — 23 is ffmpeg default

            "-c:a",
            "aac",

            "-b:a",
            "192k",

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

            # Normalise rather than copy — fixes variable frame rate issues
            # that cause videos to play at wrong speed on the Pi
            normalize_video(
                item,
                STAGING_DIR / "ads" / item.name
            )

    for image in (root / "showcase").iterdir():

        if image.is_file():

            normalize_image(
                image,
                STAGING_DIR / "showcase" / image.name
            )

    # Normalise the instructional video rather than copying it raw
    (STAGING_DIR / "videos").mkdir(parents=True, exist_ok=True)

    for item in (root / "videos").iterdir():

        if item.is_file() and item.suffix.lower() in (
            ".mp4",
            ".mov",
            ".mkv"
        ):

            normalize_video(
                item,
                STAGING_DIR / "videos" / item.name
            )

    print(STAGING_DIR)
    print(STAGING_DIR.exists())
    print(list(STAGING_DIR.iterdir()))

    print(
        "Content copied to staging."
    )

    logger.info(
        "Content copied to staging."
    )

def validate_staging():

    print("validate_staging()")
    print(STAGING_DIR)
    print(STAGING_DIR.exists())

    ads_dir = STAGING_DIR / "ads"
    showcase_dir = STAGING_DIR / "showcase"
    videos_dir = STAGING_DIR / "videos"

    ad_media = []

    for item in ads_dir.iterdir():

        if item.suffix.lower() in (
            ".jpg",
            ".jpeg",
            ".png",
            ".mp4",
            ".mov",
            ".mkv"
        ):

            ad_media.append(item)

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

    if len(ad_media) < 1:

        raise RuntimeError(
            "Staging contains no ad media"
        )

    if len(videos) != 1:

        raise RuntimeError(
            f"Staging expected 1 video, found {len(videos)}"
        )

    ad_images = 0
    ad_videos = 0

    for item in ad_media:

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

    root, mounted_here = mount_usb()

    try:

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

        print(f"Ads found: {len(ads)}")
        print(f"Showcase images found: {len(showcase_images)}")
        print(f"Video found: {videos[0].name}")
        print("Update successful.")

        logger.info(f"Ads found: {len(ads)}")
        logger.info(f"Showcase images found: {len(showcase_images)}")
        logger.info(f"Video found: {videos[0].name}")
        logger.info("Update successful.")

    finally:

        if mounted_here:

            try:

                unmount_usb(root)

            except Exception as e:

                logger.warning(
                    f"Could not unmount USB: {e}"
                )

if __name__ == "__main__":

    main()
