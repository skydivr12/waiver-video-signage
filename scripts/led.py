"""
LED State Manager
States: OFF, BOOTING, READY, PLAYING, UPDATING, ERROR
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

# Each state is a sequence of (led_on, duration) steps that repeat in a loop.
# True = LED on, False = LED off.
_PATTERNS = {
    STATE_OFF:      [(False, 0.5)],
    STATE_BOOTING:  [(True, 0.1), (False, 0.1)],
    STATE_READY:    [(True, 0.5), (False, 1.5)],
    STATE_PLAYING:  [(True,  0.1)],
    STATE_UPDATING: [(True, 0.1), (False, 0.1)],
    STATE_ERROR:    [(True, 0.2), (False, 0.2), (True, 0.2), (False, 0.2), (False, 1.0)],
}
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
            for led_on, duration in _PATTERNS.get(self.state, _DEFAULT_PATTERN):
                self.led.on() if led_on else self.led.off()
                time.sleep(duration)
