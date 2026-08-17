import unittest

from core.exceptions import CommandError, CommandNotFoundError, JarvisError


class ExceptionHierarchyTests(unittest.TestCase):
    def test_command_not_found_is_a_jarvis_error(self) -> None:
        self.assertTrue(issubclass(CommandNotFoundError, CommandError))
        self.assertTrue(issubclass(CommandNotFoundError, JarvisError))
