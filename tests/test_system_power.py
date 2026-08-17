"""Unit tests for SystemPowerService."""

from __future__ import annotations

import unittest

from system.system_power import SystemPowerService


class SystemPowerServiceTests(unittest.TestCase):
    def test_shutdown_computer_success(self) -> None:
        service = SystemPowerService(shutdown_function=lambda: True)
        result = service.shutdown_computer()
        self.assertTrue(result.success)
        self.assertEqual(result.message, "Shutting down.")

    def test_shutdown_computer_failure(self) -> None:
        service = SystemPowerService(shutdown_function=lambda: False)
        result = service.shutdown_computer()
        self.assertFalse(result.success)
        self.assertEqual(result.error_code, "system_power_failed")
        self.assertEqual(result.message, "I couldn't shut down the computer.")

    def test_restart_computer_success(self) -> None:
        service = SystemPowerService(restart_function=lambda: True)
        result = service.restart_computer()
        self.assertTrue(result.success)
        self.assertEqual(result.message, "Restarting.")

    def test_restart_computer_failure(self) -> None:
        service = SystemPowerService(restart_function=lambda: False)
        result = service.restart_computer()
        self.assertFalse(result.success)
        self.assertEqual(result.error_code, "system_power_failed")
        self.assertEqual(result.message, "I couldn't restart the computer.")

    def test_sleep_computer_success(self) -> None:
        service = SystemPowerService(sleep_function=lambda: True)
        result = service.sleep_computer()
        self.assertTrue(result.success)
        self.assertEqual(result.message, "Putting the computer to sleep.")

    def test_sleep_computer_failure(self) -> None:
        service = SystemPowerService(sleep_function=lambda: False)
        result = service.sleep_computer()
        self.assertFalse(result.success)
        self.assertEqual(result.error_code, "system_power_failed")
        self.assertEqual(result.message, "I couldn't put the computer to sleep.")

    def test_exception_handling(self) -> None:
        def failing_shutdown():
            raise RuntimeError("API error")

        service = SystemPowerService(shutdown_function=failing_shutdown)
        result = service.shutdown_computer()
        self.assertFalse(result.success)
        self.assertEqual(result.error_code, "system_power_failed")


def _confirm(raw: str) -> bool:
    """Mirror of the confirmation expression used in manual_system_power_test.py."""
    return raw.strip().casefold() == "yes"


class ManualConfirmationNormalizationTests(unittest.TestCase):
    """Verify the case-insensitive confirmation check from the manual test script."""

    def test_uppercase_yes(self) -> None:
        self.assertTrue(_confirm("YES"))

    def test_lowercase_yes(self) -> None:
        self.assertTrue(_confirm("yes"))

    def test_mixed_case_yes(self) -> None:
        self.assertTrue(_confirm("Yes"))

    def test_random_case_yes(self) -> None:
        self.assertTrue(_confirm("yEs"))

    def test_yes_with_surrounding_whitespace(self) -> None:
        self.assertTrue(_confirm("  YES  "))

    def test_empty_string_rejects(self) -> None:
        self.assertFalse(_confirm(""))

    def test_no_rejects(self) -> None:
        self.assertFalse(_confirm("no"))

    def test_cancel_rejects(self) -> None:
        self.assertFalse(_confirm("cancel"))

    def test_partial_match_rejects(self) -> None:
        self.assertFalse(_confirm("yess"))


if __name__ == "__main__":
    unittest.main()
