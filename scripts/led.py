"""
LED State Manager
States: OFF, BOOTING, READY, PLAYING, UPDATING, ERROR

One-shot states run their pattern exactly once then go to OFF.
All other states loop their pattern until the state changes.
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
    STATE_ERROR,
)
from logger import logger

STATE_OFF = "OFF"

# Repeating patterns — loop indefinitely until state changes.
_PATTERNS = {
    STATE_OFF:      [(False, 1.0)],
    STATE_READY:    [(False, 1.0)],                  # slideshow running — LED off
    STATE_BOOTING:  [(True, 1.0), (False, 2.0)],     # slow pulse — booting / shutting down
    STATE_UPDATING: [(True, 0.1), (False, 0.1)],     # rapid blink — update in progress
    STATE_ERROR: [                                    # SOS — · · ·  — — —  · · ·
        (True,  0.15), (False, 0.15),
        (True,  0.15), (False, 0.15),
        (True,  0.15), (False, 0.45),
        (True,  0.45), (False, 0.15),
        (True,  0.45), (False, 0.15),
        (True,  0.45), (False, 0.45),
        (True,  0.15), (False, 0.15),
        (True,  0.15), (False, 0.15),
        (True,  0.15), (False, 1.5),
    ],
    # One-shot: triple blink then off — video starting or slideshow resuming
    STATE_PLAYING: [
        (True,  0.15), (False, 0.15),
        (True,  0.15), (False, 0.15),
        (True,  0.15), (False, 0.15),
    ],
}

# States whose pattern runs once and then the LED goes off automatically.
_ONE_SHOT_STATES = {STATE_PLAYING}

_DEFAULT_PATTERN = [(False, 1.0)]


class LEDManager:
    def __init__(self):
        self.state = STATE_OFF
        self.running = True
        if ENABLE_LED:
            self.led = LED(LED_PIN)
            threading.Thread(target=self._worker, daemon=True).start()
            logger.info("LED subsystem initialized.")
        else:
            self.led = None
            logger.info("LED subsystem disabled.")

    def set_state(self, state):
        logger.info(f"LED state -> {state}")
        self.state = state

    def stop(self):
        self.running = False
        if self.led:
            self.led.off()

    def _worker(self):
        while self.running:
            state = self.state
            pattern = _PATTERNS.get(state, _DEFAULT_PATTERN)
            one_shot = state in _ONE_SHOT_STATES

            for led_on, duration in pattern:
                if self.state != state:
                    # State changed mid-pattern — restart the outer loop
                    break
                self.led.on() if led_on else self.led.off()
                time.sleep(duration)
            else:
                # Pattern completed without interruption
                if one_shot:
                    self.led.off()
                    self.state = STATE_OFF
