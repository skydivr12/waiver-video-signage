"""
Logging subsystem.
Every component in the project imports this logger,
guaranteeing consistent formatting across all services.
"""
import logging
from logging.handlers import RotatingFileHandler
from config import LOG_FILE, LOG_LEVEL

LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger("signage")
logger.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.INFO))

formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

if not logger.handlers:
    # File handler — rotates at 5 MB, keeps 10 backups
    file_handler = RotatingFileHandler(LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=10)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Console handler — useful when running manually; remove if not wanted
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
