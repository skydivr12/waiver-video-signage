#!/usr/bin/env python3
import os
import shutil
import socket
import subprocess
import time
import signal
import urllib.request
from config import (
    PLAYLIST_FILE,
    IMAGE_DISPLAY_SECONDS,
    SLIDESHOW_MPV_LOG,
    VIDEO_MPV_LOG,
    CMD_PLAY_VIDEO,
    CMD_RELOAD_CONTENT,
    CMD_REBOOT,
    CMD_SHUTDOWN,
    CMD_ROLLBACK,
    STATE_BOOTING,
    STATE_READY,
    STATE_PLAYING,
    STATE_UPDATING,
    STATE_ERROR,
    VLC_HOST,
    VLC_PORT,
    VLC_PASSWORD,
    ADS_DIR,
    SHOWCASE_DIR,
    VIDEOS_DIR,
    PREVIOUS_DIR,
    MANIFEST_FILE,
)
from logger import logger
from ipc import IPCServer
from led import LEDManager
from content_manager import (
    validate_content,
    write_playlist,
    write_content_version,
    get_video,
)

VLC_BASE_URL = f"http://{VLC_HOST}:{VLC_PORT}/requests"

# Build the auth opener once — reused for every VLC request.
_password_mgr = urllib.request.HTTPPasswordMgrWithDefaultRealm()
_password_mgr.add_password(None, VLC_BASE_URL, "", VLC_PASSWORD)
_vlc_opener = urllib.request.build_opener(
    urllib.request.HTTPBasicAuthHandler(_password_mgr)
)

# Watchdog interval: ping at half the period systemd expects.
_WATCHDOG_INTERVAL = int(os.environ.get("WATCHDOG_USEC", 0)) / 2_000_000
_last_watchdog = 0.0


def sd_notify(msg: str):
    """Send a notification to systemd via the notify socket."""
    notify_socket = os.environ.get("NOTIFY_SOCKET")
    if not notify_socket:
        return
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as s:
            s.connect(notify_socket)
            s.sendall(msg.encode())
    except Exception as e:
        logger.warning(f"sd_notify failed: {e}")


def _ping_watchdog():
    global _last_watchdog
    if not _WATCHDOG_INTERVAL:
        return
    now = time.monotonic()
    if now - _last_watchdog >= _WATCHDOG_INTERVAL:
        sd_notify("WATCHDOG=1")
        _last_watchdog = now


def vlc_request(path, params=None):
    """
    Send a request to the VLC HTTP interface.
    Returns the response body as bytes, or None on failure.
    """
    url = VLC_BASE_URL + path
    if params:
        url += "?" + "&".join(f"{k}={v}" for k, v in params.items())
    try:
        with _vlc_opener.open(url, timeout=2) as resp:
            return resp.read()
    except Exception:
        return None


def vlc_command(command, **kwargs):
    """Send a playback command to VLC."""
    return vlc_request("/status.json", {"command": command, **kwargs})


def _stop_process(proc, log_file):
    """Terminate a subprocess and close its log. Returns (None, None)."""
    if proc is not None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
    if log_file is not None:
        log_file.close()
    return None, None


