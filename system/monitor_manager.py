"""Read-only management of the Windows display topology through Qt."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from PySide6.QtGui import QGuiApplication, QScreen


@dataclass(frozen=True, slots=True)
class MonitorInfo:
    """Typed, assistant-facing information about one connected monitor."""

    index: int
    name: str
    x: int
    y: int
    width: int
    height: int
    is_primary: bool
    available_x: int
    available_y: int
    available_width: int
    available_height: int

    def __post_init__(self) -> None:
        if self.index < 1:
            raise ValueError("Monitor indices must start at 1.")
        if not self.name.strip():
            raise ValueError("Monitor name cannot be empty.")
        if self.width <= 0 or self.height <= 0:
            raise ValueError("Monitor dimensions must be positive.")
        if self.available_width <= 0 or self.available_height <= 0:
            raise ValueError("Available monitor dimensions must be positive.")

    @property
    def geometry(self) -> tuple[int, int, int, int]:
        """Return the full monitor bounds as ``(x, y, width, height)``."""
        return (self.x, self.y, self.width, self.height)

    @property
    def available_geometry(self) -> tuple[int, int, int, int]:
        """Return the available working area as ``(x, y, width, height)``."""
        return (
            self.available_x,
            self.available_y,
            self.available_width,
            self.available_height,
        )


class MonitorManager:
    """Reports all displays currently exposed by Qt/Windows without moving windows."""

    def __init__(
        self,
        screen_provider: Callable[[], Sequence[QScreen]] | None = None,
        primary_screen_provider: Callable[[], QScreen | None] | None = None,
    ) -> None:
        self._screen_provider = screen_provider
        self._primary_screen_provider = primary_screen_provider
        self._owned_application: QGuiApplication | None = None

    def get_monitors(self) -> list[MonitorInfo]:
        """Return all current monitors in Qt's display order."""
        screens = list(self._get_screens())
        primary = self._get_primary_screen()
        return [
            self._to_monitor_info(index, screen, screen is primary)
            for index, screen in enumerate(screens, start=1)
        ]

    def get_monitor(self, index: int) -> MonitorInfo | None:
        """Return the monitor with an assistant-facing one-based index, if present."""
        return next((monitor for monitor in self.get_monitors() if monitor.index == index), None)

    def get_primary_monitor(self) -> MonitorInfo | None:
        """Return the current primary monitor, if Qt reports one."""
        return next((monitor for monitor in self.get_monitors() if monitor.is_primary), None)

    def monitor_count(self) -> int:
        """Return the current number of connected displays."""
        return len(self._get_screens())

    def describe_monitors(self) -> str:
        """Return a concise display summary suitable for JARVIS responses."""
        descriptions = []
        for monitor in self.get_monitors():
            role = "Primary" if monitor.is_primary else "Secondary"
            descriptions.append(
                f"Monitor {monitor.index}: {monitor.name}, "
                f"{monitor.width}x{monitor.height}, {role}"
            )
        return "\n".join(descriptions) if descriptions else "No monitors detected."

    def _get_screens(self) -> Sequence[QScreen]:
        if self._screen_provider is not None:
            return self._screen_provider()
        self._ensure_application()
        return QGuiApplication.screens()

    def _get_primary_screen(self) -> QScreen | None:
        if self._primary_screen_provider is not None:
            return self._primary_screen_provider()
        self._ensure_application()
        return QGuiApplication.primaryScreen()

    def _ensure_application(self) -> None:
        if QGuiApplication.instance() is None:
            self._owned_application = QGuiApplication([])

    @staticmethod
    def _to_monitor_info(index: int, screen: QScreen, is_primary: bool) -> MonitorInfo:
        geometry = screen.geometry()
        available = screen.availableGeometry()
        name = screen.name().strip() or f"Display {index}"
        return MonitorInfo(
            index=index,
            name=name,
            x=geometry.x(),
            y=geometry.y(),
            width=geometry.width(),
            height=geometry.height(),
            is_primary=is_primary,
            available_x=available.x(),
            available_y=available.y(),
            available_width=available.width(),
            available_height=available.height(),
        )
