#!/usr/bin/env python3

import os
import time
import signal
import subprocess
import urllib.request
import urllib.error

from config import (
    PLAYLIST_FILE,
    IMAGE_DISPLAY_SECONDS,
    SLIDESHOW_MPV_LOG,
    VIDEO_MPV_LOG,

    CMD_PLAY_VIDEO,
    CMD_RELOAD_CONTENT,
    CMD_REBOOT,
    CMD_SHUTDOWN,

    STATE_BOOTING,
    STATE_READY,
    STATE_PLAYING,
    STATE_UPDATING,
    STATE_ERROR,
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

# ------------------------------------------------------------------
# VLC HTTP interface settings
# ------------------------------------------------------------------

VLC_HOST     = "127.0.0.1"
VLC_PORT     = 8080
VLC_PASSWORD = "signage"
VLC_BASE_URL = f"http://{VLC_HOST}:{VLC_PORT}/requests"


def vlc_request(path, params=None):
    """
    Send a request to the VLC HTTP interface.
    Returns the response body as bytes, or None on failure.
    path examples: "/status.json", "/status.json?command=pl_pause"
    """
    url = VLC_BASE_URL + path
    if params:
        query = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{url}?{query}"

    # VLC HTTP auth uses an empty username and the password
    password_mgr = urllib.request.HTTPPasswordMgrWithDefaultRealm()
    password_mgr.add_password(None, url, "", VLC_PASSWORD)
    handler = urllib.request.HTTPBasicAuthHandler(password_mgr)
    opener = urllib.request.build_opener(handler)

    try:
        with opener.open(url, timeout=2) as resp:
            return resp.read()
    except Exception:
        return None


def vlc_command(command, **kwargs):
    """Send a playback command to VLC."""
    params = {"command": command}
    params.update(kwargs)
    return vlc_request("/status.json", params)


class Signage:

    def __init__(self):

        self.running = True
        self.ipc = IPCServer()
        self.led = LEDManager()

        # VLC process for the slideshow
        self.vlc = None
        self._vlc_log = None

        # Separate VLC process for the instructional video
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
                str(PLAYLIST_FILE),  # M3U playlist file — VLC reads it natively
            ],
            stdout=self._vlc_log,
            stderr=self._vlc_log,
        )

        # Wait until VLC's HTTP interface is ready
        for _ in range(30):
            if vlc_request("/status.json") is not None:
                break
            time.sleep(0.2)
        else:
            logger.warning("VLC HTTP interface did not become ready in time")

        logger.info("Slideshow started")

    def stop_slideshow(self):
        if self.vlc:
            logger.info("Stopping slideshow")
            self.vlc.terminate()
            try:
                self.vlc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.vlc.kill()
            self.vlc = None

        if self._vlc_log:
            self._vlc_log.close()
            self._vlc_log = None

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

        video = get_video()
        self._video_log = open(VIDEO_MPV_LOG, "a")

        self.video_process = subprocess.Popen(
            [
                "cvlc",
                "--fullscreen",
                "--no-video-title-show",
                "--no-osd",
                "--play-and-exit",   # exit when the video finishes
                video,
            ],
            stdout=self._video_log,
            stderr=self._video_log,
        )

    def stop_video(self):
        if self.video_process:
            logger.info("Stopping video")
            self.video_process.terminate()
            try:
                self.video_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.video_process.kill()
            self.video_process = None

        if self._video_log:
            self._video_log.close()
            self._video_log = None

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
    # Cleanup
    # ------------------------------------------------------------------

    def reboot(self):
        logger.info("Reboot requested")
        self.running = False
        self.cleanup()
        os.system("sudo reboot")

    def cleanup(self):
        self.stop_video()
        self.stop_slideshow()
        self.ipc.close()
        self.led.stop()

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

        while self.running:

            # If the instructional video has finished, restart the slideshow
            if self.video_process:
                if self.video_process.poll() is not None:
                    logger.info("Video finished — resuming slideshow")
                    self.stop_video()
                    self.start_slideshow()
                    self.led.set_state(STATE_READY)

            # If VLC crashed or exited unexpectedly, restart it
            if self.vlc and self.vlc.poll() is not None:
                logger.warning("VLC exited unexpectedly — restarting slideshow")
                self.vlc = None
                if self._vlc_log:
                    self._vlc_log.close()
                    self._vlc_log = None
                self.start_slideshow()

            # Check for IPC commands from button.py or usb_update.py
            command = self.ipc.receive()

            if command is None:
                continue

            logger.info(f"Command: {command}")

            if command == CMD_PLAY_VIDEO:
                self.play_video()

            elif command == CMD_RELOAD_CONTENT:
                self.reload_content()

            elif command == CMD_REBOOT:
                self.reboot()

            elif command == CMD_SHUTDOWN:
                self.running = False

        self.cleanup()


if __name__ == "__main__":
    Signage().run()