class Signage:
    def __init__(self):
        self.running = True
        self.ipc = IPCServer()
        self.led = LEDManager()
        self.vlc = None
        self._vlc_log = None
        self.video_process = None
        self._video_log = None
        signal.signal(signal.SIGTERM, self.shutdown_signal)

    def shutdown_signal(self, signum, frame):
        logger.info("SIGTERM received")
        self.running = False

    # ------------------------------------------------------------------
    # Content validation
    # ------------------------------------------------------------------

    def validate_or_wait(self):
        """Wait until content is valid before starting, blinking error LED."""
        while self.running:
            valid, reason = validate_content()
            if valid:
                return True
            logger.error(f"Content invalid: {reason}")
            self.led.set_state(STATE_ERROR)
            time.sleep(30)
        return False

    # ------------------------------------------------------------------
    # Slideshow VLC process
    # ------------------------------------------------------------------

    def start_slideshow(self):
        """
        Start VLC with the playlist file.
        --loop              repeats the playlist indefinitely
        --image-duration    how long each image displays (in seconds)
        --extraintf http    enables the HTTP control interface
        --no-video-title-show  suppresses the filename overlay on screen
        --no-osd            disables on-screen display messages
        """
        if self.vlc:
            self.stop_slideshow()
        logger.info("Starting slideshow")
        self._vlc_log = open(SLIDESHOW_MPV_LOG, "a")
        self.vlc = subprocess.Popen(
            [
                "cvlc",
                "--fullscreen",
                "--loop",
                f"--image-duration={IMAGE_DISPLAY_SECONDS}",
                "--no-video-title-show",
                "--no-osd",
                "--aout=alsa",
                "--extraintf", "http",
                "--http-host", VLC_HOST,
                "--http-port", str(VLC_PORT),
                "--http-password", VLC_PASSWORD,
                str(PLAYLIST_FILE),
            ],
            stdout=self._vlc_log,
            stderr=self._vlc_log,
        )
        for _ in range(30):
            if vlc_request("/status.json") is not None:
                break
            time.sleep(0.2)
        else:
            logger.warning("VLC HTTP interface did not become ready in time")
        logger.info("Slideshow started")

    def stop_slideshow(self):
        if self.vlc or self._vlc_log:
            logger.info("Stopping slideshow")
            self.vlc, self._vlc_log = _stop_process(self.vlc, self._vlc_log)

    # ------------------------------------------------------------------
    # Instructional video
    # ------------------------------------------------------------------

    def play_video(self):
        """
        Stop the slideshow and play the instructional video.
        A separate cvlc process is used so the slideshow can resume
        cleanly from the beginning when the video finishes.
        """
        logger.info("Playing instructional video")
        self.led.set_state(STATE_PLAYING)
        self.stop_slideshow()
        self.stop_video()
        self._video_log = open(VIDEO_MPV_LOG, "a")
        self.video_process = subprocess.Popen(
            [
                "cvlc",
                "--fullscreen",
                "--no-video-title-show",
                "--no-osd",
                "--aout=alsa",
                "--play-and-exit",
                get_video(),
            ],
            stdout=self._video_log,
            stderr=self._video_log,
        )

    def stop_video(self):
        if self.video_process or self._video_log:
            logger.info("Stopping video")
            self.video_process, self._video_log = _stop_process(
                self.video_process, self._video_log
            )

    # ------------------------------------------------------------------
    # Content reload
    # ------------------------------------------------------------------

    def reload_content(self):
        """Rebuild the playlist and restart the slideshow."""
        logger.info("Reloading content")
        self.led.set_state(STATE_UPDATING)
        self.stop_slideshow()
        write_playlist()
        write_content_version()
        self.start_slideshow()
        self.led.set_state(STATE_READY)

    # ------------------------------------------------------------------
    # Rollback
    # ------------------------------------------------------------------

    def rollback_content(self):
        """Restore content from the snapshot saved before the last update."""
        if not PREVIOUS_DIR.exists():
            logger.warning("No previous snapshot available — rollback skipped")
            return

        logger.info("Rolling back to previous content")
        self.led.set_state(STATE_UPDATING)
        self.stop_slideshow()

        for name, dest in [("ads", ADS_DIR), ("showcase", SHOWCASE_DIR), ("videos", VIDEOS_DIR)]:
            src = PREVIOUS_DIR / name
            if dest.exists():
                shutil.rmtree(dest)
            if src.exists():
                shutil.copytree(src, dest)

        prev_manifest = PREVIOUS_DIR / "manifest.json"
        if prev_manifest.exists():
            shutil.copy2(prev_manifest, MANIFEST_FILE)

        write_playlist()
        write_content_version()
        self.start_slideshow()
        self.led.set_state(STATE_READY)
        logger.info("Rollback complete")

    # ------------------------------------------------------------------
    # Cleanup / system
    # ------------------------------------------------------------------

    def cleanup(self):
        self.stop_video()
        self.stop_slideshow()
        self.ipc.close()
        self.led.stop()

    def reboot(self):
        logger.info("Reboot requested")
        self.running = False
        self.led.set_state(STATE_BOOTING)
        self.cleanup()
        subprocess.run(["sudo", "reboot"])

    def shutdown(self):
        logger.info("Shutdown requested")
        self.running = False
        self.led.set_state(STATE_BOOTING)
        self.cleanup()
        subprocess.run(["sudo", "shutdown", "-h", "now"])

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def run(self):
        self.led.set_state(STATE_BOOTING)
        if not self.validate_or_wait():
            return

        write_playlist()
        write_content_version()
        self.start_slideshow()
        self.led.set_state(STATE_READY)
        sd_notify("READY=1")

        while self.running:
            _ping_watchdog()

            # Video finished — triple blink to signal resume, then restart slideshow
            if self.video_process and self.video_process.poll() is not None:
                logger.info("Video finished — resuming slideshow")
                self.stop_video()
                self.led.set_state(STATE_PLAYING)  # one-shot triple blink then off
                self.start_slideshow()

            # VLC crashed — restart slideshow
            if self.vlc and self.vlc.poll() is not None:
                logger.warning("VLC exited unexpectedly — restarting slideshow")
                self.stop_slideshow()
                self.start_slideshow()

            command = self.ipc.receive()
            if command is None:
                continue

            logger.info(f"Command: {command}")
            if command == CMD_PLAY_VIDEO:
                self.play_video()
            elif command == CMD_RELOAD_CONTENT:
                self.reload_content()
            elif command == CMD_ROLLBACK:
                self.rollback_content()
            elif command == CMD_REBOOT:
                self.reboot()
            elif command == CMD_SHUTDOWN:
                self.shutdown()

        self.cleanup()


if __name__ == "__main__":
    Signage().run()
