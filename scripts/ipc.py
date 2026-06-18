"""
IPC subsystem.

Provides simple messaging between services
using a Unix domain socket.

This avoids temporary files and polling.
"""

import os
import socket

from config import SOCKET_PATH
from logger import logger


class IPCServer:

    def __init__(self):

        if os.path.exists(SOCKET_PATH):
            os.remove(SOCKET_PATH)

        self.server = socket.socket(
            socket.AF_UNIX,
            socket.SOCK_STREAM
        )

        self.server.bind(SOCKET_PATH)

        self.server.listen(5)

        self.server.settimeout(1)

        logger.info(
            "IPC server listening."
        )

    def receive(self):

        try:

            conn, _ = self.server.accept()

        except socket.timeout:

            return None

        try:

            data = conn.recv(1024)

            return data.decode().strip()

        finally:

            conn.close()


    def close(self):

        self.server.close()

        if os.path.exists(SOCKET_PATH):
            os.remove(SOCKET_PATH)


class IPCClient:

    def send(self, message):

        sock = socket.socket(
            socket.AF_UNIX,
            socket.SOCK_STREAM
        )

        try:

            sock.connect(SOCKET_PATH)

            sock.sendall(
                message.encode()
            )

            logger.info(
                f"IPC sent: {message}"
            )

        except Exception as e:

            logger.error(
                f"IPC send failed: {e}"
            )

        finally:

            sock.close()
