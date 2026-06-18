"""
Logging subsystem.

Every component in the project
will import this logger.

This guarantees consistent formatting
and makes troubleshooting much easier.
"""

import logging

from logging.handlers import RotatingFileHandler

from config import LOG_FILE

LOG_FILE.parent.mkdir(
    parents=True,
    exist_ok=True
)

logger = logging.getLogger(
    "signage"
)

logger.setLevel(logging.INFO)

handler = RotatingFileHandler(
    LOG_FILE,
    maxBytes=5 * 1024 * 1024,
    backupCount=10
)

formatter = logging.Formatter(
    "%(asctime)s "
    "[%(levelname)s] "
    "%(message)s"
)

handler.setFormatter(formatter)

#logger.addHandler(handler)
if not logger.handlers:
    logger.addHandler(handler)
