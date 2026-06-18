import time

from led import LEDManager

led = LEDManager()

states = [
    "BOOTING",
    "READY",
    "PLAYING",
    "UPDATING",
    "ERROR",
    "OFF"
]

for state in states:

    print(state)

    led.set_state(state)

    time.sleep(5)

led.stop()
