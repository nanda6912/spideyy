import unittest
from pathlib import Path
from unittest.mock import Mock

from core.command_router import CommandRouter, normalize_command
from core.confirmation import ConfirmationManager
from core.models import CommandResult
from core.state import AssistantState, StateManager

from system.application_discovery import DiscoveredApplication
from system.monitor_manager import MonitorInfo
from system.window_manager import WindowInfo


class CommandRouterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.application = DiscoveredApplication.create(
            "Google Chrome", Path("chrome.exe"), source="test"
        )
        self.registry = Mock()
        self.registry.match.return_value = self.application
        self.registry.load_all.return_value = [self.application]
        self.launcher = Mock()
        self.launcher.launch.return_value = CommandResult.ok("Launching Google Chrome.")
        self.monitors = Mock()
        self.monitors.monitor_count.return_value = 2
        self.monitors.describe_monitors.return_value = "Monitor 1: Laptop, 1536x864, Primary"
        self.monitors.get_monitor.side_effect = lambda index: (
            MonitorInfo(index, "Display", 0, 0, 100, 100, index == 1, 0, 0, 100, 100)
            if index in {1, 2}
            else None
        )
        self.windows = Mock()
        self.window = WindowInfo(10, "Google Chrome", 101, "chrome.exe", 0, 0, 800, 600)
        self.windows.find_window.return_value = self.window
        self.windows.maximize_window.return_value = CommandResult.ok("Window maximized.")
        self.windows.minimize_window.return_value = CommandResult.ok("Window minimized.")
        self.windows.restore_window.return_value = CommandResult.ok("Window restored.")
        self.windows.move_window_to_monitor.return_value = CommandResult.ok("Window moved.")
        self.state = StateManager(AssistantState.LISTENING)
        self.router = CommandRouter(self.registry, self.launcher, self.monitors, self.windows, self.state)

    def test_normalizes_text_and_routes_application_commands(self) -> None:
        self.assertEqual(normalize_command("  OPEN   Chrome  "), "open chrome")
        for command in (
            "open chrome",
            "open google chrome",
            "open vscode",
            "open vs code",
            "open visual studio code",
            "open intellij",
            "open idea",
            "launch terminal",
            "launch windows terminal",
            "start eclipse",
        ):
            with self.subTest(command=command):
                result = self.router.route(command)
                self.assertTrue(result.success)
        self.assertEqual(self.launcher.launch.call_count, 10)

    def test_routes_monitor_commands(self) -> None:
        self.assertTrue(self.router.route("show monitors").success)
        self.assertTrue(self.router.route("list monitors").success)
        count = self.router.route("how many monitors")
        self.assertEqual(count.data["monitor_count"], 2)

    def test_routes_window_actions_and_alias_lookup(self) -> None:
        for command, method in (
            ("maximize chrome", self.windows.maximize_window),
            ("minimize google chrome", self.windows.minimize_window),
            ("restore chrome", self.windows.restore_window),
        ):
            with self.subTest(command=command):
                self.assertTrue(self.router.route(command).success)
                method.assert_called_with(self.window)

    def test_routes_move_commands_and_validates_monitor(self) -> None:
        for command, index in (
            ("move chrome to monitor 2", 2),
            ("move intellij to monitor 2", 2),
            ("move vscode to monitor 1", 1),
        ):
            with self.subTest(command=command):
                result = self.router.route(command)
                self.assertTrue(result.success)
                self.windows.move_window_to_monitor.assert_called_with(self.window, index)
        invalid = self.router.route("move chrome to monitor 9")
        self.assertEqual(invalid.error_code, "monitor_not_found")

    def test_handles_help_status_unknown_application_and_missing_window(self) -> None:
        self.assertTrue(self.router.route("help").success)
        self.assertTrue(self.router.route("what can you do").success)
        self.assertEqual(self.router.route("jarvis status").data["state"], "listening")
        self.assertEqual(self.router.route("dance now").error_code, "unknown_command")
        self.registry.match.return_value = None
        self.assertEqual(self.router.route("maximize unknown").error_code, "application_not_found")
        self.registry.match.return_value = self.application
        self.windows.find_window.return_value = None
        self.assertEqual(self.router.route("restore chrome").error_code, "window_not_found")

    def test_propagates_failed_operations(self) -> None:
        self.launcher.launch.return_value = CommandResult.failure("application_launch_failed", "Launch failed.")
        self.assertEqual(self.router.route("open chrome").error_code, "application_launch_failed")
        self.windows.maximize_window.return_value = CommandResult.failure("window_maximized_failed", "Failed.")
        self.assertEqual(self.router.route("maximize chrome").error_code, "window_maximized_failed")

    def test_routes_system_information_commands(self) -> None:
        sys_info = Mock()
        sys_info.get_cpu_usage.return_value = CommandResult.ok("CPU 20 percent.")
        sys_info.get_memory_usage.return_value = CommandResult.ok("Memory 50 percent.")
        sys_info.get_disk_usage.return_value = CommandResult.ok("Disk 40 percent.")
        sys_info.get_battery_status.return_value = CommandResult.ok("Battery 90 percent.")
        sys_info.get_current_time.return_value = CommandResult.ok("It is 10:00 AM.")
        sys_info.get_system_status.return_value = CommandResult.ok("System status summary.")

        router = CommandRouter(
            self.registry,
            self.launcher,
            self.monitors,
            self.windows,
            self.state,
            system_info_service=sys_info,
        )

        self.assertEqual(router.route("cpu usage").message, "CPU 20 percent.")
        sys_info.get_cpu_usage.assert_called_once()

        self.assertEqual(router.route("memory usage").message, "Memory 50 percent.")
        sys_info.get_memory_usage.assert_called_once()

        self.assertEqual(router.route("disk usage").message, "Disk 40 percent.")
        sys_info.get_disk_usage.assert_called_once()

        self.assertEqual(router.route("battery status").message, "Battery 90 percent.")
        sys_info.get_battery_status.assert_called_once()

        self.assertEqual(router.route("what time is it").message, "It is 10:00 AM.")
        sys_info.get_current_time.assert_called_once()

        self.assertEqual(router.route("system status").message, "System status summary.")
        sys_info.get_system_status.assert_called_once()

    def test_routes_system_control_commands(self) -> None:
        sys_control = Mock()
        sys_control.mute_volume.return_value = CommandResult.ok("Volume muted.")
        sys_control.unmute_volume.return_value = CommandResult.ok("Volume unmuted.")
        sys_control.volume_up.return_value = CommandResult.ok("Volume is at 55 percent.")
        sys_control.volume_down.return_value = CommandResult.ok("Volume is at 45 percent.")
        sys_control.set_volume.side_effect = lambda level: (
            CommandResult.ok(f"Volume is at {level} percent.")
            if 0 <= level <= 100
            else CommandResult.failure("invalid_volume_level", "Volume must be between 0 and 100 percent.")
        )
        sys_control.lock_computer.return_value = CommandResult.ok("Computer locked.")

        router = CommandRouter(
            self.registry,
            self.launcher,
            self.monitors,
            self.windows,
            self.state,
            system_control_service=sys_control,
        )

        self.assertEqual(router.route("mute volume").message, "Volume muted.")
        sys_control.mute_volume.assert_called_once()

        self.assertEqual(router.route("unmute volume").message, "Volume unmuted.")
        sys_control.unmute_volume.assert_called_once()

        self.assertEqual(router.route("volume up").message, "Volume is at 55 percent.")
        sys_control.volume_up.assert_called_once()

        self.assertEqual(router.route("volume down").message, "Volume is at 45 percent.")
        sys_control.volume_down.assert_called_once()

        self.assertEqual(router.route("set volume to 50").message, "Volume is at 50 percent.")
        sys_control.set_volume.assert_called_with(50)

        self.assertEqual(router.route("set volume to 150").error_code, "invalid_volume_level")
        sys_control.set_volume.assert_called_with(150)

        self.assertEqual(router.route("lock computer").message, "Computer locked.")
        sys_control.lock_computer.assert_called_once()

    def test_routes_power_commands_with_confirmation(self) -> None:
        power_service = Mock()
        power_service.shutdown_computer.return_value = CommandResult.ok("Shutting down.")
        power_service.restart_computer.return_value = CommandResult.ok("Restarting.")
        power_service.sleep_computer.return_value = CommandResult.ok("Putting the computer to sleep.")

        current_time = 1000.0
        confirmation_manager = ConfirmationManager(
            default_timeout=10.0,
            time_provider=lambda: current_time,
        )

        router = CommandRouter(
            self.registry,
            self.launcher,
            self.monitors,
            self.windows,
            self.state,
            power_service=power_service,
            confirmation_manager=confirmation_manager,
        )

        # 1. Shutdown request -> confirmation prompt
        res1 = router.route("shutdown computer")
        self.assertTrue(res1.success)
        self.assertEqual(res1.message, "Are you sure you want to shut down the computer?")
        self.assertEqual(res1.data.get("pending_confirmation"), "shutdown_computer")
        power_service.shutdown_computer.assert_not_called()

        # 2. Confirm shutdown -> executes shutdown
        res2 = router.route("yes")
        self.assertTrue(res2.success)
        self.assertEqual(res2.message, "Shutting down.")
        power_service.shutdown_computer.assert_called_once()

        # 3. 'yes' with no pending confirmation -> does not execute
        res3 = router.route("yes")
        self.assertFalse(res3.success)
        self.assertEqual(res3.error_code, "no_pending_confirmation")

        # 4. Restart request -> cancel -> does not execute
        router.route("restart computer")
        res_cancel = router.route("no")
        self.assertTrue(res_cancel.success)
        self.assertEqual(res_cancel.message, "Restart cancelled.")
        power_service.restart_computer.assert_not_called()

        # 5. Sleep request -> expiration
        router.route("sleep computer")
        current_time = 1015.0  # 15s > 10s timeout
        res_expired = router.route("confirm")
        self.assertFalse(res_expired.success)
        self.assertEqual(res_expired.error_code, "confirmation_expired")
        power_service.sleep_computer.assert_not_called()

        # 6. Action replacement: shutdown request -> restart request -> confirm restart
        router.route("shutdown computer")
        res_rep = router.route("restart computer")
        self.assertEqual(res_rep.message, "Are you sure you want to restart the computer?")
        res_conf = router.route("confirmed")
        self.assertEqual(res_conf.message, "Restarting.")
        power_service.restart_computer.assert_called_once()


