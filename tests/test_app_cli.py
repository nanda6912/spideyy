from unittest.mock import patch

from app.main import handle_cli_arguments


def test_enable_cli_does_not_create_qt_or_audio_services():
    manager = type("Manager", (), {"enable": lambda self: True})()
    with patch("app.main.StartupManager", return_value=manager), patch("app.main.create_dashboard") as dashboard:
        assert handle_cli_arguments(["--startup-enable"]) == 0
    dashboard.assert_not_called()


def test_disable_cli_returns_failure_when_registry_update_fails():
    manager = type("Manager", (), {"disable": lambda self: False})()
    with patch("app.main.StartupManager", return_value=manager):
        assert handle_cli_arguments(["--startup-disable"]) == 1


def test_status_cli_reports_registry_state_without_starting_application(capsys):
    manager = type("Manager", (), {"is_enabled": lambda self: True})()
    with patch("app.main.StartupManager", return_value=manager):
        assert handle_cli_arguments(["--startup-status"]) == 0
    assert capsys.readouterr().out.strip() == "Start with Windows: Enabled"
