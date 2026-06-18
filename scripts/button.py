#!/usr/bin/env python3

"""
Production button service.

Short press:
    Play instructional video

Long press:
    Reboot Pi
"""

import time

from gpiozero import Button
from signal import pause

from config import (
    BUTTON_PIN,
    REBOOT_PRESS_SECONDS,
    SHORT_PRESS_MAX,
    CMD_PLAY_VIDEO,
    CMD_REBOOT,
)

from logger import logger
from ipc import IPCClient

button = Button(
    BUTTON_PIN,
    pull_up=True,
    bounce_time=0.1
)

client = IPCClient()

press_start = 0


def button_pressed():

    global press_start

    press_start = time.time()

    logger.info(
        "Button pressed"
    )


def button_released():

    duration = time.time() - press_start

    logger.info(
        f"Button released after {duration:.2f}s"
    )

    if duration <= SHORT_PRESS_MAX:

        logger.info(
            "Sending PLAY_VIDEO"
        )

        client.send(CMD_PLAY_VIDEO)

    elif duration >= REBOOT_PRESS_SECONDS:

        logger.info(
            "Reboot requested"
        )

        client.send(CMD_REBOOT)


button.when_pressed = button_pressed
button.when_released = button_released

logger.info(
    "Button service started"
)

pause()
