import unittest
from unittest.mock import Mock

from core.assistant import JarvisAssistant
from core.models import CommandResult
from core.state import AssistantState, StateManager


class JarvisAssistantTests(unittest.TestCase):
    def test_handles_command_and_returns_to_standby(self) -> None:
        assistant = JarvisAssistant(
            registry=Mock(),
            registry_service=Mock(),
            monitor_manager=Mock(),
            window_manager=Mock(),
            launcher=Mock(),
        )
        assistant.router.route = Mock(return_value=CommandResult.ok("Done."))

        result = assistant.handle_command("help")

        self.assertTrue(result.success)
        self.assertEqual(assistant.state_manager.current, AssistantState.STANDBY)

    def test_processing_failure_enters_error_state(self) -> None:
        state = StateManager()
        assistant = JarvisAssistant(
            registry=Mock(),
            registry_service=Mock(),
            monitor_manager=Mock(),
            window_manager=Mock(),
            launcher=Mock(),
            state_manager=state,
        )
        assistant.router.route = Mock(side_effect=RuntimeError("test"))

        result = assistant.handle_command("help")

        self.assertEqual(result.error_code, "command_processing_failed")
        self.assertEqual(state.current, AssistantState.ERROR)