class Phase5ACommandRouterTests(unittest.TestCase):
    """Tests for Phase 5A context-aware window router dispatch."""

    def setUp(self) -> None:
        self.chrome_app = DiscoveredApplication.create(
            "Google Chrome", Path("chrome.exe"), source="test"
        )
        self.registry = Mock()
        self.registry.match.return_value = self.chrome_app
        self.registry.load_all.return_value = [self.chrome_app]
        self.launcher = Mock()
        self.monitors = Mock()
        self.monitors.monitor_count.return_value = 2
        self.monitors.get_monitor.side_effect = lambda idx: (
            MonitorInfo(idx, 'Display', 0, 0, 100, 100, idx == 1, 0, 0, 100, 100)
            if idx in {1, 2} else None
        )
        self.active_window = WindowInfo(10, 'Google Chrome', 101, 'chrome.exe', 0, 0, 800, 600)
        self.windows = Mock()
        self.windows.find_window.return_value = self.active_window
        self.windows.get_active_window.return_value = self.active_window
        self.windows.list_open_windows.return_value = [self.active_window]
        self.windows.is_application_open.return_value = True
        self.windows.get_window_monitor.return_value = MonitorInfo(1, 'Laptop', 0, 0, 1536, 864, True, 0, 0, 1536, 816)
        self.windows.activate_window.return_value = CommandResult.ok('Window activated.')
        self.windows.maximize_window.return_value = CommandResult.ok('Window maximized.')
        self.windows.minimize_window.return_value = CommandResult.ok('Window minimized.')
        self.windows.restore_window.return_value = CommandResult.ok('Window restored.')
        self.windows.move_window_to_monitor.return_value = CommandResult.ok('Window moved.')
        self.state = StateManager(AssistantState.LISTENING)
        self.router = CommandRouter(
            self.registry, self.launcher, self.monitors, self.windows, self.state
        )

    def test_maximize_active_window(self) -> None:
        result = self.router.route("maximize this window")
        self.assertTrue(result.success)
        self.windows.maximize_window.assert_called_with(self.active_window)

    def test_minimize_active_window(self) -> None:
        result = self.router.route("minimize this window")
        self.assertTrue(result.success)
        self.windows.minimize_window.assert_called_with(self.active_window)

    def test_restore_active_window(self) -> None:
        result = self.router.route("restore this window")
        self.assertTrue(result.success)
        self.windows.restore_window.assert_called_with(self.active_window)

    def test_move_active_window_success(self) -> None:
        result = self.router.route("move this window to monitor 2")
        self.assertTrue(result.success)
        self.windows.move_window_to_monitor.assert_called_with(self.active_window, 2)


