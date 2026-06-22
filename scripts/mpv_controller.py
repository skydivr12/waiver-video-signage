"""
mpv controller.

Provides a clean interface for
sending commands to mpv's IPC socket.
"""

import json
import socket

from config import MPV_SOCKET
from logger import logger

class MPVController:

    def send(self, command):

        sock = socket.socket(
            socket.AF_UNIX,
            socket.SOCK_STREAM
        )

        try:

            sock.connect(MPV_SOCKET)

            sock.sendall(
                (
                    json.dumps(command)
                    + "\n"
                ).encode()
            )

        finally:

            sock.close()

    def load_file(self, filename):

        logger.info(
            f"Loading media: {filename}"
        )

        self.send({
            "command": [
                "loadfile",
                filename,
                "replace"
            ]
        })

    def pause(self):

        self.send({
            "command": [
                "set_property",
                "pause",
                True
            ]
        })

    def resume(self):

        self.send({
            "command": [
                "set_property",
                "pause",
                False
            ]
        })

    def command(self, *args):

        self.send({
            "command": list(args)
        })

    def stop(self):

        self.command("stop")
