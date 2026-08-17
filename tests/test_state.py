import unittest

from core.exceptions import StateTransitionError
from core.state import AssistantState, StateManager


class StateManagerTests(unittest.TestCase):
    def test_valid_lifecycle_transition(self) -> None:
        state = StateManager()

        self.assertEqual(state.transition_to(AssistantState.WAKING), AssistantState.WAKING)
        self.assertEqual(state.transition_to(AssistantState.LISTENING), AssistantState.LISTENING)

    def test_invalid_transition_raises(self) -> None:
        with self.assertRaises(StateTransitionError):
            StateManager().transition_to(AssistantState.EXECUTING)

    def test_all_required_states_are_available(self) -> None:
        self.assertEqual(
            {state.name for state in AssistantState},
            {"STANDBY", "WAKING", "LISTENING", "PROCESSING", "EXECUTING", "RESPONDING", "ERROR"},
        )
