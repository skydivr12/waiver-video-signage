#!/usr/bin/env python3
"""
Button service.
Main button:     short press = play instructional video
Power button:    3 presses in 2 s = reboot
                 5 presses in 3 s = shutdown
                 (reboot is delayed 1.5 s after the 3rd press so additional
                  presses can still escalate to shutdown)
Rollback button: hold 3 s = rollback to previous content
"""
import threading
import time
from gpiozero import Button
from signal import pause
from config import (
    BUTTON_PIN,
    POWER_BUTTON_PIN,
    ROLLBACK_BUTTON_PIN,
    SHORT_PRESS_MAX,
    POWER_REBOOT_PRESSES,
    POWER_REBOOT_WINDOW,
    POWER_REBOOT_DELAY,
    POWER_SHUTDOWN_PRESSES,
    POWER_SHUTDOWN_WINDOW,
    ROLLBACK_PRESS_SECONDS,
    CMD_PLAY_VIDEO,
    CMD_REBOOT,
    CMD_SHUTDOWN,
    CMD_ROLLBACK,
)
from logger import logger
from ipc import IPCClient

client      = IPCClient()
press_times = {}

# ---------------------------------------------------------------------------
# Power button — multi-press detection
# ---------------------------------------------------------------------------

_power_presses = []   # timestamps of recent power button presses
_power_timer   = None # pending reboot timer (may be cancelled by more presses)


def power_pressed():
    global _power_timer
    now = time.time()
    _power_presses.append(now)

    # Cancel any queued reboot — user may be going for shutdown
    if _power_timer:
        _power_timer.cancel()
        _power_timer = None

    # Prune presses older than the longest window
    cutoff = now - max(POWER_REBOOT_WINDOW, POWER_SHUTDOWN_WINDOW)
    while _power_presses and _power_presses[0] < cutoff:
        _power_presses.pop(0)

    recent_shutdown = [t for t in _power_presses if t >= now - POWER_SHUTDOWN_WINDOW]
    recent_reboot   = [t for t in _power_presses if t >= now - POWER_REBOOT_WINDOW]

    logger.info(
        f"Power button pressed — {len(recent_reboot)} in reboot window, "
        f"{len(recent_shutdown)} in shutdown window"
    )

    # Shutdown threshold takes priority (more presses = deliberate action)
    if len(recent_shutdown) >= POWER_SHUTDOWN_PRESSES:
        _power_presses.clear()
        logger.info("Sending SHUTDOWN")
        client.send(CMD_SHUTDOWN)
        return

    # Reboot threshold reached — delay firing so more presses can still escalate
    if len(recent_reboot) >= POWER_REBOOT_PRESSES:
        def _do_reboot():
            _power_presses.clear()
            logger.info("Sending REBOOT")
            client.send(CMD_REBOOT)
        _power_timer = threading.Timer(POWER_REBOOT_DELAY, _do_reboot)
        _power_timer.start()
        logger.info(f"Reboot queued — fires in {POWER_REBOOT_DELAY}s unless more presses arrive")


# ---------------------------------------------------------------------------
# Main button
# ---------------------------------------------------------------------------

def main_released():
    duration = time.time() - press_times.get("main", 0)
    logger.info(f"Main button released after {duration:.2f}s")
    if duration <= SHORT_PRESS_MAX:
        logger.info("Sending PLAY_VIDEO")
        client.send(CMD_PLAY_VIDEO)


# ---------------------------------------------------------------------------
# Rollback button
# ---------------------------------------------------------------------------

def rollback_released():
    duration = time.time() - press_times.get("rollback", 0)
    logger.info(f"Rollback button released after {duration:.2f}s")
    if duration >= ROLLBACK_PRESS_SECONDS:
        logger.info("Sending ROLLBACK")
        client.send(CMD_ROLLBACK)


# ---------------------------------------------------------------------------
# Wire up buttons
# ---------------------------------------------------------------------------

main_button     = Button(BUTTON_PIN,          pull_up=True, bounce_time=0.1)
power_button    = Button(POWER_BUTTON_PIN,    pull_up=True, bounce_time=0.1)
rollback_button = Button(ROLLBACK_BUTTON_PIN, pull_up=True, bounce_time=0.1)

main_button.when_pressed      = lambda: press_times.update({"main": time.time()})
main_button.when_released     = main_released
power_button.when_pressed     = power_pressed
rollback_button.when_pressed  = lambda: press_times.update({"rollback": time.time()})
rollback_button.when_released = rollback_released

logger.info("Button service started")
pause()
