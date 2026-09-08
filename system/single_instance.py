"""Single instance enforcement for SPIDEYY desktop assistant using Windows Mutex."""

from __future__ import annotations

import logging
from typing import Any

try:
    import win32api
    import win32event
    import winerror
except ImportError:
    win32api = None  # type: ignore[assignment]
    win32event = None  # type: ignore[assignment]
    winerror = None  # type: ignore[assignment]

logger = logging.getLogger("jarvis.system.single_instance")

DEFAULT_MUTEX_NAME = "Local\\SPIDEYY_Desktop_Assistant_Instance_Mutex"


class SingleInstanceGuard:
    """Ensures only a single instance of the SPIDEYY desktop assistant runs simultaneously."""

    def __init__(
        self,
        name: str = DEFAULT_MUTEX_NAME,
        win32event_backend: Any = None,
        win32api_backend: Any = None,
        winerror_backend: Any = None,
    ) -> None:
        self.name = name
        self.handle: Any = None
        self._is_already_running = False
        self._win32event = win32event_backend if win32event_backend is not None else win32event
        self._win32api = win32api_backend if win32api_backend is not None else win32api
        self._winerror = winerror_backend if winerror_backend is not None else winerror

    @property
    def is_already_running(self) -> bool:
        """Return True if an existing instance was detected during acquire."""
        return self._is_already_running

    def acquire(self) -> bool:
        """Attempt to acquire the named mutex.

        Returns True if this is the first running instance.
        Returns False if another instance is already running.
        """
        if self._win32event is None or self._win32api is None or self._winerror is None:
            logger.warning("Win32 mutex API unavailable; skipping single instance check.")
            return True

        try:
            self.handle = self._win32event.CreateMutex(None, False, self.name)
            last_error = self._win32api.GetLastError()
            if last_error == self._winerror.ERROR_ALREADY_EXISTS:
                self._is_already_running = True
                self.release()
                logger.info("Another instance of SPIDEYY is already running.")
                return False

            self._is_already_running = False
            return True
        except Exception as exc:
            logger.warning("Failed to create single instance mutex (%s); allowing startup.", exc)
            return True

    def release(self) -> None:
        """Close and release the mutex handle."""
        if self.handle is not None and self._win32api is not None:
            try:
                self._win32api.CloseHandle(self.handle)
            except Exception as exc:
                logger.debug("Error closing mutex handle: %s", exc)
            finally:
                self.handle = None

    def __enter__(self) -> bool:
        return self.acquire()

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.release()
