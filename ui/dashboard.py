"""Lightweight PySide6 dashboard for the deterministic JARVIS assistant."""

from __future__ import annotations

import logging
from collections.abc import Callable

from PySide6.QtCore import QObject, Qt, QThread, Signal, Slot
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.assistant import JarvisAssistant
from core.models import CommandResult
from core.state import AssistantState


logger = logging.getLogger("jarvis.ui.dashboard")


class _TaskWorker(QObject):
    """Execute one assistant operation away from the Qt event loop."""

    finished = Signal(object)

    def __init__(self, operation: Callable[[], CommandResult]) -> None:
        super().__init__()
        self._operation = operation

    @Slot()
    def run(self) -> None:
        com_initialized = False
        try:
            import pythoncom

            pythoncom.CoInitialize()
            com_initialized = True
            result = self._operation()
        except Exception as error:
            logger.error("Dashboard task failed (%s).", type(error).__name__)
            result = CommandResult.failure(
                "dashboard_operation_failed",
                "JARVIS couldn't complete that operation.",
            )
        finally:
            if com_initialized:
                pythoncom.CoUninitialize()
        self.finished.emit(result)


class JarvisDashboard(QMainWindow):
    """Small desktop dashboard that delegates commands to ``JarvisAssistant``."""

    task_completed = Signal(object, str)

    def __init__(
        self, assistant: JarvisAssistant, *, initialize_on_startup: bool = True
    ) -> None:
        super().__init__()
        self._assistant = assistant
        self._threads: set[QThread] = set()
        self._workers: set[_TaskWorker] = set()
        self.task_completed.connect(self._handle_task_result)
        self.setWindowTitle("JARVIS Desktop Assistant")
        self.setMinimumSize(640, 480)
        self._build_ui()
        self._set_state(AssistantState.STANDBY)
        if initialize_on_startup:
            self._run_async(self._assistant.startup, "startup")
        else:
            self._update_counts()

    def _build_ui(self) -> None:
        root = QWidget(self)
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setSpacing(12)

        title = QLabel("JARVIS")
        title.setStyleSheet("font-size: 24px; font-weight: 700;")
        subtitle = QLabel("Windows desktop assistant")
        subtitle.setStyleSheet("color: #666;")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        overview = QHBoxLayout()
        self.state_indicator = QLabel()
        self.state_indicator.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.state_indicator.setMinimumWidth(130)
        self.monitor_count_label = QLabel("Monitors: —")
        self.application_count_label = QLabel("Applications: —")
        overview.addWidget(self.state_indicator)
        overview.addWidget(self.monitor_count_label)
        overview.addWidget(self.application_count_label)
        overview.addStretch()
        layout.addLayout(overview)

        layout.addWidget(QLabel("Activity"))
        self.activity_log = QPlainTextEdit()
        self.activity_log.setReadOnly(True)
        self.activity_log.setMaximumBlockCount(250)
        layout.addWidget(self.activity_log, stretch=1)

        command_row = QHBoxLayout()
        self.command_input = QLineEdit()
        self.command_input.setPlaceholderText("Try: show monitors, open chrome, move chrome to monitor 2")
        self.command_input.returnPressed.connect(self.execute_command)
        self.execute_button = QPushButton("Execute")
        self.execute_button.clicked.connect(self.execute_command)
        self.refresh_button = QPushButton("Refresh Applications")
        self.refresh_button.clicked.connect(self.refresh_applications)
        self.clear_button = QPushButton("Clear")
        self.clear_button.clicked.connect(self.activity_log.clear)
        command_row.addWidget(self.command_input, stretch=1)
        command_row.addWidget(self.execute_button)
        command_row.addWidget(self.refresh_button)
        command_row.addWidget(self.clear_button)
        layout.addLayout(command_row)

    @Slot()
    def execute_command(self) -> None:
        command = self.command_input.text().strip()
        if not command:
            self._append_activity(False, "Enter a command first.")
            return
        self.command_input.clear()
        self._append_activity(True, f"> {command}")
        self._run_async(lambda: self._assistant.handle_command(command), "command")

    @Slot()
    def refresh_applications(self) -> None:
        self._append_activity(True, "> refresh applications")
        self._run_async(
            lambda: self._assistant.handle_command("refresh applications"), "refresh"
        )

    def _run_async(self, operation: Callable[[], CommandResult], context: str) -> None:
        self.execute_button.setEnabled(False)
        self.refresh_button.setEnabled(False)
        self._set_state(AssistantState.PROCESSING)
        thread = QThread(self)
        worker = _TaskWorker(operation)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(lambda result: self.task_completed.emit(result, context))
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(lambda: self._threads.discard(thread))
        thread.finished.connect(lambda: self._workers.discard(worker))
        self._threads.add(thread)
        self._workers.add(worker)
        thread.start()

    @Slot(object, str)
    def _handle_task_result(self, result: CommandResult, context: str) -> None:
        self.execute_button.setEnabled(True)
        self.refresh_button.setEnabled(True)
        self._set_state(self._assistant.state_manager.current)
        self._append_activity(result.success, result.message)
        self._update_counts(result)
        if context == "startup" and not result.success:
            self._append_activity(False, "Startup completed with limited application data.")

    def _update_counts(self, result: CommandResult | None = None) -> None:
        try:
            monitor_count = self._assistant.monitor_manager.monitor_count()
            application_count = (
                result.data.get("application_count")
                if result is not None
                else len(self._assistant.registry.load_all())
            )
            if application_count is None:
                application_count = len(self._assistant.registry.load_all())
            self.monitor_count_label.setText(f"Monitors: {monitor_count}")
            self.application_count_label.setText(f"Applications: {application_count}")
        except Exception as error:
            logger.error("Dashboard counts could not be updated (%s).", type(error).__name__)
            self.monitor_count_label.setText("Monitors: unavailable")
            self.application_count_label.setText("Applications: unavailable")

    def _set_state(self, state: AssistantState) -> None:
        colors = {
            AssistantState.STANDBY: "#e7f4ea",
            AssistantState.PROCESSING: "#fff4ce",
            AssistantState.EXECUTING: "#dbeafe",
            AssistantState.ERROR: "#fee2e2",
        }
        self.state_indicator.setText(state.value.upper())
        self.state_indicator.setStyleSheet(
            f"background: {colors.get(state, '#e5e7eb')}; border: 1px solid #cbd5e1; "
            "border-radius: 4px; padding: 6px;"
        )

    def _append_activity(self, success: bool, message: str) -> None:
        self.activity_log.appendPlainText(f"{'✓' if success else '!'} {message}")
