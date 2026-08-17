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
