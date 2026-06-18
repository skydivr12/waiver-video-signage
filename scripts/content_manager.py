#!/usr/bin/env python3

"""
content_manager.py

Responsible for:

- Discovering content
- Validating content
- Building playlists
- Writing metadata
"""

import json

from datetime import datetime

from config import (
    PLAYLIST_FILE,
    ADS_DIR,
    SHOWCASE_DIR,
    VIDEOS_DIR,
    CONTENT_VERSION_FILE,
    SUPPORTED_IMAGES,
    SUPPORTED_VIDEOS,
    MIN_IMAGE_COUNT,
    MAX_VIDEO_COUNT,
)

from logger import logger


def write_playlist():

    ads = discover_ads()

    with open(
        PLAYLIST_FILE,
        "w"
    ) as f:

        for image in ads:

            f.write(
                f"{image}\n"
            )

    logger.info(
        f"Playlist updated with {len(ads)} ad image(s)"
    )


def discover_ads():
    """
    Return alphabetically sorted image list.
    """

    images = []

    for item in ADS_DIR.iterdir():

        if not item.is_file():
            continue

        if item.suffix.lower() in SUPPORTED_IMAGES:
            images.append(item)

    images.sort(
        key=lambda p: p.name.lower()
    )

    return images


def discover_showcase():
    """
    Return alphabetically sorted image list.
    """

    images = []

    for item in SHOWCASE_DIR.iterdir():

        if not item.is_file():
            continue

        if item.suffix.lower() in SUPPORTED_IMAGES:
            images.append(item)

    images.sort(
        key=lambda p: p.name.lower()
    )

    return images


def discover_videos():
    """
    Return all valid video files.
    """

    videos = []

    for item in VIDEOS_DIR.iterdir():

        if not item.is_file():
            continue

        if item.suffix.lower() in SUPPORTED_VIDEOS:
            videos.append(item)

    videos.sort(
        key=lambda p: p.name.lower()
    )

    return videos


def discover_video():
    """
    Return the single instructional video.
    """

    videos = discover_videos()

    if len(videos) != 1:
        return None

    return videos[0]


def get_video():

    video = discover_video()

    if video is None:

        raise RuntimeError(
            "No valid instructional video"
        )

    return str(video)


def validate_content():
    """
    Validate currently installed content.
    """

    ads = discover_ads()

    if len(ads) < MIN_IMAGE_COUNT:

        return (
            False,
            f"Need at least {MIN_IMAGE_COUNT} ad image(s)"
        )

    videos = discover_videos()

    if len(videos) != MAX_VIDEO_COUNT:

        return (
            False,
            f"Expected {MAX_VIDEO_COUNT} video, found {len(videos)}"
        )

    return (True, "")


def build_playlist():
    """
    Return playlist suitable for mpv.
    """

    return [
        str(image)
        for image in discover_ads()
    ]


def write_content_version():
    """
    Write content metadata file.
    """

    video = discover_video()

    ads = discover_ads()

    data = {
        "installed":
            datetime.now().isoformat(),

        "ad_count":
            len(discover_ads()),

        "showcase_count":
            len(discover_showcase()),

        "video":
            video.name if video else None,
    }

    with open(
        CONTENT_VERSION_FILE,
        "w"
    ) as f:

        json.dump(
            data,
            f,
            indent=4
        )

    logger.info(
        "Updated content_version.json"
    )
