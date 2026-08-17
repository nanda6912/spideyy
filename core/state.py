"""Assistant lifecycle state and transition rules."""

from __future__ import annotations

from enum import Enum

from core.exceptions import StateTransitionError


class AssistantState(str, Enum):
    """States used by the SPIDEYY assistant lifecycle."""

    STANDBY = "standby"
    WAKING = "waking"
    LISTENING = "listening"
    PROCESSING = "processing"
    EXECUTING = "executing"
    RESPONDING = "responding"
    ERROR = "error"


_ALLOWED_TRANSITIONS: dict[AssistantState, frozenset[AssistantState]] = {
    AssistantState.STANDBY: frozenset({AssistantState.WAKING}),
    AssistantState.WAKING: frozenset({AssistantState.LISTENING, AssistantState.ERROR}),
    AssistantState.LISTENING: frozenset({AssistantState.PROCESSING, AssistantState.STANDBY, AssistantState.ERROR}),
    AssistantState.PROCESSING: frozenset({AssistantState.EXECUTING, AssistantState.RESPONDING, AssistantState.ERROR}),
    AssistantState.EXECUTING: frozenset({AssistantState.RESPONDING, AssistantState.ERROR}),
    AssistantState.RESPONDING: frozenset({AssistantState.STANDBY, AssistantState.LISTENING, AssistantState.ERROR}),
    AssistantState.ERROR: frozenset({AssistantState.STANDBY}),
}


class StateManager:
    """Tracks the current lifecycle state and enforces valid transitions."""

    def __init__(self, initial_state: AssistantState = AssistantState.STANDBY) -> None:
        self._state = initial_state

    @property
    def current(self) -> AssistantState:
        """Return the current assistant state."""
        return self._state

    def can_transition_to(self, target: AssistantState) -> bool:
        """Return whether *target* is valid from the current state."""
        return target in _ALLOWED_TRANSITIONS[self._state]

    def transition_to(self, target: AssistantState) -> AssistantState:
        """Move to *target*, raising when the transition is invalid."""
        if not self.can_transition_to(target):
            raise StateTransitionError(
                f"Cannot transition from {self._state.value} to {target.value}."
            )
        self._state = target
        return self._state
