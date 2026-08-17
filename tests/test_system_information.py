"""Unit tests for SystemInformationService."""

from __future__ import annotations

import unittest
from dataclasses import dataclass
from datetime import datetime
from unittest.mock import Mock

from system.system_information import SystemInformationService


@dataclass
class MockMemoryInfo:
    percent: float
    available: int


@dataclass
class MockDiskInfo:
    percent: float
    free: int


@dataclass
class MockBatteryInfo:
    percent: float
    power_plugged: bool


class SystemInformationServiceTests(unittest.TestCase):
    def test_cpu_formatting(self) -> None:
        service = SystemInformationService(cpu_provider=lambda: 18.4)
        result = service.get_cpu_usage()
        self.assertTrue(result.success)
        self.assertEqual(result.message, "CPU usage is 18 percent.")
        self.assertEqual(result.data["cpu_percent"], 18.4)

    def test_memory_formatting(self) -> None:
        mock_mem = MockMemoryInfo(percent=62.3, available=6550266880)  # ~6.1 GB
        service = SystemInformationService(memory_provider=lambda: mock_mem)
        result = service.get_memory_usage()
        self.assertTrue(result.success)
        self.assertEqual(result.message, "Memory usage is 62 percent. 6.1 gigabytes are available.")
        self.assertEqual(result.data["memory_percent"], 62.3)
        self.assertEqual(result.data["available_gb"], 6.1)

    def test_disk_formatting(self) -> None:
        mock_disk = MockDiskInfo(percent=71.0, free=229782913024)  # ~214 GB
        service = SystemInformationService(disk_provider=lambda drive: mock_disk)
        result = service.get_disk_usage()
        self.assertTrue(result.success)
        self.assertEqual(result.message, "Disk usage is 71 percent. 214 gigabytes are available.")
        self.assertEqual(result.data["disk_percent"], 71.0)
        self.assertEqual(result.data["free_gb"], 214.0)

    def test_battery_present_charging(self) -> None:
        mock_bat = MockBatteryInfo(percent=84.0, power_plugged=True)
        service = SystemInformationService(battery_provider=lambda: mock_bat)
        result = service.get_battery_status()
        self.assertTrue(result.success)
        self.assertEqual(result.message, "Battery is at 84 percent and charging.")
        self.assertTrue(result.data["has_battery"])
        self.assertTrue(result.data["power_plugged"])

    def test_battery_present_discharging(self) -> None:
        mock_bat = MockBatteryInfo(percent=45.0, power_plugged=False)
        service = SystemInformationService(battery_provider=lambda: mock_bat)
        result = service.get_battery_status()
        self.assertTrue(result.success)
        self.assertEqual(result.message, "Battery is at 45 percent and not charging.")
        self.assertTrue(result.data["has_battery"])
        self.assertFalse(result.data["power_plugged"])

    def test_no_battery(self) -> None:
        service = SystemInformationService(battery_provider=lambda: None)
        result = service.get_battery_status()
        self.assertTrue(result.success)
        self.assertEqual(result.message, "No battery information is available on this system.")
        self.assertFalse(result.data["has_battery"])

    def test_current_time_formatting(self) -> None:
        fixed_time = datetime(2026, 8, 17, 20, 42)
        service = SystemInformationService(time_provider=lambda: fixed_time)
        result = service.get_current_time()
        self.assertTrue(result.success)
        self.assertEqual(result.message, "It is 8:42 PM.")
        self.assertEqual(result.data["time"], "8:42 PM")

    def test_system_status_with_battery(self) -> None:
        service = SystemInformationService(
            cpu_provider=lambda: 18.0,
            memory_provider=lambda: MockMemoryInfo(percent=62.0, available=6 * 1024**3),
            disk_provider=lambda drive: MockDiskInfo(percent=71.0, free=214 * 1024**3),
            battery_provider=lambda: MockBatteryInfo(percent=84.0, power_plugged=True),
        )
        result = service.get_system_status()
        self.assertTrue(result.success)
        expected = (
            "System status:\n"
            "CPU 18 percent.\n"
            "Memory 62 percent.\n"
            "Disk 71 percent.\n"
            "Battery 84 percent and charging."
        )
        self.assertEqual(result.message, expected)
        self.assertTrue(result.data["has_battery"])

    def test_system_status_without_battery(self) -> None:
        service = SystemInformationService(
            cpu_provider=lambda: 15.0,
            memory_provider=lambda: MockMemoryInfo(percent=50.0, available=8 * 1024**3),
            disk_provider=lambda drive: MockDiskInfo(percent=40.0, free=500 * 1024**3),
            battery_provider=lambda: None,
        )
        result = service.get_system_status()
        self.assertTrue(result.success)
        expected = (
            "System status:\n"
            "CPU 15 percent.\n"
            "Memory 50 percent.\n"
            "Disk 40 percent."
        )
        self.assertEqual(result.message, expected)
        self.assertFalse(result.data["has_battery"])

    def test_error_handling(self) -> None:
        def failing_cpu():
            raise RuntimeError("Hardware error")

        service = SystemInformationService(cpu_provider=failing_cpu)
        result = service.get_cpu_usage()
        self.assertFalse(result.success)
        self.assertEqual(result.error_code, "system_information_failed")
        self.assertEqual(result.message, "I couldn't read the system information.")


if __name__ == "__main__":
    unittest.main()
