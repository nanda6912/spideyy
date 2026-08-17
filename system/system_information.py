"""Read-only system information service for JARVIS."""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any, Callable

import psutil

from core.models import CommandResult

logger = logging.getLogger("jarvis.system.system_information")


class SystemInformationService:
    """Provides human-readable, read-only system telemetry and time."""

    def __init__(
        self,
        time_provider: Callable[[], datetime] | None = None,
        cpu_provider: Callable[[], float] | None = None,
        memory_provider: Callable[[], Any] | None = None,
        disk_provider: Callable[[str], Any] | None = None,
        battery_provider: Callable[[], Any | None] | None = None,
    ) -> None:
        self._time_provider = time_provider or datetime.now
        self._cpu_provider = cpu_provider or (lambda: psutil.cpu_percent(interval=None))
        self._memory_provider = memory_provider or psutil.virtual_memory
        self._disk_provider = disk_provider or psutil.disk_usage
        self._battery_provider = battery_provider or psutil.sensors_battery

    def get_cpu_usage(self) -> CommandResult:
        """Return formatted CPU usage percentage."""
        try:
            percent = float(self._cpu_provider())
            rounded = round(percent)
            return CommandResult.ok(
                f"CPU usage is {rounded} percent.",
                cpu_percent=percent,
            )
        except Exception as error:
            logger.error("Failed to read CPU usage (%s).", type(error).__name__)
            return CommandResult.failure(
                "system_information_failed",
                "I couldn't read the system information.",
            )

    def get_memory_usage(self) -> CommandResult:
        """Return formatted RAM usage and available memory."""
        try:
            mem = self._memory_provider()
            percent = float(mem.percent)
            available_gb = float(mem.available) / (1024**3)
            rounded_percent = round(percent)
            return CommandResult.ok(
                f"Memory usage is {rounded_percent} percent. {available_gb:.1f} gigabytes are available.",
                memory_percent=percent,
                available_gb=round(available_gb, 1),
            )
        except Exception as error:
            logger.error("Failed to read memory usage (%s).", type(error).__name__)
            return CommandResult.failure(
                "system_information_failed",
                "I couldn't read the system information.",
            )

    def get_disk_usage(self) -> CommandResult:
        """Return formatted system drive usage and available disk space."""
        try:
            drive = os.environ.get("SystemDrive", "C:")
            if not drive.endswith("\\") and not drive.endswith("/"):
                drive += "\\"
            disk = self._disk_provider(drive)
            percent = float(disk.percent)
            free_gb = float(disk.free) / (1024**3)
            rounded_percent = round(percent)
            rounded_free = round(free_gb)
            return CommandResult.ok(
                f"Disk usage is {rounded_percent} percent. {rounded_free} gigabytes are available.",
                disk_percent=percent,
                free_gb=round(free_gb, 1),
            )
        except Exception as error:
            logger.error("Failed to read disk usage (%s).", type(error).__name__)
            return CommandResult.failure(
                "system_information_failed",
                "I couldn't read the system information.",
            )

    def get_battery_status(self) -> CommandResult:
        """Return formatted battery level and charging state, or safe fallback."""
        try:
            battery = self._battery_provider()
            if battery is None:
                return CommandResult.ok(
                    "No battery information is available on this system.",
                    has_battery=False,
                )
            percent = round(float(battery.percent))
            is_charging = bool(battery.power_plugged)
            state_str = "and charging." if is_charging else "and not charging."
            return CommandResult.ok(
                f"Battery is at {percent} percent {state_str}",
                has_battery=True,
                battery_percent=percent,
                power_plugged=is_charging,
            )
        except Exception as error:
            logger.error("Failed to read battery status (%s).", type(error).__name__)
            return CommandResult.failure(
                "system_information_failed",
                "I couldn't read the system information.",
            )

    def get_current_time(self) -> CommandResult:
        """Return formatted local system time."""
        try:
            now = self._time_provider()
            time_str = now.strftime("%I:%M %p").lstrip("0")
            return CommandResult.ok(
                f"It is {time_str}.",
                time=time_str,
            )
        except Exception as error:
            logger.error("Failed to read current time (%s).", type(error).__name__)
            return CommandResult.failure(
                "system_information_failed",
                "I couldn't read the system information.",
            )

    def get_system_status(self) -> CommandResult:
        """Return a concise summary of CPU, memory, disk, and battery status."""
        try:
            cpu = round(float(self._cpu_provider()))
            mem = self._memory_provider()
            mem_pct = round(float(mem.percent))
            drive = os.environ.get("SystemDrive", "C:")
            if not drive.endswith("\\") and not drive.endswith("/"):
                drive += "\\"
            disk = self._disk_provider(drive)
            disk_pct = round(float(disk.percent))
            battery = self._battery_provider()

            lines = [
                "System status:",
                f"CPU {cpu} percent.",
                f"Memory {mem_pct} percent.",
                f"Disk {disk_pct} percent.",
            ]
            has_battery = battery is not None
            if has_battery:
                b_pct = round(float(battery.percent))
                b_state = "and charging." if bool(battery.power_plugged) else "and not charging."
                lines.append(f"Battery {b_pct} percent {b_state}")

            message = "\n".join(lines)
            return CommandResult.ok(
                message,
                cpu_percent=cpu,
                memory_percent=mem_pct,
                disk_percent=disk_pct,
                has_battery=has_battery,
            )
        except Exception as error:
            logger.error("Failed to read system status (%s).", type(error).__name__)
            return CommandResult.failure(
                "system_information_failed",
                "I couldn't read the system information.",
            )
