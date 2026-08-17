"""Safe launching of applications registered by application discovery."""

from __future__ import annotations

import logging
import subprocess

from core.models import CommandResult
from system.application_discovery import ApplicationRegistry, DiscoveredApplication


logger = logging.getLogger("jarvis.system.application_launcher")


class ApplicationLauncher:
    """Launch only executable paths obtained from the local application registry."""

    def __init__(self, registry: ApplicationRegistry | None = None) -> None:
        self._registry = registry or ApplicationRegistry()

    def launch(self, application_name: str) -> CommandResult:
        """Resolve and safely start a registered application.

        ``subprocess.Popen`` receives an argument list with ``shell=False`` so user
        input is never interpreted as a shell command.
        """
        application = self._registry.match(application_name)
        if application is None:
            logger.info("Application launch requested but no registry entry matched.")
            return CommandResult.failure(
                "application_not_found",
                "I couldn't find that application in the discovered registry.",
            )

        if not self._is_launchable(application):
            logger.warning("Registered application executable is no longer available.")
            return CommandResult.failure(
                "application_unavailable",
                f"{application.name} is no longer available at its registered location.",
                application=application.name,
            )

        try:
            subprocess.Popen(
                [str(application.executable_path)],
                shell=False,
                close_fds=True,
            )
        except OSError as error:
            logger.error(
                "Registered application process could not be started (%s).",
                type(error).__name__,
            )
            return CommandResult.failure(
                "application_launch_failed",
                f"I couldn't launch {application.name}.",
                application=application.name,
            )

        logger.info("Registered application launched successfully.")
        return CommandResult.ok(
            f"Launching {application.name}.",
            application=application.name,
            executable_path=str(application.executable_path),
        )

    @staticmethod
    def _is_launchable(application: DiscoveredApplication) -> bool:
        return (
            application.executable_path.is_file()
            and application.executable_path.suffix.casefold() == ".exe"
        )
