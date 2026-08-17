"""High-risk Windows power operations (shutdown, restart, sleep)."""

from __future__ import annotations

import ctypes
import logging
from typing import Callable

import win32api
import win32con
import win32security

from core.models import CommandResult

logger = logging.getLogger("jarvis.system.system_power")


def _enable_shutdown_privilege() -> None:
    """Enable Windows SE_SHUTDOWN_NAME privilege for the current process."""
    try:
        h_token = win32security.OpenProcessToken(
            win32api.GetCurrentProcess(),
            win32security.TOKEN_ADJUST_PRIVILEGES | win32security.TOKEN_QUERY,
        )
        luid = win32security.LookupPrivilegeValue(None, win32security.SE_SHUTDOWN_NAME)
        win32security.AdjustTokenPrivileges(h_token, 0, [(luid, win32con.SE_PRIVILEGE_ENABLED)])
    except Exception as error:
        logger.warning("Could not adjust shutdown privilege (%s).", type(error).__name__)


def _default_shutdown() -> bool:
    try:
        _enable_shutdown_privilege()
        return bool(win32api.ExitWindowsEx(win32con.EWX_SHUTDOWN | win32con.EWX_POWEROFF, 0))
    except Exception as error:
        logger.error("ExitWindowsEx shutdown failed (%s).", type(error).__name__)
        return False


def _default_restart() -> bool:
    try:
        _enable_shutdown_privilege()
        return bool(win32api.ExitWindowsEx(win32con.EWX_REBOOT, 0))
    except Exception as error:
        logger.error("ExitWindowsEx reboot failed (%s).", type(error).__name__)
        return False


def _default_sleep() -> bool:
    try:
        return bool(ctypes.windll.PowrProf.SetSuspendState(0, 1, 0))
    except Exception as error:
        logger.error("SetSuspendState sleep failed (%s).", type(error).__name__)
        return False


class SystemPowerService:
    """Provides high-risk power control operations (shutdown, restart, sleep)."""

    def __init__(
        self,
        shutdown_function: Callable[[], bool] | None = None,
        restart_function: Callable[[], bool] | None = None,
        sleep_function: Callable[[], bool] | None = None,
    ) -> None:
        self._shutdown_function = shutdown_function or _default_shutdown
        self._restart_function = restart_function or _default_restart
        self._sleep_function = sleep_function or _default_sleep

    def shutdown_computer(self) -> CommandResult:
        """Execute Windows workstation shutdown."""
        try:
            success = self._shutdown_function()
            if not success:
                logger.error("Shutdown API returned failure.")
                return CommandResult.failure(
                    "system_power_failed",
                    "I couldn't shut down the computer.",
                )
            return CommandResult.ok("Shutting down.")
        except Exception as error:
            logger.error("Failed to shutdown computer (%s).", type(error).__name__)
            return CommandResult.failure(
                "system_power_failed",
                "I couldn't shut down the computer.",
            )

    def restart_computer(self) -> CommandResult:
        """Execute Windows workstation restart."""
        try:
            success = self._restart_function()
            if not success:
                logger.error("Restart API returned failure.")
                return CommandResult.failure(
                    "system_power_failed",
                    "I couldn't restart the computer.",
                )
            return CommandResult.ok("Restarting.")
        except Exception as error:
            logger.error("Failed to restart computer (%s).", type(error).__name__)
            return CommandResult.failure(
                "system_power_failed",
                "I couldn't restart the computer.",
            )

    def sleep_computer(self) -> CommandResult:
        """Put Windows workstation to sleep."""
        try:
            success = self._sleep_function()
            if not success:
                logger.error("Sleep API returned failure.")
                return CommandResult.failure(
                    "system_power_failed",
                    "I couldn't put the computer to sleep.",
                )
            return CommandResult.ok("Putting the computer to sleep.")
        except Exception as error:
            logger.error("Failed to sleep computer (%s).", type(error).__name__)
            return CommandResult.failure(
                "system_power_failed",
                "I couldn't put the computer to sleep.",
            )
