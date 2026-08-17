import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from system.application_discovery import ApplicationRegistry, DiscoveredApplication
from system.application_registry_service import ApplicationRegistryService


class ApplicationRegistryServiceTests(unittest.TestCase):
    @staticmethod
    def _application(directory: Path, name: str = "Eclipse IDE") -> DiscoveredApplication:
        executable = directory / f"{name.replace(' ', '_')}.exe"
        executable.touch()
        return DiscoveredApplication.create(name, executable, source="test")

    def test_empty_registry_runs_discovery(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            registry = ApplicationRegistry(root / "applications.db")
            discovered = self._application(root)
            discovery = Mock()
            discovery.discover.return_value = [discovered]

            result = ApplicationRegistryService(registry, discovery).ensure_populated()

            discovery.discover.assert_called_once_with()
            self.assertTrue(result.success)
            self.assertTrue(result.data["refreshed"])
            self.assertEqual(registry.load_all(), [discovered])

    def test_populated_registry_loads_without_discovery(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            registry = ApplicationRegistry(root / "applications.db")
            application = self._application(root)
            registry.replace_all([application])
            discovery = Mock()

            result = ApplicationRegistryService(registry, discovery).ensure_populated()

            discovery.discover.assert_not_called()
            self.assertTrue(result.success)
            self.assertFalse(result.data["refreshed"])

    def test_explicit_refresh_replaces_registry(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            registry = ApplicationRegistry(root / "applications.db")
            old_application = self._application(root, "Old App")
            new_application = self._application(root, "Eclipse IDE")
            registry.replace_all([old_application])
            discovery = Mock()
            discovery.discover.return_value = [new_application]

            result = ApplicationRegistryService(registry, discovery).refresh()

            self.assertTrue(result.success)
            self.assertEqual(registry.load_all(), [new_application])

    def test_discovery_failure_keeps_existing_registry(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            registry = ApplicationRegistry(root / "applications.db")
            application = self._application(root)
            registry.replace_all([application])
            discovery = Mock()
            discovery.discover.side_effect = OSError("registry unavailable")

            result = ApplicationRegistryService(registry, discovery).refresh()

            self.assertFalse(result.success)
            self.assertEqual(result.error_code, "application_discovery_failed")
            self.assertEqual(registry.load_all(), [application])
