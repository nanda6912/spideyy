"""Safe, handle-based Windows window management using pywin32."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TypeAlias

import psutil
import win32con
import win32gui
import win32process

from core.models import CommandResult
from system.monitor_manager import MonitorInfo, MonitorManager


logger = logging.getLogger("jarvis.system.window_manager")
WindowReference: TypeAlias = "WindowInfo | int"


@dataclass(frozen=True, slots=True)
class WindowInfo:
    """A visible top-level application window discovered by Windows."""

    handle: int
    title: str
    process_id: int | None
    process_name: str | None
    x: int
    y: int
    width: int
    height: int

    def __post_init__(self) -> None:
        if self.handle <= 0:
            raise ValueError("Window handle must be positive.")
        if self.width < 0 or self.height < 0:
            raise ValueError("Window dimensions cannot be negative.")

    @property
    def geometry(self) -> tuple[int, int, int, int]:
        """Return the current window rectangle as ``(x, y, width, height)``."""
        return (self.x, self.y, self.width, self.height)


class WindowManager:
    """Enumerate and manage visible application windows without shell commands."""

    def __init__(self, monitor_manager: MonitorManager | None = None) -> None:
        self._monitor_manager = monitor_manager or MonitorManager()

    def get_windows(self) -> list[WindowInfo]:
        """Return visible, titled top-level application windows."""
        windows: list[WindowInfo] = []

        def collect(handle: int, _: object) -> bool:
            if not win32gui.IsWindowVisible(handle):
                return True
            title = win32gui.GetWindowText(handle).strip()
            if not title:
                return True
            info = self._window_info(handle, title)
            if info is not None:
                windows.append(info)
            return True

        try:
            win32gui.EnumWindows(collect, None)
        except OSError as error:
            logger.error("Window enumeration failed (%s).", type(error).__name__)
        return sorted(windows, key=lambda window: (window.title.casefold(), window.handle))

    def find_window(self, application_or_title: str) -> WindowInfo | None:
        """Find a visible window by title or process name using deterministic matching."""
        query = application_or_title.casefold().strip()
        if not query:
            return None
        exact_matches: list[WindowInfo] = []
        partial_matches: list[WindowInfo] = []
        for window in self.get_windows():
            title = window.title.casefold()
            process_name = (window.process_name or "").casefold()
            if query == title or query == process_name:
                exact_matches.append(window)
            elif query in title or query in process_name:
                partial_matches.append(window)
        matches = exact_matches or partial_matches
        return matches[0] if matches else None

    def maximize_window(self, window: WindowReference) -> CommandResult:
        """Maximize a known top-level window."""
        return self._show_window(window, win32con.SW_MAXIMIZE, "maximized")

    def minimize_window(self, window: WindowReference) -> CommandResult:
        """Minimize a known top-level window."""
        return self._show_window(window, win32con.SW_MINIMIZE, "minimized")

    def restore_window(self, window: WindowReference) -> CommandResult:
        """Restore a known top-level window from minimized or maximized state."""
        return self._show_window(window, win32con.SW_RESTORE, "restored")

    def move_window_to_monitor(
        self, window: WindowReference, monitor_index: int, *, maximize: bool = False
    ) -> CommandResult:
        """Move a window into a monitor's working area using real desktop geometry."""
        handle = self._valid_handle(window)
        if handle is None:
            return self._missing_window_result()
        monitor = self._monitor_manager.get_monitor(monitor_index)
        if monitor is None:
            return CommandResult.failure(
                "monitor_not_found",
                f"Monitor {monitor_index} is not available.",
                monitor_index=monitor_index,
            )

        try:
            if win32gui.IsIconic(handle) or self._is_maximized(handle):
                win32gui.ShowWindow(handle, win32con.SW_RESTORE)

            left, top, right, bottom = win32gui.GetWindowRect(handle)
            width, height = self._fit_dimensions(right - left, bottom - top, monitor)
            x = monitor.available_x + (monitor.available_width - width) // 2
            y = monitor.available_y + (monitor.available_height - height) // 2
            flags = win32con.SWP_NOZORDER | win32con.SWP_NOACTIVATE
            win32gui.SetWindowPos(handle, win32con.HWND_TOP, x, y, width, height, flags)
            if maximize:
                win32gui.ShowWindow(handle, win32con.SW_MAXIMIZE)
        except OSError as error:
            logger.error("Window move failed (%s).", type(error).__name__)
            return CommandResult.failure(
                "window_move_failed",
                "I couldn't move that window to the selected monitor.",
                monitor_index=monitor_index,
            )

        logger.info("Window moved to monitor %d.", monitor.index)
        return CommandResult.ok(
            f"Window moved to monitor {monitor.index}.",
            monitor_index=monitor.index,
            geometry=(x, y, width, height),
            maximized=maximize,
        )

    @staticmethod
    def _fit_dimensions(width: int, height: int, monitor: MonitorInfo) -> tuple[int, int]:
        safe_width = max(1, width)
        safe_height = max(1, height)
        return min(safe_width, monitor.available_width), min(safe_height, monitor.available_height)

    @staticmethod
    def _is_maximized(handle: int) -> bool:
        """Return whether Windows reports a maximized show state for *handle*."""
        return win32gui.GetWindowPlacement(handle)[1] == win32con.SW_SHOWMAXIMIZED

    def _show_window(self, window: WindowReference, command: int, action: str) -> CommandResult:
        handle = self._valid_handle(window)
        if handle is None:
            return self._missing_window_result()
        try:
            win32gui.ShowWindow(handle, command)
        except OSError as error:
            logger.error("Window %s failed (%s).", action, type(error).__name__)
            return CommandResult.failure(
                f"window_{action}_failed",
                f"I couldn't {action} that window.",
            )
        return CommandResult.ok(f"Window {action}.", handle=handle)

    @staticmethod
    def _valid_handle(window: WindowReference) -> int | None:
        handle = window.handle if isinstance(window, WindowInfo) else window
        if not isinstance(handle, int) or handle <= 0 or not win32gui.IsWindow(handle):
            return None
        return handle

    @staticmethod
    def _missing_window_result() -> CommandResult:
        return CommandResult.failure("window_not_found", "I couldn't find that window.")

    @staticmethod
    def _window_info(handle: int, title: str) -> WindowInfo | None:
        try:
            _, process_id = win32process.GetWindowThreadProcessId(handle)
            process_name = WindowManager._process_name(process_id)
            left, top, right, bottom = win32gui.GetWindowRect(handle)
            return WindowInfo(
                handle=handle,
                title=title,
                process_id=process_id,
                process_name=process_name,
                x=left,
                y=top,
                width=right - left,
                height=bottom - top,
            )
        except OSError:
            return None

    @staticmethod
    def _process_name(process_id: int) -> str | None:
        try:
            return psutil.Process(process_id).name()
        except (psutil.Error, OSError):
            return None
