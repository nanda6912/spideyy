"""Safe, environment-based configuration loading."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from core.exceptions import ConfigurationError


DEFAULT_LOG_PATH = Path("data/logs/jarvis.log")


@dataclass(frozen=True, slots=True)
class AssistantConfig:
    """Non-sensitive runtime settings for the assistant."""

    log_level: int = logging.INFO
    log_path: Path = DEFAULT_LOG_PATH
    debug: bool = False


def load_config(env_file: Path | str = ".env") -> AssistantConfig:
    """Load safe settings from the environment, without exposing secret values.

    Existing process environment variables take precedence over values in ``.env``.
    """
    load_dotenv(dotenv_path=env_file, override=False)

    level_name = os.getenv("JARVIS_LOG_LEVEL", "INFO").upper()
    log_level = logging.getLevelName(level_name)
    if not isinstance(log_level, int):
        raise ConfigurationError("JARVIS_LOG_LEVEL must be a valid logging level.")

    raw_debug = os.getenv("JARVIS_DEBUG", "false").strip().lower()
    if raw_debug not in {"true", "false", "1", "0", "yes", "no"}:
        raise ConfigurationError("JARVIS_DEBUG must be a boolean value.")

    log_path = Path(os.getenv("JARVIS_LOG_PATH", str(DEFAULT_LOG_PATH)))
    return AssistantConfig(
        log_level=log_level,
        log_path=log_path,
        debug=raw_debug in {"true", "1", "yes"},
    )
