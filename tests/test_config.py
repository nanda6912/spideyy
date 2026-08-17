import logging
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.config import load_config
from core.exceptions import ConfigurationError


class ConfigTests(unittest.TestCase):
    def test_loads_safe_environment_settings(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            env_file = Path(directory) / ".env"
            env_file.write_text("JARVIS_LOG_LEVEL=DEBUG\nJARVIS_DEBUG=true\n", encoding="utf-8")
            with patch.dict(os.environ, {}, clear=True):
                config = load_config(env_file)

        self.assertEqual(config.log_level, logging.DEBUG)
        self.assertTrue(config.debug)

    def test_invalid_log_level_raises_configuration_error(self) -> None:
        with patch.dict(os.environ, {"JARVIS_LOG_LEVEL": "LOUD"}, clear=True):
            with self.assertRaises(ConfigurationError):
                load_config(Path("does-not-exist.env"))
