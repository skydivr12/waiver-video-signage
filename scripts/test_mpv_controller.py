import time

from mpv_controller import MPVController

mpv = MPVController()

mpv.load_file(
    "/opt/signage/images/test.jpg"
)

time.sleep(5)

mpv.load_file(
    "/opt/signage/images/test2.jpg"
)
