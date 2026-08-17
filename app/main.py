"""JARVIS desktop application entry point."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from core.assistant import JarvisAssistant
from core.config import load_config
from core.logging_config import configure_logging
from ui.dashboard import JarvisDashboard


def create_dashboard(argv: list[str] | None = None) -> tuple[QApplication, JarvisDashboard]:
    """Create the Qt application and the JARVIS dashboard."""
    configure_logging(load_config())
    application = QApplication.instance() or QApplication(argv or sys.argv)
    dashboard = JarvisDashboard(JarvisAssistant())
    return application, dashboard


def main() -> int:
    """Start the JARVIS desktop dashboard."""
    application, dashboard = create_dashboard()
    dashboard.show()
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
