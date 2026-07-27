import logging
import os
import sys
from datetime import datetime

LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

LOG_FILE = os.path.join(LOG_DIR, f"app_{datetime.now().strftime('%Y%m%d')}.log")

_APP_LOGGER_NAME = "healthcare_app"
_app_logger = logging.getLogger(_APP_LOGGER_NAME)

if not _app_logger.handlers:
    _app_logger.propagate = False

    _formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)-8s | %(name)-30s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    _file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    _file_handler.setFormatter(_formatter)
    _file_handler.setLevel(logging.DEBUG)

    _console_handler = logging.StreamHandler(sys.stdout)
    _console_handler.setFormatter(_formatter)
    _console_handler.setLevel(logging.INFO)

    _app_logger.setLevel(logging.DEBUG)
    _app_logger.addHandler(_file_handler)
    _app_logger.addHandler(_console_handler)

for noisy_logger in ["google_genai", "httpcore", "httpx", "urllib3", "chardet"]:
    logging.getLogger(noisy_logger).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    full_name = f"{_APP_LOGGER_NAME}.{name}"
    logger = logging.getLogger(full_name)
    logger.propagate = True
    return logger
