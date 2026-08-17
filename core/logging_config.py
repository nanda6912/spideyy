"""Centralized, secret-safe Python logging configuration."""

from __future__ import annotations

import logging
import re
from pathlib import Path

from core.config import AssistantConfig


LOGGER_NAME = "jarvis"
_SECRET_PATTERN = re.compile(
    r"(?i)\b(password|secret|token|api[_-]?key)\b\s*([=:])\s*([^\s,;]+)"
)


class SecretRedactionFilter(logging.Filter):
    """Remove common credential fields from log messages."""

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        redacted = _SECRET_PATTERN.sub(r"\1\2[REDACTED]", message)
        if redacted != message:
            record.msg = redacted
            record.args = ()
        return True


def configure_logging(config: AssistantConfig) -> logging.Logger:
    """Configure and return the assistant logger.

    This module only writes operational metadata; callers must never include
    credentials, tokens, or other secrets in log messages.
    """
    log_path = Path(config.log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(config.log_level)
    logger.propagate = False
    for handler in logger.handlers:
        handler.close()
    logger.handlers.clear()

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    file_handler.addFilter(SecretRedactionFilter())
    logger.addHandler(file_handler)
    return logger
