import unittest
from unittest.mock import Mock

from system.monitor_manager import MonitorInfo, MonitorManager


class FakeGeometry:
    def __init__(self, x: int, y: int, width: int, height: int) -> None:
        self._x = x
        self._y = y
        self._width = width
        self._height = height

    def x(self) -> int:
        return self._x

    def y(self) -> int:
        return self._y

    def width(self) -> int:
        return self._width

    def height(self) -> int:
        return self._height


class FakeScreen:
    def __init__(
        self,
        name: str,
        geometry: tuple[int, int, int, int],
        available: tuple[int, int, int, int],
    ) -> None:
        self._name = name
        self._geometry = FakeGeometry(*geometry)
        self._available = FakeGeometry(*available)

    def name(self) -> str:
        return self._name

    def geometry(self) -> FakeGeometry:
        return self._geometry

    def availableGeometry(self) -> FakeGeometry:
        return self._available


class MonitorInfoTests(unittest.TestCase):
    def test_validation_rejects_invalid_dimensions_and_index(self) -> None:
        with self.assertRaises(ValueError):
            MonitorInfo(0, "Display", 0, 0, 1920, 1080, True, 0, 0, 1920, 1040)
        with self.assertRaises(ValueError):
            MonitorInfo(1, "Display", 0, 0, 0, 1080, True, 0, 0, 1920, 1040)

    def test_geometry_properties_are_structured(self) -> None:
        monitor = MonitorInfo(2, "External", -1920, 0, 1920, 1080, False, -1920, 0, 1920, 1040)

        self.assertEqual(monitor.geometry, (-1920, 0, 1920, 1080))
        self.assertEqual(monitor.available_geometry, (-1920, 0, 1920, 1040))


class MonitorManagerTests(unittest.TestCase):
    def _manager(self) -> MonitorManager:
        primary = FakeScreen("Laptop Panel", (0, 0, 1920, 1080), (0, 0, 1920, 1040))
        left = FakeScreen("External Display", (-1280, -200, 1280, 1024), (-1280, -200, 1280, 984))
        screens = [primary, left]
        return MonitorManager(
            screen_provider=Mock(return_value=screens),
            primary_screen_provider=Mock(return_value=primary),
        )

    def test_multiple_monitor_geometry_and_primary_selection(self) -> None:
        manager = self._manager()

        monitors = manager.get_monitors()

        self.assertEqual(len(monitors), 2)
        self.assertEqual(monitors[1].geometry, (-1280, -200, 1280, 1024))
        self.assertEqual(manager.get_primary_monitor().name, "Laptop Panel")
        self.assertEqual(manager.monitor_count(), 2)

    def test_monitor_lookup_and_invalid_index(self) -> None:
        manager = self._manager()

        self.assertEqual(manager.get_monitor(2).name, "External Display")
        self.assertIsNone(manager.get_monitor(3))
        self.assertIsNone(manager.get_monitor(0))

    def test_description_covers_multiple_monitor_scenario(self) -> None:
        description = self._manager().describe_monitors()

        self.assertIn("Monitor 1: Laptop Panel, 1920x1080, Primary", description)
        self.assertIn("Monitor 2: External Display, 1280x1024, Secondary", description)
