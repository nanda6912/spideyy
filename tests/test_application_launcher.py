import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from system.application_discovery import ApplicationRegistry, DiscoveredApplication
from system.application_launcher import ApplicationLauncher


class ApplicationLauncherTests(unittest.TestCase):
    def _registry_with_eclipse(self, directory: str) -> tuple[ApplicationRegistry, Path]:
        root = Path(directory)
        executable = root / "eclipse.exe"
        executable.touch()
        registry = ApplicationRegistry(root / "applications.db")
        registry.replace_all(
            [DiscoveredApplication.create("Eclipse IDE", executable, source="test")]
        )
        return registry, executable

    def test_launches_registered_application_without_a_shell(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            registry, executable = self._registry_with_eclipse(directory)
            with patch("system.application_launcher.subprocess.Popen") as popen:
                result = ApplicationLauncher(registry).launch("open eclipse")

        self.assertTrue(result.success)
        self.assertEqual(result.data["application"], "Eclipse IDE")
        popen.assert_called_once_with([str(executable)], shell=False, close_fds=True)

    def test_returns_not_found_for_unregistered_application(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            registry = ApplicationRegistry(Path(directory) / "applications.db")
            result = ApplicationLauncher(registry).launch("open unknown-tool")

        self.assertFalse(result.success)
        self.assertEqual(result.error_code, "application_not_found")

    def test_returns_unavailable_when_registered_executable_was_removed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            registry, executable = self._registry_with_eclipse(directory)
            executable.unlink()
            result = ApplicationLauncher(registry).launch("eclipse")

        self.assertFalse(result.success)
        self.assertEqual(result.error_code, "application_unavailable")

    def test_returns_launch_failure_when_process_creation_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            registry, _ = self._registry_with_eclipse(directory)
            with patch(
                "system.application_launcher.subprocess.Popen",
                side_effect=OSError("access denied"),
            ):
                result = ApplicationLauncher(registry).launch("launch eclipse")

        self.assertFalse(result.success)
        self.assertEqual(result.error_code, "application_launch_failed")
