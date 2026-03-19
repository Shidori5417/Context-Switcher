"""Merkezi loglama altyapısı."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOGS_DIR = Path.home() / ".context-switcher" / "logs"


def setup_logger(name: str = "context_switcher") -> logging.Logger:
    """Arka plan işlemleri için dönen (rotating) log yapılandırır."""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOGS_DIR / "app.log"

    logger = logging.getLogger(name)
    
    # Zaten yapılandırıldıysa tekrar ekleme
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    # Dosya loglayıcı (maks 5MB, en fazla 3 yedek var)
    file_handler = RotatingFileHandler(
        log_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)

    # Format: [Y-m-d H:M:S] [LEVEL] [module] Message
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger


# Global nesne
logger = setup_logger()
