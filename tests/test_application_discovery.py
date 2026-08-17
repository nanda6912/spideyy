import tempfile
import unittest
from pathlib import Path

from system.application_discovery import (
    ApplicationRegistry,
    DiscoveredApplication,
    aliases_for,
    normalize_name,
)


class ApplicationDiscoveryTests(unittest.TestCase):
    def test_normalization_is_deterministic_and_removes_command_prefix(self) -> None:
        self.assertEqual(normalize_name("Open: Visual-Studio_Code!"), "visual studio code")

    def test_known_aliases_support_spoken_names(self) -> None:
        self.assertIn("chrome", aliases_for("Google Chrome"))
        self.assertIn("vscode", aliases_for("Visual Studio Code"))
        self.assertIn("intellij", aliases_for("IntelliJ IDEA"))
        self.assertIn("eclipse", aliases_for("Eclipse IDE"))
        self.assertIn("terminal", aliases_for("Windows Terminal"))

    def test_invalid_discovery_result_is_rejected(self) -> None:
        application = DiscoveredApplication.create(
            "Missing App", "C:/not-a-real-application.exe", source="test"
        )
        self.assertFalse(application.is_valid())

    def test_registry_persists_and_matches_aliases(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            chrome_executable = root / "chrome.exe"
            code_executable = root / "Code.exe"
            intellij_executable = root / "idea64.exe"
            terminal_executable = root / "WindowsTerminal.exe"
            chrome_executable.touch()
            code_executable.touch()
            intellij_executable.touch()
            terminal_executable.touch()
            registry = ApplicationRegistry(root / "applications.db")
            registry.replace_all(
                [
                    DiscoveredApplication.create("Google Chrome", chrome_executable, source="test"),
                    DiscoveredApplication.create("Visual Studio Code", code_executable, source="test"),
                    DiscoveredApplication.create("IntelliJ IDEA", intellij_executable, source="test"),
                    DiscoveredApplication.create("Windows Terminal", terminal_executable, source="test"),
                ]
            )

            reloaded_registry = ApplicationRegistry(root / "applications.db")
            self.assertEqual(len(reloaded_registry.load_all()), 4)
            self.assertEqual(reloaded_registry.match("open chrome").name, "Google Chrome")
            self.assertEqual(reloaded_registry.match("vscode").name, "Visual Studio Code")
            self.assertEqual(reloaded_registry.match("intellij").name, "IntelliJ IDEA")
            self.assertEqual(reloaded_registry.match("terminal").name, "Windows Terminal")
            self.assertEqual(reloaded_registry.match("visual studio cod").name, "Visual Studio Code")
