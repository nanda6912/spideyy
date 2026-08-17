"""Unit tests for SystemControlService."""

from __future__ import annotations

import unittest
from unittest.mock import Mock

from system.system_control import SystemControlService


class MockAudioEndpoint:
    def __init__(self, initial_level: float = 0.50, initial_mute: int = 0) -> None:
        self.level = initial_level
        self.muted = initial_mute

    def SetMute(self, mute: int, context: object) -> None:
        self.muted = mute

    def GetMute(self) -> int:
        return self.muted

    def SetMasterVolumeLevelScalar(self, level: float, context: object) -> None:
        self.level = max(0.0, min(1.0, level))

    def GetMasterVolumeLevelScalar(self) -> float:
        return self.level


class SystemControlServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.endpoint = MockAudioEndpoint(initial_level=0.50, initial_mute=0)
        self.lock_called = False

        def mock_lock() -> bool:
            self.lock_called = True
            return True

        self.service = SystemControlService(
            volume_interface_provider=lambda: self.endpoint,
            lock_function=mock_lock,
        )

    def test_mute_volume(self) -> None:
        result = self.service.mute_volume()
        self.assertTrue(result.success)
        self.assertEqual(result.message, "Volume muted.")
        self.assertEqual(self.endpoint.GetMute(), 1)

    def test_unmute_volume(self) -> None:
        self.endpoint.SetMute(1, None)
        result = self.service.unmute_volume()
        self.assertTrue(result.success)
        self.assertEqual(result.message, "Volume unmuted.")
        self.assertEqual(self.endpoint.GetMute(), 0)

    def test_volume_up(self) -> None:
        result = self.service.volume_up(0.05)
        self.assertTrue(result.success)
        self.assertEqual(result.message, "Volume is at 55 percent.")
        self.assertEqual(result.data["level"], 55)
        self.assertAlmostEqual(self.endpoint.GetMasterVolumeLevelScalar(), 0.55)

    def test_volume_down(self) -> None:
        result = self.service.volume_down(0.05)
        self.assertTrue(result.success)
        self.assertEqual(result.message, "Volume is at 45 percent.")
        self.assertEqual(result.data["level"], 45)
        self.assertAlmostEqual(self.endpoint.GetMasterVolumeLevelScalar(), 0.45)

    def test_volume_boundaries_max(self) -> None:
        self.endpoint.SetMasterVolumeLevelScalar(0.98, None)
        result = self.service.volume_up(0.05)
        self.assertTrue(result.success)
        self.assertEqual(result.message, "Volume is at 100 percent.")
        self.assertEqual(result.data["level"], 100)

    def test_volume_boundaries_min(self) -> None:
        self.endpoint.SetMasterVolumeLevelScalar(0.02, None)
        result = self.service.volume_down(0.05)
        self.assertTrue(result.success)
        self.assertEqual(result.message, "Volume is at 0 percent.")
        self.assertEqual(result.data["level"], 0)

    def test_set_volume_valid_0(self) -> None:
        result = self.service.set_volume(0)
        self.assertTrue(result.success)
        self.assertEqual(result.message, "Volume is at 0 percent.")
        self.assertEqual(result.data["level"], 0)
        self.assertEqual(self.endpoint.GetMasterVolumeLevelScalar(), 0.0)

    def test_set_volume_valid_50(self) -> None:
        result = self.service.set_volume(50)
        self.assertTrue(result.success)
        self.assertEqual(result.message, "Volume is at 50 percent.")
        self.assertEqual(result.data["level"], 50)
        self.assertEqual(self.endpoint.GetMasterVolumeLevelScalar(), 0.5)

    def test_set_volume_valid_100(self) -> None:
        result = self.service.set_volume(100)
        self.assertTrue(result.success)
        self.assertEqual(result.message, "Volume is at 100 percent.")
        self.assertEqual(result.data["level"], 100)
        self.assertEqual(self.endpoint.GetMasterVolumeLevelScalar(), 1.0)

    def test_set_volume_invalid_negative(self) -> None:
        result = self.service.set_volume(-10)
        self.assertFalse(result.success)
        self.assertEqual(result.error_code, "invalid_volume_level")
        self.assertEqual(result.message, "Volume must be between 0 and 100 percent.")

    def test_set_volume_invalid_above_100(self) -> None:
        result = self.service.set_volume(150)
        self.assertFalse(result.success)
        self.assertEqual(result.error_code, "invalid_volume_level")
        self.assertEqual(result.message, "Volume must be between 0 and 100 percent.")

    def test_lock_computer(self) -> None:
        result = self.service.lock_computer()
        self.assertTrue(result.success)
        self.assertEqual(result.message, "Computer locked.")
        self.assertTrue(self.lock_called)

    def test_lock_computer_failure(self) -> None:
        service = SystemControlService(lock_function=lambda: False)
        result = service.lock_computer()
        self.assertFalse(result.success)
        self.assertEqual(result.error_code, "system_control_failed")
        self.assertEqual(result.message, "I couldn't lock the computer.")

    def test_windows_api_failure_handling(self) -> None:
        def failing_provider():
            raise RuntimeError("WASAPI COM Error")

        service = SystemControlService(volume_interface_provider=failing_provider)
        result = service.mute_volume()
        self.assertFalse(result.success)
        self.assertEqual(result.error_code, "system_control_failed")
        self.assertEqual(result.message, "I couldn't change the system volume.")


if __name__ == "__main__":
    unittest.main()
