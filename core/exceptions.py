"""Application-specific exceptions for the assistant core."""


class JarvisError(Exception):
    """Base exception for all expected assistant errors."""


class ConfigurationError(JarvisError):
    """Raised when assistant configuration is invalid or incomplete."""


class StateTransitionError(JarvisError):
    """Raised when an invalid assistant state transition is requested."""


class CommandError(JarvisError):
    """Raised when a command cannot be parsed or executed."""


class CommandNotFoundError(CommandError):
    """Raised when no registered handler matches a command."""
