"""Startup and on-demand maintenance for the application registry."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from datetime import datetime, timedelta, timezone

from core.models import CommandResult
from system.application_discovery import (
    ApplicationDiscovery,
    ApplicationRegistry,
    DiscoveredApplication,
)


logger = logging.getLogger("jarvis.system.application_registry_service")
REGISTRY_REFRESH_AGE = timedelta(days=1)


class ApplicationRegistryService:
    """Loads a saved registry and refreshes it only when required."""

    def __init__(
        self,
        registry: ApplicationRegistry | None = None,
        discovery: ApplicationDiscovery | None = None,
    ) -> None:
        self._registry = registry or ApplicationRegistry()
        self._discovery = discovery or ApplicationDiscovery()

    def ensure_populated(self) -> CommandResult:
        """Load the registry at startup, refreshing only if empty or stale."""
        existing = self._registry.load_all()
        if existing and not self._is_stale(existing):
            logger.info("Loaded %d applications from the saved registry.", len(existing))
            return CommandResult.ok(
                "Application registry loaded.",
                application_count=len(existing),
                refreshed=False,
            )
        return self.refresh(existing)

    def refresh(
        self, existing: Sequence[DiscoveredApplication] | None = None
    ) -> CommandResult:
        """Explicitly rebuild and persist the registry for a future UI command."""
        previous = list(existing) if existing is not None else self._registry.load_all()
        logger.info("Starting application discovery refresh.")
        try:
            discovered = self._discovery.discover()
        except Exception as error:
            logger.error("Application discovery refresh failed (%s).", type(error).__name__)
            return CommandResult.failure(
                "application_discovery_failed",
                "Application discovery failed; the existing registry is still available.",
                application_count=len(previous),
            )

        logger.info("Application discovery refresh found %d applications.", len(discovered))
        if not discovered and previous:
            logger.warning("Application discovery found no applications; keeping the existing registry.")
            return CommandResult.failure(
                "application_discovery_empty",
                "No applications were found; the existing registry was kept.",
                application_count=len(previous),
            )

        self._registry.replace_all(discovered)
        return CommandResult.ok(
            "Application registry refreshed.",
            application_count=len(discovered),
            refreshed=True,
        )

    def _is_stale(self, applications: Sequence[DiscoveredApplication]) -> bool:
        """Refresh unusable registries daily without rebuilding for one stale entry."""
        if not any(application.is_valid() for application in applications):
            return True
        try:
            modified = datetime.fromtimestamp(
                self._registry.database_path.stat().st_mtime, tz=timezone.utc
            )
        except OSError:
            return True
        return datetime.now(timezone.utc) - modified >= REGISTRY_REFRESH_AGE