class Phase5BCommandRouterTests(unittest.TestCase):
    """Tests verifying CommandRouter delegates Phase 5B context intents to DesktopContextService."""

    def setUp(self) -> None:
        self.registry = Mock()
        self.launcher = Mock()
        self.monitors = Mock()
        self.windows = Mock()
        self.state = Mock()
        self.context_service = Mock()

        self.router = CommandRouter(
            self.registry,
            self.launcher,
            self.monitors,
            self.windows,
            self.state,
            desktop_context_service=self.context_service,
        )

    def test_dispatches_get_active_window(self) -> None:
        self.context_service.get_active_window.return_value = CommandResult.ok("The active window is Chrome.")
        res = self.router.route("what window is active")
        self.assertTrue(res.success)
        self.context_service.get_active_window.assert_called_once()

    def test_dispatches_get_active_application(self) -> None:
        self.context_service.get_active_application.return_value = CommandResult.ok("Google Chrome is the active application.")
        res = self.router.route("what application is active")
        self.assertTrue(res.success)
        self.context_service.get_active_application.assert_called_once()

    def test_dispatches_get_active_window_monitor(self) -> None:
        self.context_service.get_active_window_monitor.return_value = CommandResult.ok("The active window is on monitor 1.")
        res = self.router.route("which monitor is this window on")
        self.assertTrue(res.success)
        self.context_service.get_active_window_monitor.assert_called_once()

    def test_dispatches_check_application_running(self) -> None:
        self.context_service.is_application_running.return_value = CommandResult.ok("Yes, Google Chrome is running.")
        res = self.router.route("is chrome open")
        self.assertTrue(res.success)
        self.context_service.is_application_running.assert_called_with("chrome")

    def test_dispatches_list_open_applications(self) -> None:
        self.context_service.get_open_applications.return_value = CommandResult.ok("Open applications are Chrome.")
        res = self.router.route("what applications are open")
        self.assertTrue(res.success)
        self.context_service.get_open_applications.assert_called_once()

    def test_dispatches_locate_application(self) -> None:
        self.context_service.locate_application.return_value = CommandResult.ok("Google Chrome is on monitor 1.")
        res = self.router.route("where is chrome")
        self.assertTrue(res.success)
        self.context_service.locate_application.assert_called_with("chrome")


