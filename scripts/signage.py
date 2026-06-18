#!/usr/bin/env python3

import os
import time
import signal
import subprocess

from config import (
    PLAYLIST_FILE,
    IMAGE_DISPLAY_SECONDS,

    CMD_PLAY_VIDEO,
    CMD_RELOAD_CONTENT,
    CMD_REBOOT,
    CMD_SHUTDOWN,

    STATE_BOOTING,
    STATE_READY,
    STATE_PLAYING,
    STATE_UPDATING,
    STATE_ERROR,

    SLIDESHOW_MPV_LOG,
    VIDEO_MPV_LOG
)

from logger import logger
from ipc import IPCServer
from led import LEDManager

from content_manager import (
    validate_content,
    write_playlist,
    write_content_version,
    get_video
)


class Signage:

    def __init__(self):

        self.video_process = None

        self.running = True

        self.ipc = IPCServer()

        self.led = LEDManager()

        self.slideshow = None

        signal.signal(
            signal.SIGTERM,
            self.shutdown_signal
        )

    def shutdown_signal(
        self,
        signum,
        frame
    ):

        logger.info(
            "SIGTERM received"
        )

        self.running = False

    def validate_or_wait(self):

        while self.running:

            valid, reason = (
                validate_content()
            )

            if valid:

                return True

            logger.error(
                f"Content invalid: {reason}"
            )

            self.led.set_state(
                STATE_ERROR
            )

            time.sleep(30)

        return False

    def start_slideshow(self):

        logger.info(
            "Starting slideshow"
        )

        log = open(
            SLIDESHOW_MPV_LOG,
            "a"
        )

        self.slideshow = subprocess.Popen(
            [
                "mpv",

                "--fs",

                "--really-quiet",

                "--loop-playlist=inf",

                f"--image-display-duration={IMAGE_DISPLAY_SECONDS}",

                f"--playlist={PLAYLIST_FILE}"
            ],
            stdout=log,
            stderr=log
        )

    def stop_slideshow(self):

        if self.slideshow:

            logger.info(
                "Stopping slideshow"
            )

            self.slideshow.terminate()

            self.slideshow.wait(
                timeout=10
            )

            self.slideshow = None

    def play_video(self):

        logger.info(
            "Playing instructional video"
        )

        self.led.set_state(
            STATE_PLAYING
        )

        self.stop_slideshow()

        self.stop_video()

        video = get_video()

        log = open(
            VIDEO_MPV_LOG,
            "a"
        )

        self.video_process = subprocess.Popen(
            [
                "mpv",
                "--fs",
                "--really-quiet",
                video
            ],
            stdout=log,
            stderr=log
        )

    def stop_video(self):

        if self.video_process:

            logger.info(
                "Stopping current video"
            )

            self.video_process.terminate()

            try:

                self.video_process.wait(
                    timeout=5
                )

            except subprocess.TimeoutExpired:

                self.video_process.kill()

            self.video_process = None


    def reload_content(self):

        logger.info(
            "Reloading content"
        )

        self.led.set_state(
            STATE_UPDATING
        )

        self.stop_slideshow()

        write_playlist()

        write_content_version()

        self.start_slideshow()

        self.led.set_state(
            STATE_READY
        )

    def reboot(self):

        logger.info(
            "Reboot requested"
        )

        self.running = False

        self.cleanup()

        os.system(
            "sudo reboot"
        )

    def cleanup(self):

        self.stop_video()

        self.stop_slideshow()

        self.ipc.close()

        self.led.stop()

    def run(self):

        self.led.set_state(
            STATE_BOOTING
        )

        if not self.validate_or_wait():

            return

        write_playlist()

        write_content_version()

        self.start_slideshow()

        self.led.set_state(
            STATE_READY
        )

        while self.running:

            if self.video_process:

                if self.video_process.poll() is not None:

                    logger.info(
                        "Video finished"
                    )

                    self.video_process = None

                    self.start_slideshow()

                    self.led.set_state(
                        STATE_READY
                    )

            command = (
                self.ipc.receive()
            )

            if command is None:

                continue

            logger.info(
                f"Command: {command}"
            )

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
