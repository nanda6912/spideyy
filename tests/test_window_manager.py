import unittest
from unittest.mock import Mock, patch

from system.monitor_manager import MonitorInfo
from system.window_manager import WindowInfo, WindowManager


class WindowManagerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.primary = MonitorInfo(1, "Laptop", 0, 0, 1536, 864, True, 0, 0, 1536, 816)
        self.external = MonitorInfo(2, "External", -1024, -196, 1024, 1280, False, -1024, -196, 1024, 1232)
        self.monitor_manager = Mock()
        self.monitor_manager.get_monitor.side_effect = lambda index: {
            1: self.primary,
            2: self.external,
        }.get(index)
        self.manager = WindowManager(self.monitor_manager)
        self.window = WindowInfo(101, "Eclipse IDE", 456, "eclipse.exe", 20, 30, 800, 600)

    @patch("system.window_manager.win32process.GetWindowThreadProcessId", return_value=(1, 456))
    @patch("system.window_manager.win32gui.GetWindowRect", return_value=(20, 30, 820, 630))
    @patch("system.window_manager.win32gui.GetWindowText", side_effect=lambda handle: {10: "Eclipse IDE", 11: ""}[handle])
    @patch("system.window_manager.win32gui.IsWindowVisible", return_value=True)
    @patch("system.window_manager.win32gui.EnumWindows")
    @patch("system.window_manager.psutil.Process")
    def test_enumerates_visible_titled_windows(self, process, enum_windows, visible, title, rect, process_id) -> None:
        process.return_value.name.return_value = "eclipse.exe"
        enum_windows.side_effect = lambda callback, _: [callback(10, None), callback(11, None)]

        windows = self.manager.get_windows()

        self.assertEqual(len(windows), 1)
        self.assertEqual(windows[0].title, "Eclipse IDE")
        self.assertEqual(windows[0].process_id, 456)

    def test_finds_window_by_title_or_process_name(self) -> None:
        with patch.object(self.manager, "get_windows", return_value=[self.window]):
            self.assertEqual(self.manager.find_window("eclipse"), self.window)
            self.assertEqual(self.manager.find_window("eclipse.exe"), self.window)
            self.assertIsNone(self.manager.find_window("chrome"))

    @patch("system.window_manager.win32gui.IsWindow", return_value=True)
    @patch("system.window_manager.win32gui.SetWindowPos")
    @patch("system.window_manager.win32gui.GetWindowRect", return_value=(0, 0, 1200, 1400))
    @patch("system.window_manager.win32gui.GetWindowPlacement", return_value=(0, 1, (0, 0), (0, 0), (0, 0, 1200, 1400)))
    @patch("system.window_manager.win32gui.IsIconic", return_value=False)
    def test_moves_window_using_monitor_working_area(self, iconic, placement, rect, set_position, is_window) -> None:
        result = self.manager.move_window_to_monitor(self.window, 2)

        self.assertTrue(result.success)
        set_position.assert_called_once_with(101, 0, -1024, -196, 1024, 1232, 20)
        self.assertEqual(result.data["geometry"], (-1024, -196, 1024, 1232))

    @patch("system.window_manager.win32gui.IsWindow", return_value=True)
    def test_rejects_invalid_monitor_and_missing_window(self, is_window) -> None:
        invalid_monitor = self.manager.move_window_to_monitor(self.window, 99)
        with patch("system.window_manager.win32gui.IsWindow", return_value=False):
            missing_window = self.manager.move_window_to_monitor(self.window, 1)

        self.assertEqual(invalid_monitor.error_code, "monitor_not_found")
        self.assertEqual(missing_window.error_code, "window_not_found")

    @patch("system.window_manager.win32gui.IsWindow", return_value=True)
    @patch("system.window_manager.win32gui.ShowWindow", side_effect=OSError("denied"))
    def test_handles_maximize_minimize_and_restore_failures(self, show_window, is_window) -> None:
        self.assertEqual(self.manager.maximize_window(self.window).error_code, "window_maximized_failed")
        self.assertEqual(self.manager.minimize_window(self.window).error_code, "window_minimized_failed")
        self.assertEqual(self.manager.restore_window(self.window).error_code, "window_restored_failed")


# ── Phase 5A tests ──────────────────────────────────────────────────────────

class GetActiveWindowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.monitor_manager = Mock()
        self.monitor_manager.get_monitors.return_value = []
        self.manager = WindowManager(self.monitor_manager)

    @patch("system.window_manager.win32process.GetWindowThreadProcessId", return_value=(1, 99))
    @patch("system.window_manager.win32gui.GetWindowRect", return_value=(0, 0, 800, 600))
    @patch("system.window_manager.win32gui.GetWindowText", return_value="Notepad")
    @patch("system.window_manager.win32gui.IsWindow", return_value=True)
    @patch("system.window_manager.win32gui.GetForegroundWindow", return_value=42)
    @patch("system.window_manager.psutil.Process")
    def test_returns_active_window_info(self, process, fg, is_window, title, rect, pid) -> None:
        process.return_value.name.return_value = "notepad.exe"
        result = self.manager.get_active_window()
        self.assertIsNotNone(result)
        self.assertEqual(result.title, "Notepad")
        self.assertEqual(result.handle, 42)

    @patch("system.window_manager.win32gui.GetForegroundWindow", return_value=0)
    def test_returns_none_when_no_foreground_window(self, fg) -> None:
        result = self.manager.get_active_window()
        self.assertIsNone(result)

    @patch("system.window_manager.win32gui.IsWindow", return_value=False)
    @patch("system.window_manager.win32gui.GetForegroundWindow", return_value=999)
    def test_returns_none_for_invalid_handle(self, fg, is_window) -> None:
        result = self.manager.get_active_window()
        self.assertIsNone(result)

    @patch("system.window_manager.win32gui.GetForegroundWindow", side_effect=OSError("access denied"))
    def test_returns_none_on_os_error(self, fg) -> None:
        result = self.manager.get_active_window()
        self.assertIsNone(result)


class ListOpenWindowsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.monitor_manager = Mock()
        self.manager = WindowManager(self.monitor_manager)
        self.normal = WindowInfo(10, "Chrome", 1, "chrome.exe", 0, 0, 1024, 768)
        self.taskbar = WindowInfo(11, "Taskbar", 2, None, 0, 840, 1536, 40)
        self.zero_size = WindowInfo(12, "Helper", 3, None, 0, 0, 0, 0)

    @patch("system.window_manager.win32gui.GetClassName")
    def test_filters_system_class_windows(self, get_class) -> None:
        get_class.side_effect = lambda h: {10: "Chrome_WidgetWin_1", 11: "Shell_TrayWnd"}[h]
        with patch.object(self.manager, "get_windows", return_value=[self.normal, self.taskbar]):
            result = self.manager.list_open_windows()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].title, "Chrome")

    @patch("system.window_manager.win32gui.GetClassName", return_value="Chrome_WidgetWin_1")
    def test_filters_zero_size_windows(self, get_class) -> None:
        with patch.object(self.manager, "get_windows", return_value=[self.normal, self.zero_size]):
            result = self.manager.list_open_windows()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].handle, 10)

    @patch("system.window_manager.win32gui.GetClassName", return_value="Chrome_WidgetWin_1")
    def test_returns_all_usable_windows(self, get_class) -> None:
        w1 = WindowInfo(20, "Firefox", 4, "firefox.exe", 0, 0, 800, 600)
        w2 = WindowInfo(21, "Notepad", 5, "notepad.exe", 0, 0, 640, 480)
        with patch.object(self.manager, "get_windows", return_value=[w1, w2]):
            result = self.manager.list_open_windows()
        self.assertEqual(len(result), 2)

    @patch("system.window_manager.win32gui.GetClassName", return_value="SomeClass")
    def test_returns_empty_when_no_windows(self, get_class) -> None:
        with patch.object(self.manager, "get_windows", return_value=[]):
            result = self.manager.list_open_windows()
        self.assertEqual(result, [])


class ActivateWindowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.monitor_manager = Mock()
        self.manager = WindowManager(self.monitor_manager)
        self.window = WindowInfo(50, "Chrome", 1, "chrome.exe", 0, 0, 800, 600)

    @patch("system.window_manager.win32gui.SetForegroundWindow")
    @patch("system.window_manager.win32gui.IsIconic", return_value=False)
    @patch("system.window_manager.win32gui.IsWindow", return_value=True)
    def test_activates_window_successfully(self, is_window, iconic, set_fg) -> None:
        result = self.manager.activate_window(self.window)
        self.assertTrue(result.success)
        self.assertEqual(result.message, "Window activated.")
        set_fg.assert_called_once_with(50)

    @patch("system.window_manager.win32gui.ShowWindow")
    @patch("system.window_manager.win32gui.SetForegroundWindow")
    @patch("system.window_manager.win32gui.IsIconic", return_value=True)
    @patch("system.window_manager.win32gui.IsWindow", return_value=True)
    def test_restores_minimized_window_before_activating(self, is_window, iconic, set_fg, show) -> None:
        result = self.manager.activate_window(self.window)
        self.assertTrue(result.success)
        show.assert_called_once()

    @patch("system.window_manager.win32gui.SetForegroundWindow", side_effect=OSError("denied"))
    @patch("system.window_manager.win32gui.IsIconic", return_value=False)
    @patch("system.window_manager.win32gui.IsWindow", return_value=True)
    def test_returns_failure_on_os_error(self, is_window, iconic, set_fg) -> None:
        result = self.manager.activate_window(self.window)
        self.assertFalse(result.success)
        self.assertEqual(result.error_code, "window_activate_failed")

    @patch("system.window_manager.win32gui.IsWindow", return_value=False)
    def test_returns_not_found_for_invalid_handle(self, is_window) -> None:
        result = self.manager.activate_window(self.window)
        self.assertEqual(result.error_code, "window_not_found")


class GetWindowMonitorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.primary = MonitorInfo(1, "Laptop", 0, 0, 1536, 864, True, 0, 0, 1536, 816)
        self.external = MonitorInfo(2, "External", 1536, 0, 1920, 1080, False, 1536, 0, 1920, 1080)
        self.monitor_manager = Mock()
        self.monitor_manager.get_monitors.return_value = [self.primary, self.external]
        self.manager = WindowManager(self.monitor_manager)
        self.window = WindowInfo(60, "Chrome", 1, "chrome.exe", 100, 100, 800, 600)

    @patch("system.window_manager.win32gui.GetWindowRect", return_value=(100, 100, 900, 700))
    @patch("system.window_manager.win32gui.IsWindow", return_value=True)
    def test_identifies_monitor_by_window_centre(self, is_window, get_rect) -> None:
        # Centre is (500, 400) which is inside primary monitor (0,0,1536,816)
        result = self.manager.get_window_monitor(self.window)
        self.assertIsNotNone(result)
        self.assertEqual(result.index, 1)

    @patch("system.window_manager.win32gui.GetWindowRect", return_value=(1700, 100, 2500, 700))
    @patch("system.window_manager.win32gui.IsWindow", return_value=True)
    def test_identifies_external_monitor(self, is_window, get_rect) -> None:
        # Centre is (2100, 400) which is inside external monitor (1536,0,3456,1080)
        result = self.manager.get_window_monitor(self.window)
        self.assertIsNotNone(result)
        self.assertEqual(result.index, 2)

    @patch("system.window_manager.win32gui.IsWindow", return_value=False)
    def test_returns_none_for_invalid_handle(self, is_window) -> None:
        result = self.manager.get_window_monitor(self.window)
        self.assertIsNone(result)

    @patch("system.window_manager.win32gui.GetWindowRect", side_effect=OSError("API failure"))
    @patch("system.window_manager.win32gui.IsWindow", return_value=True)
    def test_returns_none_on_os_error(self, is_window, get_rect) -> None:
        result = self.manager.get_window_monitor(self.window)
        self.assertIsNone(result)


class IsApplicationOpenTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manager = WindowManager(Mock())
        self.window = WindowInfo(70, "Google Chrome", 1, "chrome.exe", 0, 0, 800, 600)

    def test_returns_true_when_window_found(self) -> None:
        with patch.object(self.manager, "find_window", return_value=self.window):
            self.assertTrue(self.manager.is_application_open("chrome"))

    def test_returns_false_when_no_window(self) -> None:
        with patch.object(self.manager, "find_window", return_value=None):
            self.assertFalse(self.manager.is_application_open("firefox"))


class FocusAndCloseWindowTests(unittest.TestCase):
    """Phase 5C-1 unit tests for WindowManager focus_window and close_window."""

    def setUp(self) -> None:
        self.monitor_manager = Mock()
        self.manager = WindowManager(self.monitor_manager)
        self.window = WindowInfo(80, "Google Chrome", 10, "chrome.exe", 0, 0, 800, 600)

    @patch("system.window_manager.win32gui.SetForegroundWindow")
    @patch("system.window_manager.win32gui.IsIconic", return_value=False)
    @patch("system.window_manager.win32gui.IsWindow", return_value=True)
    def test_focus_window_success(self, is_window, iconic, set_fg) -> None:
        result = self.manager.focus_window(self.window)
        self.assertTrue(result.success)
        set_fg.assert_called_once_with(80)

    @patch("system.window_manager.win32gui.IsWindow", return_value=False)
    def test_focus_window_invalid_hwnd(self, is_window) -> None:
        result = self.manager.focus_window(self.window)
        self.assertFalse(result.success)
        self.assertEqual(result.error_code, "window_not_found")

    @patch("system.window_manager.win32gui.SetForegroundWindow", side_effect=RuntimeError("API error"))
    @patch("system.window_manager.win32gui.IsIconic", return_value=False)
    @patch("system.window_manager.win32gui.IsWindow", return_value=True)
    def test_focus_window_api_failure(self, is_window, iconic, set_fg) -> None:
        result = self.manager.focus_window(self.window)
        self.assertFalse(result.success)
        self.assertEqual(result.error_code, "window_activate_failed")

    @patch("system.window_manager.win32gui.PostMessage")
    @patch("system.window_manager.win32gui.IsWindow", return_value=True)
    def test_close_window_success_uses_wm_close(self, is_window, post_msg) -> None:
        result = self.manager.close_window(self.window)
        self.assertTrue(result.success)
        # WM_CLOSE is win32con.WM_CLOSE (16)
        post_msg.assert_called_once_with(80, 16, 0, 0)

    @patch("system.window_manager.win32gui.IsWindow", return_value=False)
    def test_close_window_invalid_hwnd(self, is_window) -> None:
        result = self.manager.close_window(self.window)
        self.assertFalse(result.success)
        self.assertEqual(result.error_code, "window_not_found")

    @patch("system.window_manager.win32gui.PostMessage", side_effect=RuntimeError("PostMessage failed"))
    @patch("system.window_manager.win32gui.IsWindow", return_value=True)
    def test_close_window_api_failure(self, is_window, post_msg) -> None:
        result = self.manager.close_window(self.window)
        self.assertFalse(result.success)
        self.assertEqual(result.error_code, "window_close_failed")


