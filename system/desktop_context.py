"""Read-only desktop context service for SPIDEYY Windows assistant."""

from __future__ import annotations

import logging
from typing import Any

import psutil

from core.models import CommandResult
from system.application_discovery import ApplicationRegistry, DiscoveredApplication
from system.monitor_manager import MonitorInfo, MonitorManager
from system.window_manager import WindowInfo, WindowManager

logger = logging.getLogger("jarvis.system.desktop_context")


class DesktopContextService:
    """Provides read-only desktop awareness and telemetry without state mutation."""

    def __init__(
        self,
        registry: ApplicationRegistry | None = None,
        window_manager: WindowManager | None = None,
        monitor_manager: MonitorManager | None = None,
    ) -> None:
        self._registry = registry or ApplicationRegistry()
        self._monitor_manager = monitor_manager or MonitorManager()
        self._window_manager = window_manager or WindowManager(self._monitor_manager)

    def get_active_window(self) -> CommandResult:
        """Report the title, handle, and process of the current foreground window."""
        try:
            window = self._window_manager.get_active_window()
            if window is None:
                return CommandResult.failure(
                    "no_active_window",
                    "I couldn't determine the active window.",
                )
            display_title = window.title or "an untitled window"
            return CommandResult.ok(
                f"The active window is {display_title}.",
                title=window.title,
                hwnd=window.handle,
                process_id=window.process_id,
                process_name=window.process_name,
            )
        except Exception as error:
            logger.error("get_active_window failed (%s).", type(error).__name__)
            return CommandResult.failure(
                "active_window_failed",
                "I couldn't determine the active window.",
            )

    def get_active_application(self) -> CommandResult:
        """Report the registered application owning the current foreground window."""
        try:
            window = self._window_manager.get_active_window()
            if window is None:
                return CommandResult.failure(
                    "no_active_window",
                    "I couldn't determine the active application.",
                )

            app: DiscoveredApplication | None = None
            if window.process_name:
                app = self._registry.match(window.process_name)
            if app is None and window.title:
                app = self._registry.match(window.title)

            if app is not None:
                display_name = app.name
            else:
                display_name = window.process_name or window.title or "an unknown application"

            return CommandResult.ok(
                f"{display_name} is the active application.",
                application=display_name,
                window_title=window.title,
                process_name=window.process_name,
            )
        except Exception as error:
            logger.error("get_active_application failed (%s).", type(error).__name__)
            return CommandResult.failure(
                "active_application_failed",
                "I couldn't determine the active application.",
            )

    def get_active_window_monitor(self) -> CommandResult:
        """Report which physical monitor contains the active window."""
        try:
            window = self._window_manager.get_active_window()
            if window is None:
                return CommandResult.failure(
                    "no_active_window",
                    "I couldn't determine the active window.",
                )

            monitor = self._window_manager.get_window_monitor(window)
            if monitor is None:
                return CommandResult.failure(
                    "monitor_not_found",
                    "I couldn't determine which monitor the active window is on.",
                )

            if monitor.name and monitor.name != f"Monitor {monitor.index}":
                message = f"The active window is on monitor {monitor.index}, {monitor.name}."
            else:
                message = f"The active window is on monitor {monitor.index}."

            return CommandResult.ok(
                message,
                monitor_index=monitor.index,
                monitor_name=monitor.name,
            )
        except Exception as error:
            logger.error("get_active_window_monitor failed (%s).", type(error).__name__)
            return CommandResult.failure(
                "monitor_determination_failed",
                "I couldn't determine which monitor the active window is on.",
            )

    def is_application_running(self, application_query: str) -> CommandResult:
        """Check whether a named application is currently running without launching it."""
        try:
            if not application_query or not application_query.strip():
                return CommandResult.failure(
                    "application_not_found",
                    "I couldn't find that application in the application registry.",
                )

            app = self._registry.match(application_query)
            if app is None:
                return CommandResult.failure(
                    "application_not_found",
                    "I couldn't find that application in the application registry.",
                )

            is_running = self._check_app_running(app, application_query)
            if is_running:
                return CommandResult.ok(
                    f"Yes, {app.name} is running.",
                    application=app.name,
                    is_running=True,
                )
            return CommandResult.ok(
                f"No, {app.name} is not running.",
                application=app.name,
                is_running=False,
            )
        except Exception as exc:
            logger.error("is_application_running failed: %s", exc, exc_info=True)
            return CommandResult.failure(
                "check_running_failed",
                "I couldn't check if that application is running.",
            )

    def get_open_applications(self) -> CommandResult:
        """Return a clean list of open desktop applications with visible windows."""
        try:
            windows = self._window_manager.list_open_windows()
            if not windows:
                return CommandResult.ok(
                    "I couldn't find any open applications.",
                    window_count=0,
                    applications=[],
                )

            apps: list[str] = []
            seen: set[str] = set()

            for window in windows:
                app = None
                if window.process_name:
                    app = self._registry.match(window.process_name)
                if app is None and window.title:
                    app = self._registry.match(window.title)

                name = app.name if app is not None else (window.title or window.process_name)
                if name and name not in seen:
                    seen.add(name)
                    apps.append(name)

            if not apps:
                return CommandResult.ok(
                    "I couldn't find any open applications.",
                    window_count=0,
                    applications=[],
                )

            if len(apps) == 1:
                summary = apps[0]
            elif len(apps) == 2:
                summary = f"{apps[0]} and {apps[1]}"
            else:
                summary = f"{', '.join(apps[:-1])}, and {apps[-1]}"

            return CommandResult.ok(
                f"Open applications are {summary}.",
                window_count=len(apps),
                applications=apps,
            )
        except Exception as error:
            logger.error("get_open_applications failed (%s).", type(error).__name__)
            return CommandResult.failure(
                "list_applications_failed",
                "I couldn't list open applications.",
            )

    def get_open_windows(self) -> CommandResult:
        """Return a structured list of open desktop windows with title, handle, and monitor."""
        try:
            windows = self._window_manager.list_open_windows()
            if not windows:
                return CommandResult.ok(
                    "I couldn't find any open windows.",
                    window_count=0,
                    windows=[],
                )

            details: list[dict[str, Any]] = []
            summaries: list[str] = []

            for window in windows:
                app = None
                if window.process_name:
                    app = self._registry.match(window.process_name)
                if app is None and window.title:
                    app = self._registry.match(window.title)

                app_name = app.name if app is not None else (window.process_name or "Unknown")
                monitor = self._window_manager.get_window_monitor(window)
                monitor_idx = monitor.index if monitor is not None else None

                details.append({
                    "application": app_name,
                    "title": window.title,
                    "process_name": window.process_name,
                    "hwnd": window.handle,
                    "monitor_index": monitor_idx,
                })

                if monitor_idx is not None:
                    summaries.append(f"{window.title} on monitor {monitor_idx}")
                else:
                    summaries.append(window.title)

            if len(summaries) == 1:
                summary = summaries[0]
            elif len(summaries) == 2:
                summary = f"{summaries[0]} and {summaries[1]}"
            elif len(summaries) <= 4:
                summary = f"{', '.join(summaries[:-1])}, and {summaries[-1]}"
            else:
                summary = f"{', '.join(summaries[:3])}, and {len(summaries) - 3} more"

            return CommandResult.ok(
                f"Open windows: {summary}.",
                window_count=len(details),
                windows=details,
            )
        except Exception as error:
            logger.error("get_open_windows failed (%s).", type(error).__name__)
            return CommandResult.failure(
                "list_windows_failed",
                "I couldn't list open windows.",
            )

    def locate_application(self, application_query: str) -> CommandResult:
        """Locate an application's visible window and monitor placement."""
        try:
            if not application_query or not application_query.strip():
                return CommandResult.failure(
                    "application_not_found",
                    "I couldn't find that application in the application registry.",
                )

            app = self._registry.match(application_query)
            if app is None:
                return CommandResult.failure(
                    "application_not_found",
                    "I couldn't find that application in the application registry.",
                )

            window: WindowInfo | None = None
            for candidate in (app.name, *app.aliases, application_query):
                window = self._window_manager.find_window(candidate)
                if window is not None:
                    break

            if window is not None:
                monitor = self._window_manager.get_window_monitor(window)
                if monitor is not None:
                    return CommandResult.ok(
                        f"{app.name} is on monitor {monitor.index}.",
                        application=app.name,
                        is_running=True,
                        has_window=True,
                        monitor_index=monitor.index,
                    )
                return CommandResult.ok(
                    f"{app.name} is running, but I couldn't determine which monitor its window is on.",
                    application=app.name,
                    is_running=True,
                    has_window=True,
                    monitor_index=None,
                )

            # Check if process is running without a visible window
            is_proc_running = self._is_process_running_by_name(app.executable_path.name)
            if is_proc_running:
                return CommandResult.ok(
                    f"{app.name} is running, but I couldn't find a visible window.",
                    application=app.name,
                    is_running=True,
                    has_window=False,
                )

            return CommandResult.ok(
                f"{app.name} is not currently running.",
                application=app.name,
                is_running=False,
                has_window=False,
            )
        except Exception as error:
            logger.error("locate_application failed (%s).", type(error).__name__)
            return CommandResult.failure(
                "locate_application_failed",
                "I couldn't locate that application.",
            )

    def focus_application(self, application_query: str) -> CommandResult:
        """Resolve an application query to a visible window and bring it to the foreground."""
        try:
            if not application_query or not application_query.strip():
                return CommandResult.failure(
                    "application_not_found",
                    "I couldn't find that application in the application registry.",
                )

            app = self._registry.match(application_query)
            if app is None:
                return CommandResult.failure(
                    "application_not_found",
                    "I couldn't find that application in the application registry.",
                )

            # Gather all matching windows deterministically
            all_matching: list[WindowInfo] = []
            seen_handles: set[int] = set()
            candidates = (app.name, *app.aliases, application_query)
            find_fn = getattr(self._window_manager, "find_windows", None)
            found_via_multi = False
            if callable(find_fn):
                try:
                    for candidate in candidates:
                        res = find_fn(candidate)
                        if isinstance(res, (list, tuple)):
                            found_via_multi = True
                            for w in res:
                                if getattr(w, "handle", None) is not None and w.handle not in seen_handles:
                                    seen_handles.add(w.handle)
                                    all_matching.append(w)
                except Exception:
                    pass

            if not found_via_multi:
                for candidate in candidates:
                    w = self._window_manager.find_window(candidate)
                    if w is not None and getattr(w, "handle", None) is not None and w.handle not in seen_handles:
                        seen_handles.add(w.handle)
                        all_matching.append(w)

            # Selection rules:
            # 1. Prefer currently active foreground window if it matches
            active_window = self._window_manager.get_active_window()
            selected_window: WindowInfo | None = None
            if active_window is not None:
                if any(getattr(w, "handle", None) == getattr(active_window, "handle", None) for w in all_matching):
                    selected_window = active_window
                else:
                    win_title = getattr(active_window, "title", "").casefold()
                    win_proc = (getattr(active_window, "process_name", "") or "").casefold()
                    cand_set = {c.casefold() for c in candidates}
                    if any(c in win_title or c in win_proc or win_proc == f"{c}.exe" for c in cand_set):
                        selected_window = active_window

            # 2. Prefer a visible, non-minimized matching window
            if selected_window is None and all_matching:
                is_min = getattr(self._window_manager, "is_minimized", None)
                if callable(is_min):
                    try:
                        non_minimized = [
                            w for w in all_matching
                            if isinstance(is_min(w.handle), bool) and not is_min(w.handle)
                        ]
                        if non_minimized:
                            selected_window = non_minimized[0]
                    except Exception:
                        pass

            # 3. Otherwise, use deterministic stable ordering
            if selected_window is None and all_matching:
                selected_window = all_matching[0]

            if selected_window is not None:
                res = self._window_manager.focus_window(selected_window)
                if res.success:
                    return CommandResult.ok(
                        f"Focusing {app.name}.",
                        application=app.name,
                        hwnd=selected_window.handle,
                    )
                return res

            # Check if process is running without a visible window
            is_proc_running = self._is_process_running_by_name(app.executable_path.name)
            if is_proc_running:
                return CommandResult.ok(
                    f"{app.name} is running, but I couldn't find a visible window.",
                    application=app.name,
                    is_running=True,
                    has_window=False,
                )

            return CommandResult.failure(
                "window_not_found",
                f"I couldn't find an open window for {app.name}.",
                application=app.name,
            )
        except Exception as error:
            logger.error("focus_application failed (%s).", type(error).__name__)
            return CommandResult.failure(
                "focus_application_failed",
                "I couldn't focus that application.",
            )

    def _check_app_running(self, app: DiscoveredApplication, query: str) -> bool:
        """Return True if an application process or window is detected."""
        for candidate in (app.name, *app.aliases, query):
            if self._window_manager.is_application_open(candidate):
                return True
        return self._is_process_running_by_name(app.executable_path.name)

    @staticmethod
    def _is_process_running_by_name(exe_name: str) -> bool:
        """Return True if an OS process matching *exe_name* is running."""
        if not exe_name:
            return False
        target = str(exe_name).casefold()
        try:
            for proc in psutil.process_iter(["name"]):
                try:
                    info = proc.info
                    name = info.get("name") if isinstance(info, dict) else None
                    if name and str(name).casefold() == target:
                        return True
                except Exception:
                    continue
        except Exception as error:
            logger.error("_is_process_running_by_name failed (%s).", type(error).__name__)
        return False
