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
import random
from datetime import datetime
from pathlib import Path
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

SUPPORTED_AD_MEDIA = {".jpg", ".jpeg", ".png", ".mp4", ".mov", ".mkv"}


def _discover(directory: Path, extensions) -> list[Path]:
    """Return files in directory matching extensions, sorted by name."""
    return sorted(
        (f for f in directory.iterdir()
         if f.is_file() and f.suffix.lower() in extensions),
        key=lambda p: p.name.lower(),
    )


def discover_ads():
    return _discover(ADS_DIR, SUPPORTED_AD_MEDIA)


def discover_showcase():
    return _discover(SHOWCASE_DIR, SUPPORTED_IMAGES)


def discover_videos():
    return _discover(VIDEOS_DIR, SUPPORTED_VIDEOS)


def discover_video():
    """Return the single instructional video, or None."""
    videos = discover_videos()
    return videos[0] if len(videos) == 1 else None


def get_video():
    video = discover_video()
    if video is None:
        raise RuntimeError("No valid instructional video")
    return str(video)


def validate_content():
    ads = discover_ads()
    if len(ads) < MIN_IMAGE_COUNT:
        return False, f"Need at least {MIN_IMAGE_COUNT} ad image(s)"
    videos = discover_videos()
    if len(videos) != MAX_VIDEO_COUNT:
        return False, f"Expected {MAX_VIDEO_COUNT} video, found {len(videos)}"
    return True, ""


def build_playlist():
    ads = discover_ads()
    showcase = discover_showcase()
    if not showcase:
        return [str(ad) for ad in ads]
    random.shuffle(showcase)
    playlist = []
    for showcase_image in showcase:
        playlist.extend(str(ad) for ad in ads)
        playlist.append(str(showcase_image))
    return playlist


def write_playlist():
    playlist = build_playlist()
    with open(PLAYLIST_FILE, "w") as f:
        f.write("#EXTM3U\n")
        f.writelines(f"{item}\n" for item in playlist)
    logger.info(f"Playlist updated with {len(playlist)} entries")


def write_content_version():
    ads = discover_ads()
    video = discover_video()
    data = {
        "installed": datetime.now().isoformat(),
        "ad_count": len(ads),
        "showcase_count": len(discover_showcase()),
        "video": video.name if video else None,
    }
    with open(CONTENT_VERSION_FILE, "w") as f:
        json.dump(data, f, indent=4)
    logger.info("Updated content_version.json")
