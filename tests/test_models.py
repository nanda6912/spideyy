import unittest

from core.models import CommandResult


class CommandResultTests(unittest.TestCase):
    def test_success_factory_creates_structured_result(self) -> None:
        result = CommandResult.ok("Opened application", app="Notepad")

        self.assertTrue(result.success)
        self.assertEqual(result.data, {"app": "Notepad"})
        self.assertIsNone(result.error_code)

    def test_failure_requires_error_code(self) -> None:
        with self.assertRaises(ValueError):
            CommandResult(success=False, message="Something failed")

    def test_failure_factory_creates_structured_result(self) -> None:
        result = CommandResult.failure("command_not_found", "No command found")

        self.assertFalse(result.success)
        self.assertEqual(result.error_code, "command_not_found")