class Phase5C2WindowManagerTests(unittest.TestCase):
    """Phase 5C-2 unit tests for discovery hardening and window inspection."""

    def setUp(self) -> None:
        self.monitor_manager = Mock()
        self.manager = WindowManager(self.monitor_manager)
        self.win1 = WindowInfo(10, "Google Chrome - Tab 1", 100, "chrome.exe", 0, 0, 800, 600)
        self.win2 = WindowInfo(20, "Google Chrome - Tab 2", 100, "chrome.exe", 0, 0, 800, 600)
        self.win3 = WindowInfo(30, "Visual Studio Code", 200, "code.exe", 0, 0, 800, 600)

    def test_find_windows_returns_deterministic_matches(self) -> None:
        with patch.object(self.manager, "get_windows", return_value=[self.win2, self.win1, self.win3]):
            matches = self.manager.find_windows("chrome")
            self.assertEqual(len(matches), 2)
            # Deterministically sorted by title: Tab 1 then Tab 2
            self.assertEqual(matches[0].handle, 10)
            self.assertEqual(matches[1].handle, 20)

    def test_find_windows_empty_query(self) -> None:
        matches = self.manager.find_windows("")
        self.assertEqual(matches, [])

    @patch("system.window_manager.win32gui.IsWindow")
    def test_is_valid_window(self, mock_is_window) -> None:
        mock_is_window.return_value = True
        self.assertTrue(self.manager.is_valid_window(10))
        mock_is_window.return_value = False
        self.assertFalse(self.manager.is_valid_window(10))
        self.assertFalse(self.manager.is_valid_window(-1))

    @patch("system.window_manager.win32gui.IsIconic")
    @patch("system.window_manager.win32gui.IsWindow", return_value=True)
    def test_is_minimized(self, mock_is_window, mock_is_iconic) -> None:
        mock_is_iconic.return_value = True
        self.assertTrue(self.manager.is_minimized(10))
        mock_is_iconic.return_value = False
        self.assertFalse(self.manager.is_minimized(10))

    @patch("system.window_manager.win32gui.GetForegroundWindow", return_value=80)
    @patch("system.window_manager.win32gui.IsIconic", return_value=False)
    @patch("system.window_manager.win32gui.IsWindow", return_value=True)
    @patch("system.window_manager.win32gui.SetForegroundWindow")
    def test_focus_window_already_focused(self, mock_set_fg, mock_is_window, mock_iconic, mock_get_fg) -> None:
        win = WindowInfo(80, "Active Window", 1, "test.exe", 0, 0, 800, 600)
        result = self.manager.focus_window(win)
        self.assertTrue(result.success)
        self.assertEqual(result.message, "Window is already focused.")
        mock_set_fg.assert_not_called()

    @patch("system.window_manager.win32gui.IsWindow", return_value=True)
    @patch("system.window_manager.win32gui.GetWindowText", return_value="Google Chrome")
    @patch.object(WindowManager, "_window_info")
    def test_get_window_info_valid(self, mock_win_info, mock_text, mock_is_window) -> None:
        mock_win_info.return_value = self.win1
        info = self.manager.get_window_info(10)
        self.assertEqual(info, self.win1)

    @patch("system.window_manager.win32gui.IsWindow", return_value=False)
    def test_get_window_info_invalid(self, mock_is_window) -> None:
        info = self.manager.get_window_info(999)
        self.assertIsNone(info)


