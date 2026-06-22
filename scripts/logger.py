"""
Logging subsystem.

Every component in the project
will import this logger.

This guarantees consistent formatting
and makes troubleshooting much easier.
"""

import logging

from logging.handlers import RotatingFileHandler

from config import LOG_FILE, LOG_LEVEL

LOG_FILE.parent.mkdir(
    parents=True,
    exist_ok=True
)

logger = logging.getLogger(
    "signage"
)

# Use the LOG_LEVEL value from config.py
# (was previously hardcoded to INFO and ignored the config setting)
logger.setLevel(
    getattr(logging, LOG_LEVEL.upper(), logging.INFO)
)

formatter = logging.Formatter(
    "%(asctime)s "
    "[%(levelname)s] "
    "%(message)s"
)

# File handler — rotates the log file so it never grows too large
if not logger.handlers:

    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=5 * 1024 * 1024,
        backupCount=10
    )

    file_handler.setFormatter(formatter)

    logger.addHandler(file_handler)

    # Console handler — prints logs to the terminal when running manually.
    # Very useful for debugging. Remove this if you don't want it.
    console_handler = logging.StreamHandler()

    console_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
