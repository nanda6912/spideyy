import logging
import tempfile
import unittest
from pathlib import Path

from core.config import AssistantConfig
from core.logging_config import configure_logging


class LoggingConfigTests(unittest.TestCase):
    def test_creates_log_file_and_redacts_sensitive_values(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            log_path = Path(directory) / "logs" / "jarvis.log"
            logger = configure_logging(AssistantConfig(log_level=logging.INFO, log_path=log_path))
            logger.info("api_key=super-secret-value command received")

            for handler in logger.handlers:
                handler.flush()
            content = log_path.read_text(encoding="utf-8")
            for handler in logger.handlers:
                handler.close()
            logger.handlers.clear()

        self.assertIn("api_key=[REDACTED]", content)
        self.assertNotIn("super-secret-value", content)
