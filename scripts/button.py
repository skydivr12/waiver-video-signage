#!/usr/bin/env python3
"""
Button service.
Main button:     short press = play instructional video
Power button:    3s press = reboot, 6s press = shutdown
Rollback button: 3s press = rollback to previous content
"""
import time
from gpiozero import Button
from signal import pause
from config import (
    BUTTON_PIN,
    POWER_BUTTON_PIN,
    ROLLBACK_BUTTON_PIN,
    SHORT_PRESS_MAX,
    POWER_REBOOT_SECONDS,
    POWER_SHUTDOWN_SECONDS,
    ROLLBACK_PRESS_SECONDS,
    CMD_PLAY_VIDEO,
    CMD_REBOOT,
    CMD_SHUTDOWN,
    CMD_ROLLBACK,
)
from logger import logger
from ipc import IPCClient

client     = IPCClient()
press_times = {}


def make_press_handler(name):
    def handler():
        press_times[name] = time.time()
        logger.info(f"{name} button pressed")
    return handler


def main_released():
    duration = time.time() - press_times.get("main", 0)
    logger.info(f"Main button released after {duration:.2f}s")
    if duration <= SHORT_PRESS_MAX:
        logger.info("Sending PLAY_VIDEO")
        client.send(CMD_PLAY_VIDEO)


def power_released():
    duration = time.time() - press_times.get("power", 0)
    logger.info(f"Power button released after {duration:.2f}s")
    if duration >= POWER_SHUTDOWN_SECONDS:
        logger.info("Sending SHUTDOWN")
        client.send(CMD_SHUTDOWN)
    elif duration >= POWER_REBOOT_SECONDS:
        logger.info("Sending REBOOT")
        client.send(CMD_REBOOT)


def rollback_released():
    duration = time.time() - press_times.get("rollback", 0)
    logger.info(f"Rollback button released after {duration:.2f}s")
    if duration >= ROLLBACK_PRESS_SECONDS:
        logger.info("Sending ROLLBACK")
        client.send(CMD_ROLLBACK)


main_button     = Button(BUTTON_PIN,          pull_up=True, bounce_time=0.1)
power_button    = Button(POWER_BUTTON_PIN,    pull_up=True, bounce_time=0.1)
rollback_button = Button(ROLLBACK_BUTTON_PIN, pull_up=True, bounce_time=0.1)

main_button.when_pressed      = make_press_handler("main")
main_button.when_released     = main_released
power_button.when_pressed     = make_press_handler("power")
power_button.when_released    = power_released
rollback_button.when_pressed  = make_press_handler("rollback")
rollback_button.when_released = rollback_released

logger.info("Button service started")
pause()