class Phase5C1CommandRouterTests(unittest.TestCase):
    """Tests for Phase 5C-1 window focus and close command router dispatch."""

    def setUp(self) -> None:
        self.chrome_app = DiscoveredApplication.create(
            "Google Chrome", Path("chrome.exe"), source="test"
        )
        self.registry = Mock()
        self.registry.match.return_value = self.chrome_app
        self.registry.load_all.return_value = [self.chrome_app]
        self.launcher = Mock()
        self.monitors = Mock()
        self.monitors.monitor_count.return_value = 2
        self.chrome_window = WindowInfo(100, "Google Chrome", 1234, "chrome.exe", 0, 0, 800, 600)
        self.windows = Mock()
        self.windows.find_window.return_value = self.chrome_window
        self.windows.get_active_window.return_value = self.chrome_window
        self.windows.focus_window.return_value = CommandResult.ok("Focusing Google Chrome.")
        self.windows.close_window.return_value = CommandResult.ok("Window close requested.")
        self.state = Mock()
        self.context_service = Mock()
        self.context_service.focus_application.return_value = CommandResult.ok("Focusing Google Chrome.")

        current_time = 1000.0
        self.confirmation_manager = ConfirmationManager(
            default_timeout=10.0,
            time_provider=lambda: current_time,
        )

        self.router = CommandRouter(
            self.registry,
            self.launcher,
            self.monitors,
            self.windows,
            self.state,
            desktop_context_service=self.context_service,
            confirmation_manager=self.confirmation_manager,
        )

    def test_focus_application_dispatches_to_context_service(self) -> None:
        self.context_service.focus_application.return_value = CommandResult.ok("Focusing Google Chrome.")
        res = self.router.route("focus chrome")
        self.assertTrue(res.success)
        self.context_service.focus_application.assert_called_with("chrome")

    def test_focus_application_does_not_require_confirmation(self) -> None:
        self.context_service.focus_application.return_value = CommandResult.ok("Focusing Google Chrome.")
        res = self.router.route("focus chrome")
        self.assertTrue(res.success)
        self.assertIsNone(self.confirmation_manager.pending)

    def test_focus_application_with_switch_to(self) -> None:
        self.context_service.focus_application.return_value = CommandResult.ok("Focusing Google Chrome.")
        res = self.router.route("switch to chrome")
        self.assertTrue(res.success)
        self.context_service.focus_application.assert_called_with("chrome")

    def test_focus_application_with_bring_to_front(self) -> None:
        self.context_service.focus_application.return_value = CommandResult.ok("Focusing Google Chrome.")
        res = self.router.route("bring chrome to front")
        self.assertTrue(res.success)
        self.context_service.focus_application.assert_called_with("chrome")

    def test_close_application_requires_confirmation(self) -> None:
        res = self.router.route("close chrome")
        self.assertTrue(res.success)
        self.assertEqual(res.message, "Are you sure you want to close the Google Chrome window?")
        self.assertEqual(res.data.get("pending_confirmation"), "close_application")
        self.assertTrue(res.data.get("requires_confirmation"))
        self.windows.close_window.assert_not_called()

    def test_close_application_confirmation_executes_close(self) -> None:
        # Request close
        self.router.route("close chrome")
        # Confirm
        res_confirm = self.router.route("yes")
        self.assertTrue(res_confirm.success)
        self.assertEqual(res_confirm.message, "Google Chrome window closed.")
        self.windows.close_window.assert_called_once_with(100)

    def test_close_application_cancellation_prevents_close(self) -> None:
        # Request close
        self.router.route("close chrome")
        # Cancel
        res_cancel = self.router.route("no")
        self.assertTrue(res_cancel.success)
        self.assertEqual(res_cancel.message, "Closing Google Chrome window cancelled.")
        self.windows.close_window.assert_not_called()

    def test_close_active_window_requires_confirmation(self) -> None:
        res = self.router.route("close this window")
        self.assertTrue(res.success)
        self.assertEqual(res.message, "Are you sure you want to close the active window?")
        self.assertEqual(res.data.get("pending_confirmation"), "close_active_window")
        self.assertTrue(res.data.get("requires_confirmation"))
        self.windows.close_window.assert_not_called()

    def test_close_active_window_confirmation_executes_close(self) -> None:
        # Request close
        self.router.route("close this window")
        # Confirm
        res_confirm = self.router.route("yes")
        self.assertTrue(res_confirm.success)
        self.assertEqual(res_confirm.message, "The active window was closed.")
        self.windows.close_window.assert_called_once_with(100)

    def test_close_active_window_cancellation_prevents_close(self) -> None:
        # Request close
        self.router.route("close this window")
        # Cancel
        res_cancel = self.router.route("no")
        self.assertTrue(res_cancel.success)
        self.assertEqual(res_cancel.message, "Closing active window cancelled.")
        self.windows.close_window.assert_not_called()

    def test_close_active_window_no_active_window(self) -> None:
        self.windows.get_active_window.return_value = None
        res = self.router.route("close this window")
        self.assertFalse(res.success)
        self.assertEqual(res.error_code, "no_active_window")
        self.assertIsNone(self.confirmation_manager.pending)

    def test_confirmation_expiration_prevents_close(self) -> None:
        # Request close
        self.router.route("close chrome")
        # Advance time past timeout
        current_time = 1015.0  # 15s > 10s timeout
        self.confirmation_manager._time_provider = lambda: current_time
        # Try to confirm
        res_expired = self.router.route("yes")
        self.assertFalse(res_expired.success)
        self.assertEqual(res_expired.error_code, "confirmation_expired")
        self.windows.close_window.assert_not_called()

    def test_wrong_confirmation_cannot_trigger_action(self) -> None:
        # Try to confirm without pending action
        res = self.router.route("yes")
        self.assertFalse(res.success)
        self.assertEqual(res.error_code, "no_pending_confirmation")
        self.windows.close_window.assert_not_called()

    def test_action_replacement_with_new_confirmation(self) -> None:
        # Request close chrome
        self.router.route("close chrome")
        # Request close this window (replaces previous)
        res_replace = self.router.route("close this window")
        self.assertEqual(res_replace.message, "Are you sure you want to close the active window?")
        # Confirm should execute close active window, not close chrome
        res_confirm = self.router.route("yes")
        self.assertTrue(res_confirm.success)
        self.assertEqual(res_confirm.message, "The active window was closed.")
        self.windows.close_window.assert_called_once_with(100)

    def test_focus_application_service_failure_propagates(self) -> None:
        self.context_service.focus_application.return_value = CommandResult.failure(
            "focus_application_failed", "Failed to focus application."
        )
        res = self.router.route("focus chrome")
        self.assertFalse(res.success)
        self.assertEqual(res.error_code, "focus_application_failed")

    def test_close_application_window_not_found(self) -> None:
        self.windows.find_window.return_value = None
        res = self.router.route("close chrome")
        self.assertFalse(res.success)
        self.assertEqual(res.error_code, "window_not_found")
        self.assertIsNone(self.confirmation_manager.pending)

    def test_close_active_window_rejects_closing_assistant_dashboard(self) -> None:
        dashboard_window = WindowInfo(999, "JARVIS Desktop Assistant", 5000, "python.exe", 0, 0, 640, 480)
        self.windows.get_active_window.return_value = dashboard_window
        res = self.router.route("close this window")
        self.assertFalse(res.success)
        self.assertEqual(res.error_code, "protected_window")
        self.assertIn("cannot close the assistant dashboard", res.message)
        self.assertIsNone(self.confirmation_manager.pending)
        self.windows.close_window.assert_not_called()


