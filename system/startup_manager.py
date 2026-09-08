"""Windows per-user startup manager for SPIDEYY assistant."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

try:
    import winreg
except ImportError:
    winreg = None  # type: ignore[assignment]

logger = logging.getLogger("jarvis.system.startup")

RUN_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
DEFAULT_VALUE_NAME = "SPIDEYY"


class StartupManager:
    """Manages automatic per-user Windows desktop login startup via HKCU Run key."""

    def __init__(
        self,
        value_name: str = DEFAULT_VALUE_NAME,
        registry_backend: Any = None,
    ) -> None:
        self._value_name = value_name
        self._winreg = registry_backend if registry_backend is not None else winreg

    @property
    def value_name(self) -> str:
        return self._value_name

    def get_startup_command(self) -> str:
        """Resolve canonical executable and entry point command line with proper quoting."""
        python_exe = Path(sys.executable).resolve()
        project_root = Path(__file__).resolve().parent.parent
        main_script = (project_root / "app" / "main.py").resolve()
        return f'"{python_exe}" "{main_script}"'

    def is_enabled(self) -> bool:
        """Check whether SPIDEYY is configured to launch on Windows login."""
        if self._winreg is None:
            logger.warning("winreg module unavailable; startup check returning False.")
            return False

        try:
            with self._winreg.OpenKey(
                self._winreg.HKEY_CURRENT_USER,
                RUN_KEY_PATH,
                0,
                self._winreg.KEY_READ,
            ) as key:
                value, value_type = self._winreg.QueryValueEx(key, self._value_name)
                return (
                    value_type == self._winreg.REG_SZ
                    and isinstance(value, str)
                    and bool(value.strip())
                )
        except (FileNotFoundError, OSError):
            return False
        except Exception as exc:
            logger.error("Failed to query startup registry key: %s", exc)
            return False

    def enable(self, command: str | None = None) -> bool:
        """Register SPIDEYY in HKCU Run to automatically launch upon user login."""
        if self._winreg is None:
            logger.warning("winreg module unavailable; cannot enable startup.")
            return False

        cmd = command if command is not None else self.get_startup_command()
        try:
            with self._winreg.CreateKeyEx(
                self._winreg.HKEY_CURRENT_USER,
                RUN_KEY_PATH,
                0,
                self._winreg.KEY_SET_VALUE,
            ) as key:
                self._winreg.SetValueEx(
                    key,
                    self._value_name,
                    0,
                    self._winreg.REG_SZ,
                    cmd,
                )
            logger.info("SPIDEYY Windows startup enabled: %s", cmd)
            return True
        except Exception as exc:
            logger.error("Failed to enable Windows startup in registry: %s", exc)
            return False

    def disable(self) -> bool:
        """Remove SPIDEYY from HKCU Run key to stop automatic startup."""
        if self._winreg is None:
            logger.warning("winreg module unavailable; cannot disable startup.")
            return False

        try:
            with self._winreg.OpenKey(
                self._winreg.HKEY_CURRENT_USER,
                RUN_KEY_PATH,
                0,
                self._winreg.KEY_SET_VALUE,
            ) as key:
                try:
                    self._winreg.DeleteValue(key, self._value_name)
                except (FileNotFoundError, OSError):
                    # Already absent
                    pass
            logger.info("SPIDEYY Windows startup disabled.")
            return True
        except Exception as exc:
            logger.error("Failed to disable Windows startup in registry: %s", exc)
            return False
