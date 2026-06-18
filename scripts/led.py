"""
LED State Manager

This module provides a common interface
for the rest of the project.

States:

OFF
BOOTING
READY
PLAYING
UPDATING
ERROR
"""

import threading
import time

from gpiozero import LED

from config import (
    ENABLE_LED,
    LED_PIN,

    STATE_BOOTING,
    STATE_READY,
    STATE_PLAYING,
    STATE_UPDATING,
    STATE_ERROR
)

from logger import logger


class LEDManager:

    def __init__(self):

        self.state = "OFF"

        self.running = True

        self.thread = None

        if ENABLE_LED:

            self.led = LED(LED_PIN)

            self.thread = threading.Thread(
                target=self._worker,
                daemon=True
            )

            self.thread.start()

            logger.info(
                "LED subsystem initialized."
            )

        else:

            self.led = None

            logger.info(
                "LED subsystem disabled."
            )

    def set_state(self, state):

        logger.info(
            f"LED state -> {state}"
        )

        self.state = state

    def stop(self):

        self.running = False

        if self.led:

            self.led.off()

    def _worker(self):

        while self.running:

            if self.state == "OFF":

                self.led.off()

                time.sleep(0.5)

            elif self.state == STATE_BOOTING:

                self.led.on()

                time.sleep(0.1)

                self.led.off()

                time.sleep(0.1)

            elif self.state == "READY":

                self.led.on()

                time.sleep(0.5)

                self.led.off()

                time.sleep(1.5)

            elif self.state == "PLAYING":

                self.led.on()

                time.sleep(0.1)

            elif self.state == "UPDATING":

                self.led.on()

                time.sleep(0.1)

                self.led.off()

                time.sleep(0.1)

            elif self.state == "ERROR":

                self.led.on()

                time.sleep(0.2)

                self.led.off()

                time.sleep(0.2)

                self.led.on()

                time.sleep(0.2)

                self.led.off()

                time.sleep(1.0)

            else:

                self.led.off()

                time.sleep(1)
