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
        except Exception as error:
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

    def get_active_window(self) -> WindowInfo | None:
        """Return the currently focused top-level window, or None if unavailable."""
        try:
            handle = win32gui.GetForegroundWindow()
        except Exception as error:
            logger.error("GetForegroundWindow failed (%s).", type(error).__name__)
            return None
        if not handle or not win32gui.IsWindow(handle):
            return None
        title = ""
        try:
            title = win32gui.GetWindowText(handle).strip()
        except Exception:
            pass
        return self._window_info(handle, title or "(unknown)")

    def list_open_windows(self) -> list[WindowInfo]:
        """Return a filtered list of visible, usable, titled top-level windows.

        Applies extra filtering on top of ``get_windows`` to remove obvious
        system helper windows (zero-size, system-class, or untitled).
        """
        results: list[WindowInfo] = []
        for window in self.get_windows():
            # Skip windows with no meaningful size (invisible helpers).
            if window.width <= 0 or window.height <= 0:
                continue
            # Skip obvious Windows internals by class name.
            try:
                class_name = win32gui.GetClassName(window.handle)
            except OSError:
                class_name = ""
            if class_name in {
                "Shell_TrayWnd",        # taskbar
                "Progman",              # desktop
                "WorkerW",              # desktop worker
                "DV2ControlHost",       # start menu host
                "ApplicationFrameWindow",  # some UWP wrappers
            }:
                continue
            results.append(window)
        return results

    def activate_window(self, window: WindowReference) -> CommandResult:
        """Bring a window to the foreground and give it keyboard focus."""
        handle = self._valid_handle(window)
        if handle is None:
            return self._missing_window_result()
        try:
            # Restore if minimized before activating.
            if win32gui.IsIconic(handle):
                win32gui.ShowWindow(handle, win32con.SW_RESTORE)
            win32gui.SetForegroundWindow(handle)
        except Exception as error:
            logger.error("SetForegroundWindow failed (%s).", type(error).__name__)
            return CommandResult.failure(
                "window_activate_failed",
                "I couldn't activate that window.",
            )
        return CommandResult.ok("Window activated.", handle=handle)

    def focus_window(self, window: WindowReference) -> CommandResult:
        """Bring a window to the foreground and give it keyboard focus."""
        return self.activate_window(window)

    def close_window(self, window: WindowReference) -> CommandResult:
        """Request normal window closure using Windows WM_CLOSE message.

        Does NOT call TerminateProcess, taskkill, or kill the process.
        """
        handle = self._valid_handle(window)
        if handle is None:
            return self._missing_window_result()
        try:
            win32gui.PostMessage(handle, win32con.WM_CLOSE, 0, 0)
        except Exception as error:
            logger.error("WM_CLOSE PostMessage failed (%s).", type(error).__name__)
            return CommandResult.failure(
                "window_close_failed",
                "I couldn't close that window.",
            )
        return CommandResult.ok("Window close requested.", handle=handle)

    def get_window_monitor(self, window: WindowReference) -> MonitorInfo | None:
        """Return the ``MonitorInfo`` that contains the majority of *window*.

        Uses the window's current rect and asks MonitorManager for the monitor
        whose working area overlaps most with the window centre point.
        Returns ``None`` if no monitor can be determined or the handle is invalid.
        """
        handle = self._valid_handle(window)
        if handle is None:
            return None
        try:
            left, top, right, bottom = win32gui.GetWindowRect(handle)
        except OSError as error:
            logger.error("GetWindowRect failed (%s).", type(error).__name__)
            return None
        centre_x = (left + right) // 2
        centre_y = (top + bottom) // 2
        for monitor in self._monitor_manager.get_monitors():
            mx = monitor.available_x
            my = monitor.available_y
            mw = monitor.available_width
            mh = monitor.available_height
            if mx <= centre_x < mx + mw and my <= centre_y < my + mh:
                return monitor
        # Fallback: check any overlap with window bounds across all monitors.
        for monitor in self._monitor_manager.get_monitors():
            mx = monitor.available_x
            my = monitor.available_y
            mw = monitor.available_width
            mh = monitor.available_height
            if left < mx + mw and right > mx and top < my + mh and bottom > my:
                return monitor
        return None

    def is_application_open(self, query: str) -> bool:
        """Return ``True`` when a visible window matching *query* exists."""
        return self.find_window(query) is not None

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
            width = max(0, right - left)
            height = max(0, bottom - top)
            return WindowInfo(
                handle=handle,
                title=title,
                process_id=process_id,
                process_name=process_name,
                x=left,
                y=top,
                width=width,
                height=height,
            )
        except Exception:
            return None

    @staticmethod
    def _process_name(process_id: int) -> str | None:
        try:
            return psutil.Process(process_id).name()
        except (psutil.Error, OSError):
            return None
