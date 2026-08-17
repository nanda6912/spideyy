"""Deterministic routing for supported JARVIS desktop commands."""

from __future__ import annotations

import re

from core.command_registry import CommandRegistry, get_default_command_registry
from core.models import CommandIntent, CommandResult
from core.state import StateManager
from system.application_discovery import ApplicationRegistry, DiscoveredApplication
from system.application_launcher import ApplicationLauncher
from system.application_registry_service import ApplicationRegistryService
from system.monitor_manager import MonitorManager
from system.system_control import SystemControlService
from system.system_information import SystemInformationService
from system.window_manager import WindowInfo, WindowManager


def normalize_command(command: str) -> str:
    """Normalize user command text without changing its deterministic meaning."""
    return re.sub(r"\s+", " ", command.casefold()).strip()


class CommandRouter:
    """Route supported commands using CommandRegistry matching and intent dispatching."""

    def __init__(
        self,
        registry: ApplicationRegistry,
        launcher: ApplicationLauncher,
        monitor_manager: MonitorManager,
        window_manager: WindowManager,
        state_manager: StateManager,
        registry_service: ApplicationRegistryService | None = None,
        command_registry: CommandRegistry | None = None,
        system_info_service: SystemInformationService | None = None,
        system_control_service: SystemControlService | None = None,
    ) -> None:
        self._registry = registry
        self._launcher = launcher
        self._monitor_manager = monitor_manager
        self._window_manager = window_manager
        self._state_manager = state_manager
        self._registry_service = registry_service
        self._command_registry = command_registry or get_default_command_registry()
        self._system_info_service = system_info_service or SystemInformationService()
        self._system_control_service = system_control_service or SystemControlService()

    def route(self, command: str) -> CommandResult:
        """Return a structured result for one supported, normalized command."""
        normalized = normalize_command(command)
        if not normalized:
            return CommandResult.failure("unknown_command", "Please tell me what you would like to do.")

        intent = self._command_registry.match(normalized)
        if intent is None:
            return CommandResult.failure(
                "unknown_command",
                "I don't support that command yet. Say 'help' to see available commands.",
            )

        return self.dispatch_intent(intent)

    def dispatch_intent(self, intent: CommandIntent) -> CommandResult:
        """Dispatch a parsed CommandIntent to existing JARVIS system services."""
        if intent.name == "help":
            return CommandResult.ok(self._help_text())

        if intent.name == "status":
            return CommandResult.ok(
                f"JARVIS is {self._state_manager.current.value}.",
                state=self._state_manager.current.value,
                monitor_count=self._monitor_manager.monitor_count(),
                application_count=len(self._registry.load_all()),
            )

        if intent.name == "show_monitors":
            return CommandResult.ok(
                self._monitor_manager.describe_monitors(),
                monitor_count=self._monitor_manager.monitor_count(),
            )

        if intent.name == "count_monitors":
            count = self._monitor_manager.monitor_count()
            return CommandResult.ok(f"{count} monitor{' is' if count == 1 else 's are'} connected.", monitor_count=count)

        if intent.name == "refresh_applications":
            if self._registry_service is not None:
                return self._registry_service.refresh()

        if intent.name == "get_cpu_usage":
            return self._system_info_service.get_cpu_usage()

        if intent.name == "get_memory_usage":
            return self._system_info_service.get_memory_usage()

        if intent.name == "get_disk_usage":
            return self._system_info_service.get_disk_usage()

        if intent.name == "get_battery_status":
            return self._system_info_service.get_battery_status()

        if intent.name == "get_current_time":
            return self._system_info_service.get_current_time()

        if intent.name == "get_system_status":
            return self._system_info_service.get_system_status()

        if intent.name == "mute_volume":
            return self._system_control_service.mute_volume()

        if intent.name == "unmute_volume":
            return self._system_control_service.unmute_volume()

        if intent.name == "volume_up":
            return self._system_control_service.volume_up()

        if intent.name == "volume_down":
            return self._system_control_service.volume_down()

        if intent.name == "set_volume":
            level = intent.arguments.get("level")
            return self._system_control_service.set_volume(level)

        if intent.name == "lock_computer":
            return self._system_control_service.lock_computer()


        if intent.name == "launch_application":
            if not intent.target:
                return CommandResult.failure(
                    "application_not_found",
                    "I couldn't find that application in the discovered registry.",
                )
            return self._launcher.launch(intent.target)

        if intent.name in {"maximize_window", "minimize_window", "restore_window"}:
            if not intent.target:
                return CommandResult.failure(
                    "application_not_found",
                    "I couldn't find that application in the discovered registry.",
                )
            window_result = self._find_application_window(intent.target)
            if isinstance(window_result, CommandResult):
                return window_result
            handler = {
                "maximize_window": self._window_manager.maximize_window,
                "minimize_window": self._window_manager.minimize_window,
                "restore_window": self._window_manager.restore_window,
            }[intent.name]
            return handler(window_result)

        if intent.name == "move_window":
            if not intent.target:
                return CommandResult.failure(
                    "application_not_found",
                    "I couldn't find that application in the discovered registry.",
                )
            monitor_index = intent.arguments.get("monitor")
            if monitor_index is None or self._monitor_manager.get_monitor(monitor_index) is None:
                return CommandResult.failure(
                    "monitor_not_found",
                    f"Monitor {monitor_index} is not available.",
                    monitor_index=monitor_index,
                )
            window_result = self._find_application_window(intent.target)
            if isinstance(window_result, CommandResult):
                return window_result
            return self._window_manager.move_window_to_monitor(window_result, monitor_index)

        return CommandResult.failure(
            "unknown_command",
            "I don't support that command yet. Say 'help' to see available commands.",
        )

    def _find_application_window(self, query: str) -> WindowInfo | CommandResult:
        application = self._registry.match(query)
        if application is None:
            return CommandResult.failure(
                "application_not_found",
                "I couldn't find that application in the discovered registry.",
            )
        window = self._find_window_for_application(application, query)
        if window is None:
            return CommandResult.failure(
                "window_not_found",
                f"I couldn't find an open window for {application.name}.",
                application=application.name,
            )
        return window

    def _find_window_for_application(
        self, application: DiscoveredApplication, original_query: str
    ) -> WindowInfo | None:
        seen: set[str] = set()
        for candidate in (application.name, *application.aliases, original_query):
            if candidate in seen:
                continue
            seen.add(candidate)
            window = self._window_manager.find_window(candidate)
            if window is not None:
                return window
        return None

    @staticmethod
    def _help_text() -> str:
        return (
            "You can open applications, show monitors, maximize, minimize, restore, "
            "or move an application window to a monitor."
        )
