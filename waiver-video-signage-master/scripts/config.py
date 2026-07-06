"""
Central configuration file.

Almost everything that might need to be changed
later should live here instead of being hardcoded
throughout the project.
"""

from pathlib import Path

# ------------------------------------------------------------------
# Feature Flags
# ------------------------------------------------------------------

ENABLE_LED = True

LOG_LEVEL = "INFO"

# ------------------------------------------------------------------
# GPIO
# ------------------------------------------------------------------

BUTTON_PIN = 17
POWER_BUTTON_PIN    = 3
ROLLBACK_BUTTON_PIN = 27
LED_PIN = 18

# ------------------------------------------------------------------
# Timing
# ------------------------------------------------------------------

IMAGE_DISPLAY_SECONDS = 10
POWER_REBOOT_PRESSES   = 3     # presses needed to reboot
POWER_REBOOT_WINDOW    = 2.0   # seconds those presses must fall within
POWER_SHUTDOWN_PRESSES = 5     # presses needed to shutdown
POWER_SHUTDOWN_WINDOW  = 3.0   # seconds those presses must fall within
POWER_REBOOT_DELAY     = 1.5   # seconds to wait after reboot threshold before firing,
                                # giving the user time to add more presses for shutdown
ROLLBACK_PRESS_SECONDS = 3
SHORT_PRESS_MAX = 2

# ------------------------------------------------------------------
# Paths
# ------------------------------------------------------------------

ROOT_DIR = Path("/opt/signage")
PREVIOUS_DIR  = ROOT_DIR / "previous"
MANIFEST_FILE = ROOT_DIR / "installed_manifest.json"
ADS_DIR = ROOT_DIR / "ads"

SHOWCASE_DIR = ROOT_DIR / "showcase"

VIDEOS_DIR = ROOT_DIR / "videos"

LOG_DIR = ROOT_DIR / "logs"

CONFIG_DIR = ROOT_DIR / "config"

PLAYLIST_FILE = (
    CONFIG_DIR / "playlist.m3u"  # M3U format required by VLC
)

CONTENT_VERSION_FILE = (
    CONFIG_DIR / "content_version.json"
)

SLIDESHOW_MPV_SOCKET = "/tmp/mpv_slideshow.sock"

SLIDESHOW_MPV_LOG = (
    LOG_DIR / "mpv_slideshow.log"
)

VIDEO_MPV_LOG = (
    LOG_DIR / "mpv_video.log"
)

UPDATE_LOCK_FILE = (
    CONFIG_DIR / "update.lock"
)

CONVERT_COMMAND = "/usr/bin/convert"

FFMPEG_COMMAND = "/usr/bin/ffmpeg"

# Target frame rate for video normalisation.
# Re-encoding to a clean 30fps fixes playback speed issues caused by
# variable or mismatched frame rates in source videos.
VIDEO_FRAMERATE = 30

# CRF controls output quality. Lower = better quality, larger file.
# 23 is ffmpeg's default and a good balance for signage.
VIDEO_CRF = 23

# ------------------------------------------------------------------
# State Names
# ------------------------------------------------------------------

STATE_BOOTING = "BOOTING"

STATE_READY = "READY"

STATE_PLAYING = "PLAYING"

STATE_UPDATING = "UPDATING"

STATE_ERROR = "ERROR"

# ------------------------------------------------------------------
# Images
# ------------------------------------------------------------------

MAX_IMAGE_WIDTH = 1920
MAX_IMAGE_HEIGHT = 1080

JPEG_QUALITY = 90

SUPPORTED_IMAGES = (
    ".jpg",
    ".jpeg",
    ".png"
)

SUPPORTED_VIDEOS = (
    ".mp4",
    ".mov",
    ".mkv"
)

SLIDESHOW_TRANSITION = "none"

# ------------------------------------------------------------------
# IPC
# ------------------------------------------------------------------

SOCKET_PATH = "/tmp/signage.sock"
CMD_ROLLBACK = "ROLLBACK"
VLC_HOST     = "127.0.0.1"
VLC_PORT     = 8080
VLC_PASSWORD = "signage"

# ------------------------------------------------------------------
# IPC Commands
# ------------------------------------------------------------------

CMD_PLAY_VIDEO = "PLAY_VIDEO"

CMD_RELOAD_CONTENT = "RELOAD_CONTENT"

CMD_SHUTDOWN = "SHUTDOWN"

CMD_REBOOT = "REBOOT"

# ------------------------------------------------------------------
# Logging
# ------------------------------------------------------------------

LOG_FILE = LOG_DIR / "signage.log"


# ------------------------------------------------------------------
# Update Validation
# ------------------------------------------------------------------

UPDATE_KEY_FILENAME = "SIGNAGE_UPDATE.KEY"

MIN_IMAGE_COUNT = 1

MAX_VIDEO_COUNT = 1

# ------------------------------------------------------------------
# USB Update
# ------------------------------------------------------------------

USB_MOUNT_POINT = "/mnt/signage_update"

UPDATE_KEY_CONTENT = (
    "WAIVER_VIDEO_SIGNAGE_V1"
)

UPDATE_VERSION_FILE = (
    "content_version.json"
)



