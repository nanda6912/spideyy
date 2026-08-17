"""Data models shared by the assistant core."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class CommandResult:
    """The structured outcome of a command handled by the assistant."""

    success: bool
    message: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    error_code: str | None = None

    def __post_init__(self) -> None:
        if self.success and self.error_code is not None:
            raise ValueError("Successful command results cannot have an error code.")
        if not self.success and not self.error_code:
            raise ValueError("Failed command results must have an error code.")

    @classmethod
    def ok(cls, message: str = "", **data: Any) -> CommandResult:
        """Build a successful command result."""
        return cls(success=True, message=message, data=data)

    @classmethod
    def failure(
        cls, error_code: str, message: str, **data: Any
    ) -> CommandResult:
        """Build a failed command result."""
        return cls(success=False, message=message, data=data, error_code=error_code)


@dataclass(frozen=True, slots=True)
class CommandIntent:
    """The structured internal representation of an interpreted command."""

    name: str
    target: str | None = None
    arguments: dict[str, Any] = field(default_factory=dict)
    raw_command: str = ""

