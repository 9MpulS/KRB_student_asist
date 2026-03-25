import logging
import sys

from src.core.config import settings


def setup_logging() -> None:
    """Налаштувати базову конфігурацію логування."""
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def get_logger(name: str) -> logging.Logger:
    """Отримати налаштований логер.

    Args:
        name: Ім'я модуля/компонента

    Returns:
        Налаштований Logger
    """
    return logging.getLogger(name)


# Ініціалізація при імпорті
setup_logging()
