"""Tests for CommandDefinition, CommandRegistry, and CommandIntent."""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import Mock

from core.command_registry import (
    CommandDefinition,
    CommandRegistry,
    get_default_command_registry,
)
from core.command_router import CommandRouter, normalize_command
from core.models import CommandIntent, CommandResult
from core.state import AssistantState, StateManager
from system.application_discovery import DiscoveredApplication
from system.monitor_manager import MonitorInfo
from system.window_manager import WindowInfo


class CommandRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = get_default_command_registry()

    def test_1_command_definition_registration(self) -> None:
        custom_registry = CommandRegistry()
        defn = CommandDefinition(
            name="custom_command",
            patterns=("do custom",),
            description="Custom test command",
        )
        custom_registry.register(defn)
        self.assertEqual(custom_registry.get("custom_command"), defn)
        self.assertIn(defn, custom_registry.list_definitions())

    def test_2_command_matching(self) -> None:
        intent = self.registry.match("help")
        self.assertIsNotNone(intent)
        self.assertEqual(intent.name, "help")

        intent_status = self.registry.match("jarvis status")
        self.assertIsNotNone(intent_status)
        self.assertEqual(intent_status.name, "status")

    def test_3_command_intent_creation(self) -> None:
        intent = CommandIntent(
            name="launch_application",
            target="chrome",
            arguments={"flag": True},
            raw_command="open chrome",
        )
        self.assertEqual(intent.name, "launch_application")
        self.assertEqual(intent.target, "chrome")
        self.assertEqual(intent.arguments, {"flag": True})
        self.assertEqual(intent.raw_command, "open chrome")

    def test_4_argument_extraction(self) -> None:
        intent = self.registry.match("move chrome to monitor 2")
        self.assertIsNotNone(intent)
        self.assertEqual(intent.name, "move_window")
        self.assertEqual(intent.target, "chrome")
        self.assertEqual(intent.arguments.get("monitor"), 2)

    def test_5_launch_command_intent(self) -> None:
        for command in ("open chrome", "launch chrome", "start chrome"):
            with self.subTest(command=command):
                intent = self.registry.match(command)
                self.assertIsNotNone(intent)
                self.assertEqual(intent.name, "launch_application")
                self.assertEqual(intent.target, "chrome")
                self.assertEqual(intent.raw_command, command)

    def test_6_maximize_command_intent(self) -> None:
        intent = self.registry.match("maximize chrome")
        self.assertIsNotNone(intent)
        self.assertEqual(intent.name, "maximize_window")
        self.assertEqual(intent.target, "chrome")

    def test_7_minimize_command_intent(self) -> None:
        intent = self.registry.match("minimize chrome")
        self.assertIsNotNone(intent)
        self.assertEqual(intent.name, "minimize_window")
        self.assertEqual(intent.target, "chrome")

    def test_8_restore_command_intent(self) -> None:
        intent = self.registry.match("restore chrome")
        self.assertIsNotNone(intent)
        self.assertEqual(intent.name, "restore_window")
        self.assertEqual(intent.target, "chrome")

    def test_9_move_command_intent(self) -> None:
        intent = self.registry.match("move vscode to monitor 1")
        self.assertIsNotNone(intent)
        self.assertEqual(intent.name, "move_window")
        self.assertEqual(intent.target, "vscode")

    def test_10_monitor_argument_extraction(self) -> None:
        intent = self.registry.match("move firefox to monitor 3")
        self.assertIsNotNone(intent)
        self.assertEqual(intent.arguments, {"monitor": 3})

    def test_11_help_command_intent(self) -> None:
        for command in ("help", "what can you do"):
            with self.subTest(command=command):
                intent = self.registry.match(command)
                self.assertIsNotNone(intent)
                self.assertEqual(intent.name, "help")

    def test_12_status_command_intent(self) -> None:
        for command in ("jarvis status", "status"):
            with self.subTest(command=command):
                intent = self.registry.match(command)
                self.assertIsNotNone(intent)
                self.assertEqual(intent.name, "status")

    def test_13_refresh_command_intent(self) -> None:
        intent = self.registry.match("refresh applications")
        self.assertIsNotNone(intent)
        self.assertEqual(intent.name, "refresh_applications")

    def test_14_unsupported_command(self) -> None:
        intent = self.registry.match("dance now")
        self.assertIsNone(intent)

    def test_15_empty_command(self) -> None:
        intent = self.registry.match("")
        self.assertIsNone(intent)

    def test_16_application_alias_integration(self) -> None:
        phrases = self.registry.get_grammar_phrases(
            ["chrome", "google chrome", "vscode"], 2
        )
        self.assertIn("open chrome", phrases)
        self.assertIn("launch google chrome", phrases)
        self.assertIn("start vscode", phrases)
        self.assertIn("maximize chrome", phrases)
        self.assertIn("move google chrome to monitor 2", phrases)

    def test_17_speech_grammar_compatibility(self) -> None:
        phrases = self.registry.get_grammar_phrases(["chrome"], 1)
        expected_subset = {
            "help",
            "what can you do",
            "jarvis status",
            "status",
            "show monitors",
            "list monitors",
            "how many monitors",
            "refresh applications",
            "open chrome",
            "launch chrome",
            "start chrome",
            "maximize chrome",
            "minimize chrome",
            "restore chrome",
            "move chrome to monitor 1",
        }
        for item in expected_subset:
            self.assertIn(item, phrases)
        self.assertNotIn("move chrome to monitor 2", phrases)

    def test_18_cpu_command_intents(self) -> None:
        for phrase in ("cpu usage", "cpu status", "processor usage"):
            with self.subTest(phrase=phrase):
                intent = self.registry.match(phrase)
                self.assertIsNotNone(intent)
                self.assertEqual(intent.name, "get_cpu_usage")

    def test_19_memory_command_intents(self) -> None:
        for phrase in ("memory usage", "ram usage", "memory status"):
            with self.subTest(phrase=phrase):
                intent = self.registry.match(phrase)
                self.assertIsNotNone(intent)
                self.assertEqual(intent.name, "get_memory_usage")

    def test_20_disk_command_intents(self) -> None:
        for phrase in ("disk usage", "disk status", "storage status"):
            with self.subTest(phrase=phrase):
                intent = self.registry.match(phrase)
                self.assertIsNotNone(intent)
                self.assertEqual(intent.name, "get_disk_usage")

    def test_21_battery_command_intents(self) -> None:
        for phrase in ("battery status", "battery level"):
            with self.subTest(phrase=phrase):
                intent = self.registry.match(phrase)
                self.assertIsNotNone(intent)
                self.assertEqual(intent.name, "get_battery_status")

    def test_22_time_command_intents(self) -> None:
        for phrase in ("what time is it", "current time", "time"):
            with self.subTest(phrase=phrase):
                intent = self.registry.match(phrase)
                self.assertIsNotNone(intent)
                self.assertEqual(intent.name, "get_current_time")

    def test_23_system_status_command_intent(self) -> None:
        intent = self.registry.match("system status")
        self.assertIsNotNone(intent)
        self.assertEqual(intent.name, "get_system_status")

    def test_24_mute_and_unmute_intents(self) -> None:
        intent_mute = self.registry.match("mute volume")
        self.assertIsNotNone(intent_mute)
        self.assertEqual(intent_mute.name, "mute_volume")

        intent_unmute = self.registry.match("unmute volume")
        self.assertIsNotNone(intent_unmute)
        self.assertEqual(intent_unmute.name, "unmute_volume")

    def test_25_volume_up_down_intents(self) -> None:
        intent_up = self.registry.match("volume up")
        self.assertIsNotNone(intent_up)
        self.assertEqual(intent_up.name, "volume_up")

        intent_down = self.registry.match("volume down")
        self.assertIsNotNone(intent_down)
        self.assertEqual(intent_down.name, "volume_down")

    def test_26_set_volume_intent_and_arguments(self) -> None:
        intent_num = self.registry.match("set volume to 50")
        self.assertIsNotNone(intent_num)
        self.assertEqual(intent_num.name, "set_volume")
        self.assertEqual(intent_num.arguments.get("level"), 50)

        intent_word = self.registry.match("set volume to fifty")
        self.assertIsNotNone(intent_word)
        self.assertEqual(intent_word.name, "set_volume")
        self.assertEqual(intent_word.arguments.get("level"), 50)

        intent_invalid = self.registry.match("set volume to unknown")
        self.assertIsNone(intent_invalid)

    def test_27_lock_computer_intent(self) -> None:
        for phrase in ("lock computer", "lock workstation"):
            with self.subTest(phrase=phrase):
                intent = self.registry.match(phrase)
                self.assertIsNotNone(intent)
                self.assertEqual(intent.name, "lock_computer")


if __name__ == "__main__":
    unittest.main()


