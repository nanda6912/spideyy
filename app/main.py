"""JARVIS / SPIDEYY desktop application entry point."""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure project root is in sys.path and is current working directory
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
try:
    os.chdir(PROJECT_ROOT)
except Exception:
    pass

from PySide6.QtWidgets import QApplication

from core.assistant import JarvisAssistant
from core.config import load_config
from core.logging_config import configure_logging
from system.single_instance import SingleInstanceGuard
from system.startup_manager import StartupManager
from ui.dashboard import JarvisDashboard


def handle_cli_arguments(args: list[str]) -> int | None:
    """Handle non-GUI CLI commands such as startup configuration.

    Returns an exit code if a CLI command was processed, or None to proceed with GUI.
    """
    if "--startup-enable" in args:
        manager = StartupManager()
        if manager.enable():
            print("SPIDEYY startup enabled.")
            return 0
        print("Failed to enable SPIDEYY startup.")
        return 1

    if "--startup-disable" in args:
        manager = StartupManager()
        if manager.disable():
            print("SPIDEYY startup disabled.")
            return 0
        print("Failed to disable SPIDEYY startup.")
        return 1

    if "--startup-status" in args:
        manager = StartupManager()
        status_str = "Enabled" if manager.is_enabled() else "Disabled"
        print(f"Start with Windows: {status_str}")
        return 0

    return None


def create_dashboard(argv: list[str] | None = None) -> tuple[QApplication, JarvisDashboard]:
    """Create the Qt application and the JARVIS dashboard."""
    configure_logging(load_config())
    application = QApplication.instance() or QApplication(argv or sys.argv)
    dashboard = JarvisDashboard(JarvisAssistant())
    return application, dashboard


def main(argv: list[str] | None = None) -> int:
    """Start the JARVIS desktop dashboard or execute a startup configuration command."""
    args = argv if argv is not None else sys.argv[1:]

    cli_exit = handle_cli_arguments(args)
    if cli_exit is not None:
        return cli_exit

    guard = SingleInstanceGuard()
    if not guard.acquire():
        print("SPIDEYY is already running.")
        return 0

    try:
        application, dashboard = create_dashboard(argv)
        dashboard.show()
        return application.exec()
    finally:
        guard.release()


if __name__ == "__main__":
    raise SystemExit(main())
