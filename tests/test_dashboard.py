import unittest
from unittest.mock import Mock, patch

from PySide6.QtWidgets import QApplication

from core.models import CommandResult
from core.state import AssistantState, StateManager
from ui.dashboard import JarvisDashboard


class DashboardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.application = QApplication.instance() or QApplication([])

    def test_dashboard_displays_counts_and_results(self) -> None:
        assistant = Mock()
        assistant.state_manager = StateManager()
        assistant.monitor_manager.monitor_count.return_value = 2
        assistant.registry.load_all.return_value = [Mock(), Mock(), Mock()]
        with patch("system.startup_manager.StartupManager.is_enabled", return_value=False):
            dashboard = JarvisDashboard(assistant, initialize_on_startup=False)
            dashboard._handle_task_result(
                CommandResult.ok("Monitor information loaded.", application_count=3), "startup"
            )

        self.assertEqual(dashboard.monitor_count_label.text(), "Monitors: 2")
        self.assertEqual(dashboard.application_count_label.text(), "Applications: 3")
        self.assertEqual(dashboard.startup_status_label.text(), "Start with Windows: Disabled")
        self.assertIn("Monitor information loaded.", dashboard.activity_log.toPlainText())
        self.assertEqual(dashboard.state_indicator.text(), AssistantState.STANDBY.value.upper())
        dashboard.close()

    def test_voice_initialization_failure_leaves_dashboard_usable(self) -> None:
        assistant = Mock()
        assistant.state_manager = StateManager()
        assistant.monitor_manager.monitor_count.return_value = 1
        assistant.registry.load_all.return_value = []
        voice = Mock()
        voice.start.side_effect = RuntimeError("microphone unavailable")
        dashboard = JarvisDashboard(
            assistant,
            initialize_on_startup=False,
            voice_interaction=voice,
        )

        dashboard._start_voice_services()

        self.assertIn("Voice listener unavailable: microphone unavailable", dashboard.activity_log.toPlainText())
        self.assertTrue(dashboard.execute_button.isEnabled())
        dashboard.close()
