"""Confirmation state management for high-risk assistant actions."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable


@dataclass(frozen=True, slots=True)
class PendingConfirmation:
    """Represents a pending high-risk action requiring user confirmation."""

    action: str
    created_at: float = field(default_factory=time.monotonic)
    timeout_seconds: float = 10.0
    description: str = ""

    def is_expired(self, current_time: float | None = None) -> bool:
        """Return whether this pending confirmation has exceeded its timeout."""
        now = time.monotonic() if current_time is None else current_time
        return (now - self.created_at) > self.timeout_seconds


class ConfirmationManager:
    """Manages creation, validation, expiration, and resolution of pending confirmations."""

    def __init__(
        self,
        default_timeout: float = 10.0,
        time_provider: Callable[[], float] | None = None,
    ) -> None:
        self._default_timeout = default_timeout
        self._time_provider = time_provider or time.monotonic
        self._pending: PendingConfirmation | None = None
        self._last_expired_action: str | None = None

    @property
    def pending(self) -> PendingConfirmation | None:
        """Return the current active pending confirmation, or None if expired/absent."""
        if self._pending is None:
            return None
        now = self._time_provider()
        if self._pending.is_expired(now):
            self._last_expired_action = self._pending.action
            self._pending = None
            return None
        return self._pending

    def create(
        self, action: str, description: str = "", timeout: float | None = None
    ) -> PendingConfirmation:
        """Store a new pending confirmation, overriding any previous pending action."""
        duration = self._default_timeout if timeout is None else timeout
        pending = PendingConfirmation(
            action=action,
            created_at=self._time_provider(),
            timeout_seconds=duration,
            description=description,
        )
        self._pending = pending
        self._last_expired_action = None
        return pending

    def clear(self) -> None:
        """Clear any active pending confirmation."""
        self._pending = None
        self._last_expired_action = None

    def pop_expired_action(self) -> str | None:
        """Return and clear the action name of a confirmation that recently expired."""
        # Trigger expiration check
        _ = self.pending
        action = self._last_expired_action
        self._last_expired_action = None
        return action
