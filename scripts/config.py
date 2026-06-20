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
LED_PIN = 18

# ------------------------------------------------------------------
# Timing
# ------------------------------------------------------------------

IMAGE_DISPLAY_SECONDS = 10

SHORT_PRESS_MAX = 2

REBOOT_PRESS_SECONDS = 5

BACKUP_RETENTION = 10

# ------------------------------------------------------------------
# Paths
# ------------------------------------------------------------------

ROOT_DIR = Path("/opt/signage")

ADS_DIR = ROOT_DIR / "ads"

SHOWCASE_DIR = ROOT_DIR / "showcase"

VIDEOS_DIR = ROOT_DIR / "videos"

STAGING_DIR = ROOT_DIR / "staging"

STAGING_ADS_DIR = STAGING_DIR / "ads"

STAGING_SHOWCASE_DIR = STAGING_DIR / "showcase"

STAGING_VIDEOS_DIR = STAGING_DIR / "videos"

BACKUP_DIR = ROOT_DIR / "backups"

LOG_DIR = ROOT_DIR / "logs"

CONFIG_DIR = ROOT_DIR / "config"

PLAYLIST_FILE = (
    CONFIG_DIR / "playlist.txt"
)

CONTENT_VERSION_FILE = (
    CONFIG_DIR / "content_version.json"
)

MPV_SOCKET = "/tmp/mpv.sock"

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

UPDATE_LOCK_FILE = (
    CONFIG_DIR / "update.lock"
)

INSTALLED_VIDEO_NAME = (
    "instruction.mp4"
)

CONVERT_COMMAND = "/usr/bin/convert"

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



