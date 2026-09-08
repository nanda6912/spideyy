"""Unit tests for DesktopContextService."""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from core.models import CommandResult
from system.application_discovery import DiscoveredApplication
from system.desktop_context import DesktopContextService
from system.monitor_manager import MonitorInfo
from system.window_manager import WindowInfo


class DesktopContextServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.chrome_app = DiscoveredApplication.create(
            "Google Chrome", Path("C:/Apps/chrome.exe"), source="test"
        )
        self.vscode_app = DiscoveredApplication.create(
            "Visual Studio Code", Path("C:/Apps/code.exe"), source="test"
        )

        self.registry = Mock()
        self.registry.match.side_effect = lambda query: {
            "chrome.exe": self.chrome_app,
            "chrome": self.chrome_app,
            "google chrome": self.chrome_app,
            "code.exe": self.vscode_app,
            "vscode": self.vscode_app,
            "visual studio code": self.vscode_app,
        }.get(query.casefold() if isinstance(query, str) else query)

        self.monitor1 = MonitorInfo(1, "Primary Display", 0, 0, 1920, 1080, True, 0, 0, 1920, 1040)
        self.monitor2 = MonitorInfo(2, "DELL 1908FP", 1920, 0, 1280, 1024, False, 1920, 0, 1280, 1024)

        self.monitor_manager = Mock()
        self.monitor_manager.get_monitors.return_value = [self.monitor1, self.monitor2]

        self.active_window = WindowInfo(100, "Google Chrome - New Tab", 1234, "chrome.exe", 10, 10, 800, 600)
        self.vscode_window = WindowInfo(101, "main.py - Visual Studio Code", 5678, "code.exe", 1930, 10, 800, 600)

        self.window_manager = Mock()
        self.window_manager.get_active_window.return_value = self.active_window
        self.window_manager.get_window_monitor.return_value = self.monitor1
        self.window_manager.list_open_windows.return_value = [self.active_window, self.vscode_window]
        self.window_manager.is_application_open.side_effect = lambda q: q.casefold() in {"chrome", "google chrome", "code", "vscode"}
        self.window_manager.find_window.side_effect = lambda q: (
            self.active_window if q.casefold() in {"chrome", "google chrome"} else (
                self.vscode_window if q.casefold() in {"vscode", "visual studio code", "code"} else None
            )
        )

        self.service = DesktopContextService(
            registry=self.registry,
            window_manager=self.window_manager,
            monitor_manager=self.monitor_manager,
        )

    # 1. Active window detected
    def test_1_get_active_window_detected(self) -> None:
        result = self.service.get_active_window()
        self.assertTrue(result.success)
        self.assertIn("Google Chrome - New Tab", result.message)
        self.assertEqual(result.data["hwnd"], 100)
        self.assertEqual(result.data["process_name"], "chrome.exe")

    # 2. Active window unavailable
    def test_2_get_active_window_unavailable(self) -> None:
        self.window_manager.get_active_window.return_value = None
        result = self.service.get_active_window()
        self.assertFalse(result.success)
        self.assertEqual(result.error_code, "no_active_window")
        self.assertIn("couldn't determine", result.message)

    # 3. Active application resolved
    def test_3_get_active_application_resolved(self) -> None:
        result = self.service.get_active_application()
        self.assertTrue(result.success)
        self.assertEqual(result.data["application"], "Google Chrome")
        self.assertIn("Google Chrome is the active application", result.message)

    # 4. Unknown active executable
    def test_4_get_active_application_unknown_executable(self) -> None:
        unknown_window = WindowInfo(200, "Secret Tool", 9999, "unknown_tool.exe", 0, 0, 500, 500)
        self.window_manager.get_active_window.return_value = unknown_window
        self.registry.match.return_value = None

        result = self.service.get_active_application()
        self.assertTrue(result.success)
        self.assertEqual(result.data["application"], "unknown_tool.exe")
        self.assertIn("unknown_tool.exe is the active application", result.message)

    # 5. Active monitor detected
    def test_5_get_active_window_monitor_detected(self) -> None:
        self.window_manager.get_window_monitor.return_value = self.monitor2
        result = self.service.get_active_window_monitor()
        self.assertTrue(result.success)
        self.assertEqual(result.data["monitor_index"], 2)
        self.assertIn("monitor 2, DELL 1908FP", result.message)

    # 6. Monitor unavailable
    def test_6_get_active_window_monitor_unavailable(self) -> None:
        self.window_manager.get_window_monitor.return_value = None
        result = self.service.get_active_window_monitor()
        self.assertFalse(result.success)
        self.assertEqual(result.error_code, "monitor_not_found")

    # 7. Application running
    def test_7_is_application_running_yes(self) -> None:
        result = self.service.is_application_running("chrome")
        self.assertTrue(result.success)
        self.assertTrue(result.data["is_running"])
        self.assertIn("Yes, Google Chrome is running", result.message)

    # 8. Application not running
    @patch("system.desktop_context.psutil.process_iter", return_value=[])
    def test_8_is_application_running_no(self, mock_proc) -> None:
        self.window_manager.is_application_open.side_effect = None
        self.window_manager.is_application_open.return_value = False
        result = self.service.is_application_running("vscode")
        self.assertTrue(result.success)
        self.assertFalse(result.data["is_running"])
        self.assertIn("No, Visual Studio Code is not running", result.message)

    # 9. Unknown application
    def test_9_is_application_running_unknown(self) -> None:
        result = self.service.is_application_running("nonexistent_app")
        self.assertFalse(result.success)
        self.assertEqual(result.error_code, "application_not_found")

    # 10. Open application list
    def test_10_get_open_applications(self) -> None:
        result = self.service.get_open_applications()
        self.assertTrue(result.success)
        self.assertEqual(result.data["window_count"], 2)
        self.assertEqual(result.data["applications"], ["Google Chrome", "Visual Studio Code"])
        self.assertIn("Google Chrome and Visual Studio Code", result.message)

    # 11. Duplicate applications deduplicated
    def test_11_get_open_applications_deduplicated(self) -> None:
        chrome2 = WindowInfo(102, "Google Chrome - Tab 2", 1234, "chrome.exe", 10, 10, 800, 600)
        self.window_manager.list_open_windows.return_value = [self.active_window, chrome2, self.vscode_window]

        result = self.service.get_open_applications()
        self.assertTrue(result.success)
        self.assertEqual(result.data["applications"], ["Google Chrome", "Visual Studio Code"])
        self.assertEqual(result.data["window_count"], 2)

    # 12. Locate running application
    def test_12_locate_running_application(self) -> None:
        self.window_manager.get_window_monitor.return_value = self.monitor2
        result = self.service.locate_application("vscode")
        self.assertTrue(result.success)
        self.assertTrue(result.data["is_running"])
        self.assertTrue(result.data["has_window"])
        self.assertEqual(result.data["monitor_index"], 2)
        self.assertIn("Visual Studio Code is on monitor 2", result.message)

    # 13. Locate stopped application
    @patch("system.desktop_context.psutil.process_iter", return_value=[])
    def test_13_locate_stopped_application(self, mock_proc) -> None:
        self.window_manager.is_application_open.side_effect = None
        self.window_manager.is_application_open.return_value = False
        self.window_manager.find_window.side_effect = None
        self.window_manager.find_window.return_value = None
        result = self.service.locate_application("vscode")
        self.assertTrue(result.success)
        self.assertFalse(result.data["is_running"])
        self.assertFalse(result.data["has_window"])
        self.assertIn("Visual Studio Code is not currently running", result.message)

    # 14. Running application with no visible window
    def test_14_locate_running_application_no_visible_window(self) -> None:
        self.window_manager.is_application_open.side_effect = None
        self.window_manager.is_application_open.return_value = False
        self.window_manager.find_window.side_effect = None
        self.window_manager.find_window.return_value = None
        mock_proc = Mock()
        mock_proc.info = {"name": "code.exe"}

        with patch("system.desktop_context.psutil.process_iter", return_value=[mock_proc]):
            result = self.service.locate_application("vscode")

        self.assertTrue(result.success)
        self.assertTrue(result.data["is_running"])
        self.assertFalse(result.data["has_window"])
        self.assertIn("running, but I couldn't find a visible window", result.message)

    # 15. Service exceptions converted into safe results
    def test_15_service_exceptions_handled_safely(self) -> None:
        self.window_manager.get_active_window.side_effect = RuntimeError("OS API failure")
        result = self.service.get_active_window()
        self.assertFalse(result.success)
        self.assertEqual(result.error_code, "active_window_failed")
        self.assertIn("couldn't determine", result.message)

    # 16. Focus application success
    def test_16_focus_application_success(self) -> None:
        self.window_manager.focus_window.return_value = CommandResult.ok("Focusing Google Chrome.")
        result = self.service.focus_application("chrome")
        self.assertTrue(result.success)
        self.assertIn("Focusing Google Chrome", result.message)
        self.window_manager.focus_window.assert_called_once()

    # 17. Focus application no visible window
    def test_17_focus_application_no_visible_window(self) -> None:
        self.window_manager.get_active_window.return_value = None
        self.window_manager.find_window.side_effect = None
        self.window_manager.find_window.return_value = None
        self.window_manager.focus_window.return_value = CommandResult.ok("Focusing Google Chrome.")
        with patch("system.desktop_context.psutil.process_iter", return_value=[]):
            result = self.service.focus_application("chrome")
        self.assertFalse(result.success)
        self.assertEqual(result.error_code, "window_not_found")
        self.assertIn("couldn't find an open window", result.message)

    # 18. Focus application running but no visible window
    def test_18_focus_application_running_no_visible_window(self) -> None:
        self.window_manager.get_active_window.return_value = None
        self.window_manager.find_window.side_effect = None
        self.window_manager.find_window.return_value = None
        mock_proc = Mock()
        mock_proc.info = {"name": "chrome.exe"}
        with patch("system.desktop_context.psutil.process_iter", return_value=[mock_proc]):
            result = self.service.focus_application("chrome")
        self.assertTrue(result.success)
        self.assertIn("running, but I couldn't find a visible window", result.message)

    # 19. Focus application unknown
    def test_19_focus_application_unknown(self) -> None:
        self.registry.match.return_value = None
        result = self.service.focus_application("unknown_app")
        self.assertFalse(result.success)
        self.assertEqual(result.error_code, "application_not_found")

    # 20. Focus application prefers active matching window
    def test_20_focus_application_prefers_active_window(self) -> None:
        self.window_manager.get_active_window.return_value = self.active_window
        self.window_manager.focus_window.return_value = CommandResult.ok("Focusing Google Chrome.")
        result = self.service.focus_application("chrome")
        self.assertTrue(result.success)
        # Should focus the active window since it matches
        self.window_manager.focus_window.assert_called_once()

    # 21. Focus application API failure
    def test_21_focus_application_api_failure(self) -> None:
        self.window_manager.focus_window.return_value = CommandResult.failure("window_activate_failed", "Failed to focus.")
        result = self.service.focus_application("chrome")
        self.assertFalse(result.success)
        self.assertEqual(result.error_code, "window_activate_failed")

    # 22. Get open windows with structured details
    def test_22_get_open_windows_with_details(self) -> None:
        result = self.service.get_open_windows()
        self.assertTrue(result.success)
        self.assertEqual(result.data["window_count"], 2)
        windows = result.data["windows"]
        self.assertEqual(len(windows), 2)
        self.assertEqual(windows[0]["application"], "Google Chrome")
        self.assertEqual(windows[0]["hwnd"], 100)
        self.assertEqual(windows[0]["monitor_index"], 1)
        self.assertIn("Google Chrome - New Tab on monitor 1", result.message)

    # 23. Get open windows when none open
    def test_23_get_open_windows_empty(self) -> None:
        self.window_manager.list_open_windows.return_value = []
        result = self.service.get_open_windows()
        self.assertTrue(result.success)
        self.assertEqual(result.data["window_count"], 0)
        self.assertEqual(result.data["windows"], [])
        self.assertIn("couldn't find any open windows", result.message)

    # 24. Focus application prefers non-minimized matching window
    def test_24_focus_application_prefers_non_minimized(self) -> None:
        self.window_manager.get_active_window.return_value = None
        minimized_win = WindowInfo(101, "Google Chrome - Minimized", 1234, "chrome.exe", 0, 0, 800, 600)
        normal_win = WindowInfo(102, "Google Chrome - Visible", 1234, "chrome.exe", 0, 0, 800, 600)
        self.window_manager.find_windows.return_value = [minimized_win, normal_win]
        self.window_manager.is_minimized.side_effect = lambda hwnd: hwnd == 101
        self.window_manager.focus_window.return_value = CommandResult.ok("Focusing Google Chrome.")

        result = self.service.focus_application("chrome")
        self.assertTrue(result.success)
        # Should have chosen normal_win (102) over minimized_win (101)
        self.window_manager.focus_window.assert_called_with(normal_win)


if __name__ == "__main__":
    unittest.main()

