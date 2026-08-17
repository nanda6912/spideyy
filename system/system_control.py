"""Low-risk Windows system control operations."""

from __future__ import annotations

import ctypes
import logging
from typing import Any, Callable

from core.models import CommandResult

logger = logging.getLogger("jarvis.system.system_control")


def _default_volume_interface() -> Any:
    from comtypes import CLSCTX_ALL
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

    devices = AudioUtilities.GetSpeakers()
    interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    return interface.QueryInterface(IAudioEndpointVolume)


def _default_lock_function() -> bool:
    return bool(ctypes.windll.user32.LockWorkStation())


class SystemControlService:
    """Provides low-risk Windows system controls (volume, workstation locking)."""

    def __init__(
        self,
        volume_interface_provider: Callable[[], Any] | None = None,
        lock_function: Callable[[], bool] | None = None,
    ) -> None:
        self._volume_interface_provider = volume_interface_provider or _default_volume_interface
        self._lock_function = lock_function or _default_lock_function

    def mute_volume(self) -> CommandResult:
        """Mute the Windows master audio endpoint."""
        try:
            volume = self._volume_interface_provider()
            volume.SetMute(1, None)
            return CommandResult.ok("Volume muted.")
        except Exception as error:
            logger.error("Failed to mute volume (%s).", type(error).__name__)
            return CommandResult.failure(
                "system_control_failed",
                "I couldn't change the system volume.",
            )

    def unmute_volume(self) -> CommandResult:
        """Unmute the Windows master audio endpoint."""
        try:
            volume = self._volume_interface_provider()
            volume.SetMute(0, None)
            return CommandResult.ok("Volume unmuted.")
        except Exception as error:
            logger.error("Failed to unmute volume (%s).", type(error).__name__)
            return CommandResult.failure(
                "system_control_failed",
                "I couldn't change the system volume.",
            )

    def volume_up(self, step: float = 0.05) -> CommandResult:
        """Increase master volume by *step* (default 5%)."""
        try:
            volume = self._volume_interface_provider()
            current = float(volume.GetMasterVolumeLevelScalar())
            new_level = min(1.0, current + step)
            volume.SetMasterVolumeLevelScalar(new_level, None)
            level_pct = round(new_level * 100)
            return CommandResult.ok(
                f"Volume is at {level_pct} percent.",
                level=level_pct,
            )
        except Exception as error:
            logger.error("Failed to increase volume (%s).", type(error).__name__)
            return CommandResult.failure(
                "system_control_failed",
                "I couldn't change the system volume.",
            )

    def volume_down(self, step: float = 0.05) -> CommandResult:
        """Decrease master volume by *step* (default 5%)."""
        try:
            volume = self._volume_interface_provider()
            current = float(volume.GetMasterVolumeLevelScalar())
            new_level = max(0.0, current - step)
            volume.SetMasterVolumeLevelScalar(new_level, None)
            level_pct = round(new_level * 100)
            return CommandResult.ok(
                f"Volume is at {level_pct} percent.",
                level=level_pct,
            )
        except Exception as error:
            logger.error("Failed to decrease volume (%s).", type(error).__name__)
            return CommandResult.failure(
                "system_control_failed",
                "I couldn't change the system volume.",
            )

    def set_volume(self, level: int) -> CommandResult:
        """Set master volume to an explicit percentage (0 to 100)."""
        if not isinstance(level, int) or isinstance(level, bool) or level < 0 or level > 100:
            return CommandResult.failure(
                "invalid_volume_level",
                "Volume must be between 0 and 100 percent.",
            )

        try:
            volume = self._volume_interface_provider()
            scalar = level / 100.0
            volume.SetMasterVolumeLevelScalar(scalar, None)
            return CommandResult.ok(
                f"Volume is at {level} percent.",
                level=level,
            )
        except Exception as error:
            logger.error("Failed to set volume (%s).", type(error).__name__)
            return CommandResult.failure(
                "system_control_failed",
                "I couldn't change the system volume.",
            )

    def lock_computer(self) -> CommandResult:
        """Lock the current Windows workstation session."""
        try:
            success = self._lock_function()
            if not success:
                logger.error("LockWorkStation API returned failure.")
                return CommandResult.failure(
                    "system_control_failed",
                    "I couldn't lock the computer.",
                )
            return CommandResult.ok("Computer locked.")
        except Exception as error:
            logger.error("Failed to lock computer (%s).", type(error).__name__)
            return CommandResult.failure(
                "system_control_failed",
                "I couldn't lock the computer.",
            )
