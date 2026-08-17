"""Command definitions and pattern matching for JARVIS assistant commands."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, Iterable, Sequence

from core.models import CommandIntent


@dataclass(frozen=True, slots=True)
class CommandDefinition:
    """Describes a supported assistant command, its patterns, and intent matching logic."""

    name: str
    patterns: tuple[str, ...] = ()
    verbs: tuple[str, ...] = ()
    description: str = ""
    matcher: Callable[[str, CommandDefinition], CommandIntent | None] | None = None

    def match(self, normalized_command: str) -> CommandIntent | None:
        """Attempt to match normalized user text to a CommandIntent."""
        if self.matcher is not None:
            return self.matcher(normalized_command, self)

        if normalized_command in self.patterns:
            return CommandIntent(name=self.name, raw_command=normalized_command)

        return None


class CommandRegistry:
    """Registry of supported command definitions and pattern matcher."""

    def __init__(self, definitions: Sequence[CommandDefinition] | None = None) -> None:
        self._definitions: dict[str, CommandDefinition] = {}
        if definitions:
            for defn in definitions:
                self.register(defn)

    def register(self, definition: CommandDefinition) -> None:
        """Register a command definition."""
        self._definitions[definition.name] = definition

    def get(self, name: str) -> CommandDefinition | None:
        """Retrieve a command definition by name."""
        return self._definitions.get(name)

    def list_definitions(self) -> list[CommandDefinition]:
        """Return all registered command definitions."""
        return list(self._definitions.values())

    def match(self, command_text: str) -> CommandIntent | None:
        """Match a normalized command string against all registered command definitions."""
        for definition in self._definitions.values():
            intent = definition.match(command_text)
            if intent is not None:
                return intent
        return None

    def get_static_phrases(self) -> list[str]:
        """Return all static textual phrases across registered commands."""
        phrases: set[str] = set()
        for definition in self._definitions.values():
            phrases.update(definition.patterns)
        return sorted(phrases)

    def get_grammar_phrases(
        self, application_names: Iterable[str], monitor_count: int
    ) -> list[str]:
        """Build exact command phrases for speech recognition grammar."""
        phrases: set[str] = set()
        phrases.update(self.get_static_phrases())

        names = sorted({
            " ".join(name.casefold().split())
            for name in application_names
            if isinstance(name, str) and name.strip()
        })

        for definition in self._definitions.values():
            if definition.verbs:
                if definition.name in {
                    "launch_application",
                    "maximize_window",
                    "minimize_window",
                    "restore_window",
                }:
                    for name in names:
                        for verb in definition.verbs:
                            phrases.add(f"{verb} {name}")
                elif definition.name == "move_window":
                    for name in names:
                        for number in range(1, monitor_count + 1):
                            phrases.add(f"move {name} to monitor {number}")
                elif definition.name == "set_volume":
                    for number in (0, 10, 20, 25, 30, 40, 50, 60, 70, 75, 80, 90, 100):
                        phrases.add(f"set volume to {number}")

        return sorted(phrases)


_WORD_TO_NUMBER = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19,
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90, "hundred": 100, "one hundred": 100,
}


def _match_launch(command: str, defn: CommandDefinition) -> CommandIntent | None:
    match = re.fullmatch(r"(?:open|launch|start) (.+)", command)
    if match:
        return CommandIntent(
            name=defn.name,
            target=match.group(1),
            raw_command=command,
        )
    return None


def _match_window_action(command: str, defn: CommandDefinition) -> CommandIntent | None:
    if not defn.verbs:
        return None
    verbs_pattern = "|".join(re.escape(v) for v in defn.verbs)
    match = re.fullmatch(rf"({verbs_pattern}) (.+)", command)
    if match:
        return CommandIntent(
            name=defn.name,
            target=match.group(2),
            raw_command=command,
        )
    return None


def _match_move_window(command: str, defn: CommandDefinition) -> CommandIntent | None:
    match = re.fullmatch(r"move (.+) to monitor (\d+)", command)
    if match:
        target, monitor_str = match.groups()
        return CommandIntent(
            name=defn.name,
            target=target,
            arguments={"monitor": int(monitor_str)},
            raw_command=command,
        )
    return None


def _match_set_volume(command: str, defn: CommandDefinition) -> CommandIntent | None:
    match = re.fullmatch(r"set volume to (.+)", command)
    if match:
        raw_val = match.group(1).strip()
        if raw_val.isdigit() or (raw_val.startswith("-") and raw_val[1:].isdigit()):
            level = int(raw_val)
            return CommandIntent(
                name=defn.name,
                arguments={"level": level},
                raw_command=command,
            )
        elif raw_val in _WORD_TO_NUMBER:
            level = _WORD_TO_NUMBER[raw_val]
            return CommandIntent(
                name=defn.name,
                arguments={"level": level},
                raw_command=command,
            )
        else:
            parts = raw_val.split()
            if len(parts) == 2 and parts[0] in _WORD_TO_NUMBER and parts[1] in _WORD_TO_NUMBER:
                level = _WORD_TO_NUMBER[parts[0]] + _WORD_TO_NUMBER[parts[1]]
                return CommandIntent(
                    name=defn.name,
                    arguments={"level": level},
                    raw_command=command,
                )
    return None


def get_default_command_registry() -> CommandRegistry:
    """Return a CommandRegistry pre-populated with JARVIS system commands."""
    registry = CommandRegistry()

    registry.register(
        CommandDefinition(
            name="help",
            patterns=("help", "what can you do"),
            description="Display available JARVIS commands",
        )
    )
    registry.register(
        CommandDefinition(
            name="status",
            patterns=("jarvis status", "status"),
            description="Report assistant lifecycle state and connected resources",
        )
    )
    registry.register(
        CommandDefinition(
            name="show_monitors",
            patterns=("show monitors", "list monitors"),
            description="List connected monitors and their resolutions",
        )
    )
    registry.register(
        CommandDefinition(
            name="count_monitors",
            patterns=("how many monitors",),
            description="Report the count of connected monitors",
        )
    )
    registry.register(
        CommandDefinition(
            name="refresh_applications",
            patterns=("refresh applications",),
            description="Re-run application discovery to update the registry",
        )
    )
    registry.register(
        CommandDefinition(
            name="launch_application",
            verbs=("open", "launch", "start"),
            description="Launch an application by name or alias",
            matcher=_match_launch,
        )
    )
    registry.register(
        CommandDefinition(
            name="maximize_window",
            verbs=("maximize",),
            description="Maximize an application window",
            matcher=_match_window_action,
        )
    )
    registry.register(
        CommandDefinition(
            name="minimize_window",
            verbs=("minimize",),
            description="Minimize an application window",
            matcher=_match_window_action,
        )
    )
    registry.register(
        CommandDefinition(
            name="restore_window",
            verbs=("restore",),
            description="Restore a window to normal state",
            matcher=_match_window_action,
        )
    )
    registry.register(
        CommandDefinition(
            name="move_window",
            verbs=("move",),
            description="Move an application window to a specific monitor",
            matcher=_match_move_window,
        )
    )
    registry.register(
        CommandDefinition(
            name="get_cpu_usage",
            patterns=("cpu usage", "cpu status", "processor usage"),
            description="Report current CPU usage percentage",
        )
    )
    registry.register(
        CommandDefinition(
            name="get_memory_usage",
            patterns=("memory usage", "ram usage", "memory status"),
            description="Report current RAM usage and available memory",
        )
    )
    registry.register(
        CommandDefinition(
            name="get_disk_usage",
            patterns=("disk usage", "disk status", "storage status"),
            description="Report system drive disk usage and available space",
        )
    )
    registry.register(
        CommandDefinition(
            name="get_battery_status",
            patterns=("battery status", "battery level"),
            description="Report battery percentage and charging state",
        )
    )
    registry.register(
        CommandDefinition(
            name="get_current_time",
            patterns=("what time is it", "current time", "time"),
            description="Report current local system time",
        )
    )
    registry.register(
        CommandDefinition(
            name="get_system_status",
            patterns=("system status",),
            description="Report combined system status metrics",
        )
    )
    registry.register(
        CommandDefinition(
            name="mute_volume",
            patterns=("mute volume", "mute"),
            description="Mute system audio",
        )
    )
    registry.register(
        CommandDefinition(
            name="unmute_volume",
            patterns=("unmute volume", "unmute"),
            description="Unmute system audio",
        )
    )
    registry.register(
        CommandDefinition(
            name="volume_up",
            patterns=("volume up",),
            description="Increase system volume by 5%",
        )
    )
    registry.register(
        CommandDefinition(
            name="volume_down",
            patterns=("volume down",),
            description="Decrease system volume by 5%",
        )
    )
    registry.register(
        CommandDefinition(
            name="set_volume",
            verbs=("set volume to",),
            description="Set system volume to an explicit percentage (0-100)",
            matcher=_match_set_volume,
        )
    )
    registry.register(
        CommandDefinition(
            name="lock_computer",
            patterns=("lock computer", "lock workstation"),
            description="Lock the current Windows user session",
        )
    )

    return registry