class Phase5C2CommandRouterTests(unittest.TestCase):
    """Phase 5C-2 router tests for discovery hardening, multi-window rejection, and stale HWND."""

    def setUp(self) -> None:
        self.chrome_app = DiscoveredApplication.create(
            "Google Chrome", Path("chrome.exe"), source="test"
        )
        self.registry = Mock()
        self.registry.match.return_value = self.chrome_app
        self.launcher = Mock()
        self.monitors = Mock()
        self.monitors.monitor_count.return_value = 2

        self.chrome_win1 = WindowInfo(100, "Google Chrome - Tab 1", 1234, "chrome.exe", 0, 0, 800, 600)
        self.chrome_win2 = WindowInfo(101, "Google Chrome - Tab 2", 1234, "chrome.exe", 0, 0, 800, 600)

        self.windows = Mock()
        self.windows.find_window.return_value = self.chrome_win1
        self.windows.find_windows.return_value = [self.chrome_win1]
        self.windows.get_active_window.return_value = self.chrome_win1
        self.windows.is_valid_window.return_value = True
        self.windows.get_window_info.return_value = self.chrome_win1
        self.windows.close_window.return_value = CommandResult.ok("Window close requested.")

        self.state = Mock()
        self.context_service = Mock()
        self.context_service.get_open_windows.return_value = CommandResult.ok("Open windows: Chrome.")
        self.context_service.get_open_applications.return_value = CommandResult.ok("Open applications: Chrome.")

        self.confirmation_manager = ConfirmationManager(
            default_timeout=10.0,
            time_provider=lambda: 1000.0,
        )

        self.router = CommandRouter(
            self.registry,
            self.launcher,
            self.monitors,
            self.windows,
            self.state,
            desktop_context_service=self.context_service,
            confirmation_manager=self.confirmation_manager,
        )

    def test_list_open_windows_dispatches_to_get_open_windows(self) -> None:
        res = self.router.route("list open windows")
        self.assertTrue(res.success)
        self.context_service.get_open_windows.assert_called_once()
        self.context_service.get_open_applications.assert_not_called()

    def test_close_application_multiple_windows_rejected_without_confirmation(self) -> None:
        self.windows.find_windows.return_value = [self.chrome_win1, self.chrome_win2]
        res = self.router.route("close chrome")
        self.assertFalse(res.success)
        self.assertEqual(res.error_code, "multiple_windows_found")
        self.assertIn("Multiple windows found", res.message)
        self.assertIsNone(self.confirmation_manager.pending)
        self.windows.close_window.assert_not_called()

    def test_stale_hwnd_rejection_on_close_application(self) -> None:
        # 1. Request close chrome -> creates confirmation for HWND 100
        res = self.router.route("close chrome")
        self.assertTrue(res.success)
        self.assertIsNotNone(self.confirmation_manager.pending)

        # 2. Window disappears before user confirms
        self.windows.is_valid_window.return_value = False
        res_confirm = self.router.route("yes")
        self.assertFalse(res_confirm.success)
        self.assertEqual(res_confirm.error_code, "stale_window")
        self.assertIn("no longer available", res_confirm.message)
        self.windows.close_window.assert_not_called()

    def test_stale_hwnd_target_mismatch_on_close_application(self) -> None:
        # 1. Request close chrome -> creates confirmation for HWND 100
        res = self.router.route("close chrome")
        self.assertTrue(res.success)

        # 2. HWND was recycled to Notepad before user confirms
        notepad_win = WindowInfo(100, "Untitled - Notepad", 9999, "notepad.exe", 0, 0, 500, 500)
        self.windows.get_window_info.return_value = notepad_win
        res_confirm = self.router.route("yes")
        self.assertFalse(res_confirm.success)
        self.assertEqual(res_confirm.error_code, "stale_window")
        self.assertIn("no longer corresponds", res_confirm.message)
        self.windows.close_window.assert_not_called()

    def test_stale_hwnd_rejection_on_close_active_window(self) -> None:
        # 1. Request close this window -> creates confirmation for HWND 100
        res = self.router.route("close this window")
        self.assertTrue(res.success)
        self.assertIsNotNone(self.confirmation_manager.pending)

        # 2. Window disappears before user confirms
        self.windows.is_valid_window.return_value = False
        res_confirm = self.router.route("yes")
        self.assertFalse(res_confirm.success)
        self.assertEqual(res_confirm.error_code, "stale_window")
        self.assertIn("no longer available", res_confirm.message)
        self.windows.close_window.assert_not_called()




