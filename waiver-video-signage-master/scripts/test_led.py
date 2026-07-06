#!/usr/bin/env python3
"""
LED pattern test script.
Run directly on the Pi to audition LED states before committing them to led.py.

Usage:
    sudo python3 /opt/signage/scripts/test_led.py
"""

import os
import sys
import threading
import time

os.environ.setdefault("GPIOZERO_PIN_FACTORY", "lgpio")

from gpiozero import LED
from config import LED_PIN

# ---------------------------------------------------------------------------
# Patterns — list of (led_on, duration_seconds) steps that loop indefinitely
# ---------------------------------------------------------------------------

PATTERNS = {
    "1": (
        "Triple blink",
        [
            (True,  0.15), (False, 0.15),
            (True,  0.15), (False, 0.15),
            (True,  0.15), (False, 0.75),
        ],
    ),
    "2": (
        "Slow pulse",
        [
            (True,  1.0), (False, 2.0),
        ],
    ),
    "3": (
        "Fast pulse",
        [
            (True,  0.1), (False, 0.1),
        ],
    ),
    "4": (
        "Always on",
        [
            (True, 1.0),
        ],
    ),
    "5": (
        "Always off",
        [
            (False, 1.0),
        ],
    ),
    "6": (
        "SOS (morse: · · ·  — — —  · · ·)",
        [
            # S: · · ·
            (True, 0.15), (False, 0.15),
            (True, 0.15), (False, 0.15),
            (True, 0.15), (False, 0.45),  # letter gap
            # O: — — —
            (True, 0.45), (False, 0.15),
            (True, 0.45), (False, 0.15),
            (True, 0.45), (False, 0.45),  # letter gap
            # S: · · ·
            (True, 0.15), (False, 0.15),
            (True, 0.15), (False, 0.15),
            (True, 0.15), (False, 1.5),   # word gap before repeat
        ],
    ),
}

# ---------------------------------------------------------------------------

def run_pattern(led, pattern, stop_event):
    while not stop_event.is_set():
        for led_on, duration in pattern:
            if stop_event.is_set():
                break
            led.on() if led_on else led.off()
            time.sleep(duration)


def main():
    led = LED(LED_PIN)
    current_thread = None
    stop_event = threading.Event()

    print("\n=== LED Pattern Tester ===")
    print(f"GPIO pin: {LED_PIN}\n")

    while True:
        for key, (name, _) in PATTERNS.items():
            print(f"  [{key}] {name}")
        print("  [q] Quit\n")

        choice = input("Select pattern: ").strip().lower()

        # Stop any running pattern
        stop_event.set()
        if current_thread:
            current_thread.join()
        led.off()
        stop_event.clear()

        if choice == "q":
            print("LED off. Bye.")
            break

        if choice not in PATTERNS:
            print("Invalid choice.\n")
            continue

        name, pattern = PATTERNS[choice]
        print(f"\nRunning: {name}  (press Enter to stop)\n")

        current_thread = threading.Thread(
            target=run_pattern, args=(led, pattern, stop_event), daemon=True
        )
        current_thread.start()

        input()  # wait for Enter

        stop_event.set()
        current_thread.join()
        led.off()
        stop_event.clear()
        print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(0)
