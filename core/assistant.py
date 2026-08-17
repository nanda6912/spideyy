
"""High-level JARVIS assistant façade for deterministic desktop commands."""

from __future__ import annotations

from core.command_router import CommandRouter
from core.models import CommandResult
from core.state import AssistantState, StateManager
from system.application_discovery import ApplicationRegistry
from system.application_launcher import ApplicationLauncher
from system.application_registry_service import ApplicationRegistryService
from system.monitor_manager import MonitorManager
from system.system_information import SystemInformationService
from system.window_manager import WindowManager


class JarvisAssistant:
    """Connect startup services, lifecycle state, and command routing."""

    def __init__(
        self,
        registry: ApplicationRegistry | None = None,
        registry_service: ApplicationRegistryService | None = None,
        monitor_manager: MonitorManager | None = None,
        window_manager: WindowManager | None = None,
        launcher: ApplicationLauncher | None = None,
        state_manager: StateManager | None = None,
        system_info_service: SystemInformationService | None = None,
    ) -> None:
        self.registry = registry or ApplicationRegistry()
        self.state_manager = state_manager or StateManager()
        self.monitor_manager = monitor_manager or MonitorManager()
        self.window_manager = window_manager or WindowManager(
            self.monitor_manager
        )
        self.launcher = launcher or ApplicationLauncher(self.registry)
        self.registry_service = (
            registry_service or ApplicationRegistryService(self.registry)
        )
        self.system_info_service = (
            system_info_service or SystemInformationService()
        )

        self.router = CommandRouter(
            self.registry,
            self.launcher,
            self.monitor_manager,
            self.window_manager,
            self.state_manager,
            self.registry_service,
            system_info_service=self.system_info_service,
        )


    def startup(self) -> CommandResult:
        """Ensure application discovery has populated the persistent registry."""
        return self.registry_service.ensure_populated()

    def handle_command(self, command: str) -> CommandResult:
        """Process one command through the expected assistant state lifecycle."""
        try:
            if self.state_manager.current == AssistantState.ERROR:
                self.state_manager.transition_to(AssistantState.STANDBY)

            if self.state_manager.current == AssistantState.STANDBY:
                self.state_manager.transition_to(AssistantState.WAKING)
                self.state_manager.transition_to(AssistantState.LISTENING)

            self.state_manager.transition_to(AssistantState.PROCESSING)
            self.state_manager.transition_to(AssistantState.EXECUTING)

            result = self.router.route(command)

            self.state_manager.transition_to(AssistantState.RESPONDING)
            self.state_manager.transition_to(AssistantState.STANDBY)

            return result

        except Exception:
            if self.state_manager.current != AssistantState.ERROR:
                self.state_manager.transition_to(AssistantState.ERROR)

            return CommandResult.failure(
                "command_processing_failed",
                "I couldn't process that command safely.",
            )

    def begin_voice_session(self) -> None:
        """Move the assistant into voice-command listening mode."""
        if self.state_manager.current == AssistantState.STANDBY:
            self.state_manager.transition_to(AssistantState.WAKING)
            self.state_manager.transition_to(AssistantState.LISTENING)

    def handle_voice_command(self, command: str) -> CommandResult:
        """Execute a command received after the voice wake phrase."""
        try:
            if self.state_manager.current != AssistantState.LISTENING:
                return CommandResult.failure(
                    "invalid_voice_state",
                    "I'm not currently listening for a command.",
                )

            self.state_manager.transition_to(AssistantState.PROCESSING)
            self.state_manager.transition_to(AssistantState.EXECUTING)

            result = self.router.route(command)

            self.state_manager.transition_to(AssistantState.RESPONDING)
            self.state_manager.transition_to(AssistantState.STANDBY)

            return result

        except Exception:
            if self.state_manager.current != AssistantState.ERROR:
                self.state_manager.transition_to(AssistantState.ERROR)

            return CommandResult.failure(
                "command_processing_failed",
                "I couldn't process that command safely.",
            )


Assistant = JarvisAssistant

